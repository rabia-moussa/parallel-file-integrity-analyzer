"""Journalisation centralisee du moteur File Integrity Checker.

Regle d'architecture :
  - ce module est le SEUL endroit qui configure les handlers (console, fichier) ;
  - les autres modules se contentent de `logging.getLogger("fic.<module>")` ;
  - en multi-processus (forkserver), chaque processus enfant doit appeler
    `setup_logging()` au debut de sa tache, car il n'herite pas des handlers
    configures dans le parent.

Format produit (une ligne par evenement) :
  2026-11-28T09:14:02.117+0100 INFO  pid=48211 tid=48211 run=9f3a1c2e task=scan start scan root=/data

Variables d'environnement :
  FIC_LOG_LEVEL  DEBUG | INFO | WARNING | ERROR   (defaut INFO)
  FIC_LOG_FILE   chemin du fichier de log          (defaut : console seule)
  FIC_LOG_JSON   1 pour un objet JSON par ligne    (defaut 0)
"""
import datetime
import json
import logging
import os
import sys
import time
import uuid
from contextlib import contextmanager

FORMAT = (
    "%(asctime)s %(levelname)-8s "
    "pid=%(process)d tid=%(thread)d run=%(run)s task=%(task)s %(message)s"
)
DATEFMT = "%Y-%m-%dT%H:%M:%S%z"


def _iso_time(record):
    """Horodatage ISO 8601 local avec millisecondes AVANT le fuseau.

    2026-11-28T09:14:02.117+0100
    """
    moment = datetime.datetime.fromtimestamp(record.created).astimezone()
    return (
        moment.strftime("%Y-%m-%dT%H:%M:%S")
        + f".{int(record.msecs):03d}"
        + moment.strftime("%z")
    )


class TextFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        return _iso_time(record)


class ContextFilter(logging.Filter):
    """Complete task/run pour les enregistrements qui ne les portent pas.

    Le filtre est attache aux handlers (et non au logger) pour couvrir aussi
    les messages propages depuis les loggers enfants (fic.osmod, ...).
    """

    def __init__(self, task, run):
        super().__init__()
        self.task = task
        self.run = run

    def filter(self, record):
        if not hasattr(record, "task"):
            record.task = self.task
        if not hasattr(record, "run"):
            record.run = self.run
        return True


class JsonFormatter(logging.Formatter):
    """Un objet JSON par ligne, pour l'agregation des mesures."""

    def format(self, record):
        payload = {
            "ts": _iso_time(record),
            "level": record.levelname,
            "pid": record.process,
            "tid": record.thread,
            "run": getattr(record, "run", ""),
            "task": getattr(record, "task", ""),
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def new_run_id():
    """Identifiant court pour correler toutes les lignes d'un meme scan."""
    return uuid.uuid4().hex[:8]


def start_log_file(path, label):
    """Recree le fichier de log et ecrit l'en-tete d'un lancement.

    Le fichier ne contient ainsi que les evenements d'UN seul lancement du
    serveur ; les processus enfants y ajoutent ensuite leurs lignes en mode
    append (O_APPEND) via `setup_logging()`.
    """
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    moment = datetime.datetime.now().astimezone().strftime(
        "%Y-%m-%dT%H:%M:%S.%f%z"
    )
    with open(path, "w", encoding="utf-8") as fichier:
        fichier.write("=" * 78 + "\n")
        fichier.write(
            f"{moment} SERVER LAUNCH pid={os.getpid()} {label}\n"
        )
        fichier.write("=" * 78 + "\n")
    return path


def setup_logging(task, run, level=None, path=None, json_logs=None):
    """Configure les handlers du logger racine `fic` et renvoie un adapter.

    A appeler une fois dans le parent, puis une fois dans CHAQUE processus
    enfant (producer, consumer, helper) sous forkserver.
    """
    base = logging.getLogger("fic")
    base.setLevel(logging.DEBUG)
    base.propagate = False          # evite le handler par defaut de la racine
    base.handlers.clear()           # neutralise un etat herite d'un fork eventuel

    level = (level or os.getenv("FIC_LOG_LEVEL", "INFO")).upper()
    if json_logs is None:
        json_logs = os.getenv("FIC_LOG_JSON", "0") == "1"
    formatter = JsonFormatter() if json_logs else TextFormatter(FORMAT, DATEFMT)
    context = ContextFilter(task, run)

    console = logging.StreamHandler(sys.stderr)
    console.setLevel(getattr(logging, level, logging.INFO))
    console.setFormatter(formatter)
    console.addFilter(context)
    base.addHandler(console)

    path = path or os.getenv("FIC_LOG_FILE")
    if path:
        directory = os.path.dirname(os.path.abspath(path))
        os.makedirs(directory, exist_ok=True)
        fichier = logging.FileHandler(path, mode="a", encoding="utf-8")
        fichier.setLevel(logging.DEBUG)
        fichier.setFormatter(formatter)
        fichier.addFilter(context)
        base.addHandler(fichier)

    return get_task_logger(task, run)


def get_task_logger(task, run):
    """Logger du module courant, enrichi de la tache et du run.

    N'installe aucun handler : la configuration doit deja avoir ete faite
    par setup_logging() dans ce processus.
    """
    return logging.LoggerAdapter(
        logging.getLogger("fic"), {"task": task, "run": run}
    )


@contextmanager
def span(logger, name, **fields):
    """Trace le debut, la fin, la duree et le code de retour d'une tache.

    rc=0 si la tache se termine normalement, rc=2 si elle leve.
    """
    t0 = time.perf_counter()
    details = " ".join(f"{key}={value}" for key, value in fields.items())
    logger.info("start %s %s", name, details)
    rc = 0
    try:
        yield
    except Exception:
        logger.exception("error %s", name)
        rc = 2
        raise
    finally:
        logger.info(
            "end %s rc=%d duration=%.3fs", name, rc, time.perf_counter() - t0
        )
