import threading as thread
from queue import Queue

import multiProcess
from journal import get_task_logger, setup_logging
from stop_control import StopController


class MultiTreaded(multiProcess.MultiProcess):
    def __init__(self, hash_db, worker_num, path, install_handler=True):
        super().__init__(
            hash_db,
            worker_num,
            path,
            StopController('thread', install_handler=install_handler),
            install_handler=install_handler,
        )
        self.queue = Queue(maxsize=worker_num)
        self.results = Queue(maxsize=worker_num)
        self.isprocess = False  # pas de SIG_IGN, pas de reconfiguration des logs

    def parcour(self):
        log = get_task_logger("threads", self.run_id)
        self.hash_directory = {}
        self.unprocessed = []
        self.interrupted = False
        self.walk_failed = False
        self.producer_done.clear()
        self.producer_failed.clear()

        producer_process = thread.Thread(target=self.producer, name="producer")
        workers = [
            thread.Thread(target=self.consumer, name=f"thread_{i}")
            for i in range(self.worker_num)
        ]

        log.info("start pipeline workers=%d root=%s", self.worker_num, self.path)
        producer_process.start()
        for worker in workers:
            worker.start()

        self.collect_results(workers, producer_process)

        producer_process.join()
        for worker in workers:
            worker.join()

        rc = 0 if self.scan_complete() else 1
        log.info(
            "end pipeline files=%d unprocessed=%d rc=%d",
            len(self.hash_directory), len(self.unprocessed), rc,
        )
        return self.hash_directory


if __name__ == "__main__":
    multiT = MultiTreaded("hash_database.json", 3, '/home/moussa/Documents')
    setup_logging("cli", multiT.run_id, level="INFO", path="logs/fic.log")
    multiT.verification_tmp(5)
