import multiprocessing
import os
import queue
import signal
import threading

import osmod
from hashingFile import hashing
from journal import get_task_logger, setup_logging
from stop_control import StopController


class MultiProcess(osmod.Sequential):
    def __init__(self, hash_db, worker_num, path, stop=None, install_handler=True):
        if not isinstance(worker_num, int) or isinstance(worker_num, bool) or worker_num < 1:
            raise ValueError(
                f'worker number must be an integer >= 1 , you put {worker_num} '
            )  # P1-11 : maxsize=0 signifierait file illimitee + aucun consommateur
        super().__init__(hash_db, path)
        self.worker_num = worker_num
        self.queue = multiprocessing.Queue(maxsize=self.worker_num)
        self.results = multiprocessing.Queue(maxsize=self.worker_num)
        # sous Flask, Ctrl+C doit arreter le serveur : pas de handler installe
        self.stop = stop or StopController('process', install_handler=install_handler)
        # P0-07 : pose par le producteur quand il a fini d'emettre
        self.producer_done = multiprocessing.Event()
        # production incomplete : file pleine, dossier illisible, ...
        self.producer_failed = multiprocessing.Event()

        self.isprocess = True  # decide du SIG_IGN et de la configuration des logs

    def scan_complete(self):
        """Complete au sens du pipeline : pas d'abandon et production terminee."""
        return (
            super().scan_complete()
            and not self.stop.abort_requested()
            and not self.producer_failed.is_set()
        )

    def producer(self):
        if self.isprocess:
            log = setup_logging("producer", self.run_id)
            signal.signal(signal.SIGINT, signal.SIG_IGN)
        else:
            log = get_task_logger("producer", self.run_id)

        batch_size = 64
        batch = []
        sent_files = 0
        sent_batches = 0
        stopped = False

        def onerror(err):
            log.warning("walk error path=%s err=%s",
                        getattr(err, "filename", "?"), err)
            self.producer_failed.set()

        try:
            for root, dirs, names in os.walk(self.path, onerror=onerror):
                if stopped:
                    break
                if self.stop.abort_requested():
                    log.warning("abort requested -> stop admitting")
                    break
                for name in names:
                    if self.stop.abort_requested():
                        break
                    batch.append(os.path.join(root, name))
                    if len(batch) >= batch_size:
                        try:
                            self.queue.put(batch, timeout=20)
                            sent_files += len(batch)
                            sent_batches += 1
                        except queue.Full:
                            log.error("queue full -> producer gives up")
                            self.producer_failed.set()
                            stopped = True
                            break
                        batch = []
        finally:
            if batch and not stopped and not self.stop.abort_requested():
                try:
                    self.queue.put(batch, timeout=20)
                    sent_files += len(batch)
                    sent_batches += 1
                except queue.Full:
                    log.error("queue full on final batch")
                    self.producer_failed.set()

            for _ in range(self.worker_num):
                try:
                    self.queue.put(None, timeout=20)
                except queue.Full:
                    log.error("queue full while sending sentinels")
                    self.producer_failed.set()
                    break
            self.producer_done.set()
            log.info(
                "end producer files=%d batches=%d rc=%d",
                sent_files, sent_batches,
                1 if self.producer_failed.is_set() else 0,
            )

    def consumer(self):
        if self.isprocess:
            task = f"worker-{os.getpid()}"
            log = setup_logging(task, self.run_id)
            signal.signal(signal.SIGINT, signal.SIG_IGN)
        else:
            # un pid identique pour tous les threads : le nom du thread distingue
            task = f"worker-{threading.current_thread().name}"
            log = get_task_logger(task, self.run_id)

        done_count = 0
        left_count = 0
        try:
            while True:
                try:
                    batch = self.queue.get(timeout=20)
                except queue.Empty:
                    # P0-07 : file vide et production terminee -> plus rien a venir
                    if self.producer_done.is_set():
                        break
                    continue
                if batch is None:
                    break

                done, left = [], []
                for i, path in enumerate(batch):
                    if self.stop.stop_requested():
                        left = batch[i:]
                        log.warning("stop requested -> left=%d", len(left))
                        break
                    digest = hashing(path, self.stop.stop_requested, self.run_id)
                    if digest == "Error:Aborted":
                        # un fichier abandonne ne doit jamais entrer dans done
                        left = batch[i:]
                        log.warning("hashing aborted -> left=%d", len(left))
                        break
                    done.append((path, digest))

                if done:
                    self.results.put(("done", done))
                    done_count += len(done)
                if left:
                    self.results.put(("left", left))
                    left_count += len(left)
        finally:
            self.results.put(None)
            log.info("end consumer done=%d left=%d", done_count, left_count)

    def start_producer(self):
        producer_process = multiprocessing.Process(target=self.producer)
        producer_process.start()
        return producer_process

    def start_workers(self):
        workers = [
            multiprocessing.Process(
                target=self.consumer,
                name=f"process_{i}",
            )
            for i in range(self.worker_num)
        ]
        for worker in workers:
            worker.start()
        return workers

    def collect_results(self, workers, producer_process=None):
        log = get_task_logger("collector", self.run_id)
        flag = 0
        injected = False
        while flag < self.worker_num:
            try:
                item = self.results.get(timeout=1)  # P0-06 : jamais de get bloquant
            except queue.Empty:
                # P0-06 : plus aucun worker vivant -> des sentinelles manquent
                if not any(worker.is_alive() for worker in workers):
                    log.error("workers died before sending all sentinels")
                    self.interrupted = True
                    break
                # P0-07 : producteur mort sans avoir pose producer_done
                if (producer_process is not None
                        and not producer_process.is_alive()
                        and not self.producer_done.is_set()
                        and not injected):
                    log.warning("producer died -> injecting sentinels")
                    self.interrupted = True
                    ok = True
                    for _ in range(self.worker_num):
                        try:
                            self.queue.put(None, timeout=1)
                        except queue.Full:
                            ok = False
                            break
                    injected = ok
                continue

            if item is None:
                flag += 1
                continue
            kind, payload = item
            if kind == "done":
                for path, info in payload:
                    self.hash_directory[path] = info
            else:
                self.unprocessed.extend(payload)

        log.info(
            "collect end files=%d unprocessed=%d interrupted=%s",
            len(self.hash_directory), len(self.unprocessed), self.interrupted,
        )

    def parcour(self):
        log = get_task_logger("pipeline", self.run_id)
        self.hash_directory = {}
        self.unprocessed = []
        self.interrupted = False
        self.walk_failed = False
        self.producer_done.clear()
        self.producer_failed.clear()

        log.info("start pipeline workers=%d root=%s", self.worker_num, self.path)
        producer_process = self.start_producer()
        workers = self.start_workers()
        self.collect_results(workers, producer_process)

        producer_process.join(timeout=10)
        if producer_process.is_alive():
            log.warning("producer still alive after join timeout -> terminating")
            self.interrupted = True
            producer_process.terminate()
            producer_process.join(timeout=5)
        elif producer_process.exitcode != 0:
            log.error("producer exitcode=%s", producer_process.exitcode)

        for worker in workers:
            worker.join(timeout=30)
            if worker.is_alive():
                log.error("worker still alive after join timeout -> terminating name=%s",
                          worker.name)
                self.interrupted = True
                worker.terminate()
                worker.join(timeout=5)
            elif worker.exitcode not in (0, None):
                log.error("worker exitcode=%s name=%s",
                          worker.exitcode, worker.name)

        rc = 0 if self.scan_complete() else 1
        log.info(
            "end pipeline files=%d unprocessed=%d rc=%d",
            len(self.hash_directory), len(self.unprocessed), rc,
        )
        return self.hash_directory

    def verification_tmp(self, timestamp):
        log = get_task_logger("watch", self.run_id)
        if not self.isprocess:
            return self.helper(timestamp)
        helper_p = multiprocessing.Process(target=self.helper, args=(timestamp,))
        helper_p.start()
        helper_p.join()
        if helper_p.exitcode not in (0, None):
            log.error("helper exitcode=%s", helper_p.exitcode)

    def helper(self, timestamp):
        if self.isprocess:
            log = setup_logging("helper", self.run_id)
            signal.signal(signal.SIGINT, signal.SIG_IGN)
        else:
            log = get_task_logger("helper", self.run_id)

        if self.stop.abort_requested():
            log.warning("abort already requested -> helper exits")
            return
        if not self.First_run():
            log.warning("initial baseline not written -> helper exits")
            return

        i = 0
        while True:
            if self.stop.abort_requested():
                break
            i += 1
            self.run()
            if self.stop.abort_requested():
                break
            self.save_baseline()
            if self.unprocessed:
                log.warning("unprocessed files=%d", len(self.unprocessed))
            log.info("cycle end i=%d", i)
            if self.stop.wait_abort_requested(timestamp):
                break


if __name__ == "__main__":
    mlt = MultiProcess("hash_database.json", 3, '/home/moussa/Documents/otherFiles')
    setup_logging("cli", mlt.run_id, level="INFO", path="logs/fic.log")
    mlt.verification_tmp(5)
