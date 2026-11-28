import hashlib as hs
import logging

from journal import get_task_logger

log = logging.getLogger("fic.hashing")


def hashing(file, stop=None, run=None):
    """Empreinte SHA-256 d'un fichier, lue par blocs.

    `stop` est un predicat sans argument (par exemple self.stop.stop_requested).
    Il est consulte entre deux blocs ; s'il renvoie True, la fonction retourne
    "Error:Aborted" sans avoir produit d'empreinte.
    `run` est l'identifiant du bloc de log courant, pour que les avertissements
    restent dans le meme run que le scan qui les a provoques.
    """
    log = get_task_logger("hashing", run) if run else log
    try:
        hashobj = hs.sha256()
        with open(file, 'rb') as f:
            while True:
                if stop is not None and stop():
                    return "Error:Aborted"
                data = f.read(65536)
                if not data:
                    break
                hashobj.update(data)
        return hashobj.hexdigest()
    except FileNotFoundError as err:
        log.warning("file not found path=%s", file)
        return f"Error:{type(err).__name__}"
    except PermissionError as err:
        log.warning("permission denied path=%s", file)
        return f"Error:{type(err).__name__}"
    except OSError as err:
        log.warning("os error path=%s err=%s", file, err)
        return f"Error:{type(err).__name__}"
    except Exception as err:
        log.exception("hashing failed path=%s", file)
        return f"Error:{type(err).__name__}"
