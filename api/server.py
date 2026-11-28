import os
import sys
import threading
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
# permet `python3 api/server.py` autant que `python3 -m api.server`
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from flask import Flask, render_template, request, send_from_directory  # noqa: E402

from journal import (  # noqa: E402
    get_task_logger,
    new_run_id,
    setup_logging,
    start_log_file,
)
from multiProcess import MultiProcess  # noqa: E402
from multiThreading import MultiTreaded  # noqa: E402
from osmod import Sequential  # noqa: E402

TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
BASELINE = os.environ.get("FIC_BASELINE") or os.path.join(
    PROJECT_DIR, "hash_database.json"
)
LOG_FILE = os.environ.get("FIC_LOG_FILE") or os.path.join(
    PROJECT_DIR, "jornal.txt"
)
WORKERS = 3

# Un seul fichier par lancement du serveur. Les enfants heritent de la variable
# et ajoutent leurs lignes dans ce meme fichier avec O_APPEND.
if not os.environ.get("FIC_LOG_FILE"):
    os.environ["FIC_LOG_FILE"] = LOG_FILE
    start_log_file(LOG_FILE, "log=jornal.txt")

LAUNCH_ID = new_run_id()
log = setup_logging("api", LAUNCH_ID)

app = Flask(__name__)
# sans debug, Jinja garde les templates en cache : on recharge home.html/modifications CSS
app.config["TEMPLATES_AUTO_RELOAD"] = True

# un seul scan a la fois ; /stop doit pouvoir retrouver le moteur en cours
SCAN_LOCK = threading.Lock()
ENGINE_LOCK = threading.Lock()
CURRENT_ENGINE = [None]


def build_engine(mode, directory):
    if mode == "sequential":
        return Sequential(BASELINE, directory)
    if mode == "multiprocess":
        # pas de handler SIGINT : Ctrl+C doit garder son role (arreter Flask)
        return MultiProcess(BASELINE, WORKERS, directory, install_handler=False)
    if mode == "multithreaded":
        return MultiTreaded(BASELINE, WORKERS, directory, install_handler=False)
    raise ValueError(f"Unknown scan mode: {mode}")


def parse_payload():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return None, None, ({"error": "Request body must be a JSON object."}, 400)

    directory = payload.get("directory")
    mode = payload.get("scanMode", "sequential")
    if not isinstance(directory, str) or not directory.strip():
        return None, None, ({"error": "A directory path is required."}, 400)

    directory = directory.strip()
    if not os.path.isdir(directory):
        return None, None, ({"error": f"Not a directory: {directory}"}, 400)
    return directory, mode, None


