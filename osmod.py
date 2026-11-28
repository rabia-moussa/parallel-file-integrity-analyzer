from collections import Counter
import json
import logging
import os
import time

from hashingFile import hashing
from journal import get_task_logger, new_run_id, setup_logging
from stop_control import StopController


class Sequential:
    def __init__(self, hash_db, path):
        self.hash_db = hash_db
        # cle canonique : /data, /data/ et un lien symbolique designent la meme racine
        self.path = os.path.realpath(os.path.abspath(path))
        self.hash_directory = {}
        # etat de completude du dernier scan (voir scan_complete)
        self.unprocessed = []
        self.interrupted = False
        self.walk_failed = False
        self.run_id = new_run_id()
        # evenements seulement : Ctrl+C continue de lever KeyboardInterrupt
        self.stop = StopController(None, install_handler=False)

    def check_duplicate(self):
        log = get_task_logger("duplicates", self.run_id)
        valid_files = {}
        for path, hash in self.hash_directory.items():
            if hash is None:
                continue
            try:
                if os.path.getsize(path) == 0:
                    continue
            except OSError as err:
                log.warning("getsize failed path=%s err=%s", path, err)
                continue
            if hash.startswith("Error:"):
                continue
            valid_files[path] = hash
        hash_counts = Counter(valid_files.values())
        duplicated_files = [
            (path, hash)
            for path, hash in valid_files.items()
            if hash_counts[hash] > 1
        ]
        result = {}
        for path, hash in duplicated_files:
            result.setdefault(hash, []).append(path)
        log.debug("groups=%d files=%d", len(result), len(duplicated_files))
        return result

    def check_modified(self):
        log = get_task_logger("check", self.run_id)
        try:
            with open(self.hash_db, 'r') as f:
                hash_database = json.load(f)
        except FileNotFoundError:
            log.error("baseline file missing path=%s", self.hash_db)
            raise KeyError(f"no baseline file : {self.hash_db}") from None
        except json.JSONDecodeError as err:
            log.error("baseline file invalid path=%s err=%s", self.hash_db, err)
            raise KeyError(f"invalid baseline file : {self.hash_db}") from None

        entries = hash_database.get(self.path)
        if entries is None:
            log.error("no baseline for root=%s", self.path)
            raise KeyError(f"no baseline for this root : {self.path}")

        ls_modified = [
            path
            for path, hash in self.hash_directory.items()
            if path in entries and hash != entries[path]
        ]
        ls_new = [path for path in self.hash_directory if path not in entries]
        ls_deleted = [
            path
            for path in entries
            if path not in self.hash_directory and not os.path.lexists(path)
        ]
        ls_permission_denied = [
            path
            for path, hash in self.hash_directory.items()
            if hash.startswith("Error:PermissionError")
        ]
        log.debug(
            "modified=%d new=%d deleted=%d denied=%d",
            len(ls_modified), len(ls_new), len(ls_deleted), len(ls_permission_denied),
        )
        return ls_modified, ls_new, ls_deleted, ls_permission_denied

    def parcour(self):
        log = get_task_logger("scan", self.run_id)
        if not os.path.isdir(self.path):
            log.error("not a directory path=%s", self.path)
            raise ValueError(f"not a directory: {self.path}")

        self.hash_directory = {}
        self.walk_failed = False
        self.interrupted = False

        def onerror(err):
            # os.walk ignore silencieusement les dossiers illisibles : on le trace
            # et on marque le scan incomplet pour ne pas ecrire un baseline partiel.
            self.walk_failed = True
            log.warning("walk error path=%s err=%s",
                        getattr(err, "filename", "?"), err)

        start = time.perf_counter()
        for root, dirs, files in os.walk(self.path, onerror=onerror):
            if self.stop.abort_requested():
                self.interrupted = True
                break
            for name in files:
                if self.stop.abort_requested():
                    self.interrupted = True
                    break
                full = os.path.join(root, name)
                digest = hashing(full, self.stop.abort_requested, self.run_id)
                if digest == "Error:Aborted":
                    self.interrupted = True
                    break
                self.hash_directory[full] = digest
            if self.interrupted:
                break
        log.info(
            "walk done files=%d walk_failed=%s duration=%.3fs",
            len(self.hash_directory), self.walk_failed,
            time.perf_counter() - start,
        )
        return self.hash_directory

    def scan_complete(self):
        """True si le dernier scan a couvert toute la racine sans abandon."""
        return not self.unprocessed and not self.interrupted and not self.walk_failed

    def save_baseline(self):
        """Ecrit le baseline uniquement si le scan est complet (invariant I1)."""
        log = get_task_logger("baseline", self.run_id)
        if not self.scan_complete():
            log.warning(
                "skipped reason=incomplete unprocessed=%d interrupted=%s walk_failed=%s",
                len(self.unprocessed), self.interrupted, self.walk_failed,
            )
            return False

        data = {}
        if os.path.lexists(self.hash_db):
            try:
                with open(self.hash_db) as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    raise ValueError("baseline must be a JSON object")
            except (json.JSONDecodeError, OSError, ValueError):
                log.warning("unreadable -> rebuilding path=%s", self.hash_db)
                data = {}

        # ancien format plat : chemin -> hash (aucune racine stockee)
        if data and all(isinstance(v, str) for v in data.values()):
            log.warning("legacy flat format -> rebuilding path=%s", self.hash_db)
            data = {}

        data[self.path] = self.hash_directory
        with open(self.hash_db, 'w') as f:
            json.dump(data, f, indent=2)
        log.info("written root=%s entries=%d roots=%d",
                 self.path, len(self.hash_directory), len(data))
        return True

    def First_run(self, force=False):
        """Cree ou remplace l'entree de cette racine dans le baseline.

        `force` est conserve pour compatibilite avec l'API : l'entree de la
        racine est de toute facon remplacee, les autres racines sont preservees.
        """
        log = get_task_logger("baseline", self.run_id)
        log.info("start root=%s", self.path)
        self.hash_directory = self.parcour()
        ok = self.save_baseline()
        log.info("end root=%s rc=%d", self.path, 0 if ok else 1)
        return ok

    def check_run(self, baseline: bool = False):
        log = get_task_logger("check", self.run_id)
        self.interrupted = False
        self.walk_failed = False
        self.unprocessed = []
        try:
            start = time.perf_counter()
            self.hash_directory = self.parcour()
            if self.interrupted:
                log.warning("scan aborted before comparison")
                return None
            modified, new, deleted, permission_denied = self.check_modified()
            duplicates = self.check_duplicate()
            log.info(
                "done files=%d modified=%d new=%d deleted=%d denied=%d "
                "duplicates=%d duration=%.3fs",
                len(self.hash_directory), len(modified), len(new), len(deleted),
                len(permission_denied), len(duplicates),
                time.perf_counter() - start,
            )
            return modified, new, deleted, duplicates, permission_denied
        except KeyboardInterrupt:
            self.interrupted = True
            log.warning("interrupted by user")
            return None

    def run(self):
        result = self.check_run(False)
        if result is None:
            print('the check in interrupted')
            return None
        modified, new, deleted, duplicates, permission_denied = result
        print('the modified files are: ', modified)
        print('the new files are: ', new)
        print('the deleted files are: ', deleted)
        print('the duplicate files are: ', duplicates)
        print('the permission denied files are: ', permission_denied)
        return result

    def verification_tmp(self, timestamp):
        """Boucle de verification periodique, arretable par /stop.

        Un cycle = check + ecriture conditionnelle du baseline (I1), puis
        attente de `timestamp` secondes. Le drapeau `abort` est verifie a chaque
        frontiere pour que le 2e Ctrl+C / le bouton Stop interrompe la boucle.
        """
        log = get_task_logger("watch", self.run_id)
        if self.stop.abort_requested():
            log.warning("abort already requested -> watcher exits")
            return
        if not self.First_run():
            log.warning("initial baseline not written -> watcher exits")
            return

        i = 0
        while not self.stop.abort_requested():
            i += 1
            result = self.run()
            if result is None or self.stop.abort_requested():
                break
            self.save_baseline()
            log.info("cycle end i=%d", i)
            if self.stop.wait_abort_requested(timestamp):
                break
        log.info("watch end cycles=%d rc=%d", i, 1 if self.stop.abort_requested() else 0)


if __name__ == "__main__":
    seq = Sequential('hash_database.json', '/home/moussa/Documents')
    setup_logging("cli", seq.run_id, level="INFO", path="logs/fic.log")
    seq.First_run()
    seq.run()