@app.after_request
def add_cors_headers(response):
    # on renvoie l'origine appelante ; '*' couvre une page ouverte en file://
    origin = request.headers.get("Origin")
    response.headers["Access-Control-Allow-Origin"] = origin or "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    # page et assets toujours frais pendant le developpement
    if request.path in ("/", "/app.css", "/api.js"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/")
def index():
    return render_template("home.html")


@app.route("/app.css")
def app_css():
    return send_from_directory(TEMPLATES_DIR, "app.css")


@app.route("/api.js")
def api_js():
    return send_from_directory(TEMPLATES_DIR, "api.js")


SEPARATOR = "=" * 78
RUN_COUNTER = [0]
COUNTER_LOCK = threading.Lock()


def run_label(kind):
    return "CHECK" if kind == "check" else "BASELINE"


def begin_run(kind, directory, mode):
    """Ouvre un bloc numéroté et bien délimité dans jornal.txt."""
    with COUNTER_LOCK:
        RUN_COUNTER[0] += 1
        seq = RUN_COUNTER[0]

    run_id = new_run_id()
    run_log = get_task_logger("api", run_id)
    label = run_label(kind)
    run_log.info("%s", SEPARATOR)
    run_log.info(
        "%s #%d START run=%s directory=%s mode=%s",
        label, seq, run_id, directory, mode,
    )
    run_log.info("%s", SEPARATOR)
    return seq, run_id, run_log


def finish_run(run_log, run_id, kind, seq, rc, duration, **fields):
    """Ferme le bloc, y compris quand le scan lève une exception."""
    details = " ".join(f"{key}={value}" for key, value in fields.items())
    label = run_label(kind)
    run_log.info("%s", SEPARATOR)
    run_log.info(
        "%s #%d END run=%s rc=%d duration=%.3fs %s",
        label, seq, run_id, rc, duration, details,
    )
    run_log.info("%s", SEPARATOR)


@app.route("/scan", methods=["POST"])
def scan():
    directory, mode, error = parse_payload()
    if error:
        return error

    if not SCAN_LOCK.acquire(blocking=False):
        log.warning("scan rejected root=%s reason=busy", directory)
        return {"error": "A scan is already running."}, 409

    seq, run_id, run_log = begin_run("check", directory, mode)
    started = time.perf_counter()
    rc = 2
    try:
        try:
            engine = build_engine(mode, directory)
            # toutes les lignes du moteur portent le meme identifiant de bloc
            engine.run_id = run_id
        except ValueError as exc:
            run_log.error("invalid mode mode=%s err=%s", mode, exc)
            rc = 2
            return {"error": str(exc)}, 400

        with ENGINE_LOCK:
            CURRENT_ENGINE[0] = engine
        try:
            result = engine.check_run()
        except KeyError as exc:
            run_log.warning("no baseline root=%s err=%s", directory, exc)
            rc = 2
            return {"error": str(exc)}, 400
        except Exception:
            run_log.exception("scan failed root=%s mode=%s", directory, mode)
            rc = 2
            return {"error": "scan failed, see logs"}, 500
        finally:
            with ENGINE_LOCK:
                CURRENT_ENGINE[0] = None

        if result is None:
            rc = 1
            return {
                "error": "scan interrupted",
                "complete": False,
                "unprocessed": engine.unprocessed,
            }, 409

        modified, new, deleted, duplicates, permission_denied = result
        rc = 0
        return {
            "directory": directory,
            "mode": mode,
            "complete": engine.scan_complete(),
            "unprocessed": engine.unprocessed,
            "modified": modified,
            "new": new,
            "deleted": deleted,
            "permission_denied": permission_denied,
            "duplicates": duplicates,
            "counts": {
                "modified": len(modified),
                "new": len(new),
                "deleted": len(deleted),
                "duplicate_groups": len(duplicates),
                "permission_denied": len(permission_denied),
            },
        }, 200
    finally:
        finish_run(
            run_log, run_id, "check", seq, rc, time.perf_counter() - started
        )
        SCAN_LOCK.release()


@app.route("/baseline", methods=["POST"])
def baseline():
    directory, mode, error = parse_payload()
    if error:
        return error

    if not SCAN_LOCK.acquire(blocking=False):
        log.warning("baseline rejected root=%s reason=busy", directory)
        return {"error": "A scan is already running."}, 409

    seq, run_id, run_log = begin_run("baseline", directory, mode)
    started = time.perf_counter()
    rc = 2
    try:
        try:
            engine = build_engine(mode, directory)
            engine.run_id = run_id
        except ValueError as exc:
            run_log.error("invalid mode mode=%s err=%s", mode, exc)
            return {"error": str(exc)}, 400

        with ENGINE_LOCK:
            CURRENT_ENGINE[0] = engine
        try:
            ok = engine.First_run()
        except Exception:
            run_log.exception("baseline failed root=%s mode=%s", directory, mode)
            return {"error": "baseline failed, see logs"}, 500
        finally:
            with ENGINE_LOCK:
                CURRENT_ENGINE[0] = None

        if not ok:
            rc = 1
            return {
                "error": "baseline not written: scan incomplete",
                "complete": False,
                "unprocessed": engine.unprocessed,
            }, 409

        rc = 0
        return {
            "status": "ok",
            "directory": directory,
            "mode": mode,
            "entries": len(engine.hash_directory),
        }, 200
    finally:
        finish_run(
            run_log, run_id, "baseline", seq, rc, time.perf_counter() - started
        )
        SCAN_LOCK.release()


@app.route("/stop", methods=["GET", "POST"])
def clean_stoppage():
    with ENGINE_LOCK:
        engine = CURRENT_ENGINE[0]
    if engine is None:
        return {"status": "idle"}, 200

    stop = getattr(engine, "stop", None)
    if stop is None:
        return {"error": "this engine cannot be stopped"}, 400

    # arret en deux temps : admission puis workers
    stop.abort.set()
    stop.event.set()
    log.warning("stop requested via API")
    return {"status": "stopping"}, 200


if __name__ == "__main__":
    app.run(debug=False, threaded=True)
