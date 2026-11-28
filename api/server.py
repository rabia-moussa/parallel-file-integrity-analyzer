import datetime
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

# verification_temp tourne dans un thread : il ne doit pas bloquer les scans
# ponctuels, mais un seul watcher peut etre actif a la fois.
WATCH_LOCK = threading.Lock()
WATCH_STATE = {
    "running": False,
    "engine": None,
    "thread": None,
    "run_id": None,
    "directory": None,
    "mode": None,
    "timestamp": None,
    "workers": WORKERS,
    "started_at": None,
    "stop_requested": False,
    "last_run_id": None,
    "last_rc": None,
    "ended_at": None,
    "cycles": 0,
    "last_result": None,
}


def build_engine(mode, directory, workers=WORKERS):
    if mode == "sequential":
        return Sequential(BASELINE, directory)
    if mode == "multiprocess":
        # pas de handler SIGINT : Ctrl+C doit garder son role (arreter Flask)
        return MultiProcess(BASELINE, workers, directory, install_handler=False)
    if mode == "multithreaded":
        return MultiTreaded(BASELINE, workers, directory, install_handler=False)
    raise ValueError(f"Unknown scan mode: {mode}")


def parse_workers(payload):
    """Nombre de workers pour multiprocess / multithreaded (defaut WORKERS)."""
    value = payload.get("workers", WORKERS)
    if isinstance(value, bool):
        return None, ({"error": "workers must be an integer >= 1."}, 400)
    try:
        workers = int(value)
    except (TypeError, ValueError):
        return None, ({"error": "workers must be an integer >= 1."}, 400)
    if workers < 1 or workers > 64:
        return None, ({"error": "workers must be between 1 and 64."}, 400)
    return workers, None


def parse_payload():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return None, None, None, ({"error": "Request body must be a JSON object."}, 400)

    directory = payload.get("directory")
    mode = payload.get("scanMode", "sequential")
    if not isinstance(directory, str) or not directory.strip():
        return None, None, None, ({"error": "A directory path is required."}, 400)

    directory = directory.strip()
    if not os.path.isdir(directory):
        return None, None, None, ({"error": f"Not a directory: {directory}"}, 400)

    workers, error = parse_workers(payload)
    if error:
        return None, None, None, error
    return directory, mode, workers, None


@app.after_request
def add_cors_headers(response):
    # on renvoie l'origine appelante ; '*' couvre une page ouverte en file://
    origin = request.headers.get("Origin")
    response.headers["Access-Control-Allow-Origin"] = origin or "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    # page et assets toujours frais pendant le developpement
    if request.path in ("/", "/verification_temp", "/app.css", "/api.js"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/")
def index():
    return render_template("home.html")


@app.route("/verification_temp")
def verification_temp_page():
    return render_template("verification_temp.html")


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
    if kind == "check":
        return "CHECK"
    if kind == "watch":
        return "VERIFICATION_TEMP"
    return "BASELINE"


def begin_run(kind, directory, mode, workers=None):
    """Ouvre un bloc numéroté et bien délimité dans jornal.txt."""
    with COUNTER_LOCK:
        RUN_COUNTER[0] += 1
        seq = RUN_COUNTER[0]

    run_id = new_run_id()
    run_log = get_task_logger("api", run_id)
    label = run_label(kind)
    workers_field = "" if workers is None else f" workers={workers}"
    run_log.info("%s", SEPARATOR)
    run_log.info(
        "%s #%d START run=%s directory=%s mode=%s%s",
        label, seq, run_id, directory, mode, workers_field,
    )
    run_log.info("%s", SEPARATOR)
    return seq, run_id, run_log


def finish_run(run_log, run_id, kind, seq, rc, duration, **fields):
    """Ferme le bloc, y compris quand le scan lève une exception."""
    details = " ".join(f"{key}={value}" for key, value in fields.items())
    label = run_label(kind)
    suffix = (" " + details) if details else ""
    run_log.info("%s", SEPARATOR)
    run_log.info(
        "%s #%d END run=%s rc=%d duration=%.3fs%s",
        label, seq, run_id, rc, duration, suffix,
    )
    run_log.info("%s", SEPARATOR)


def now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def watcher_running():
    with WATCH_LOCK:
        return bool(WATCH_STATE["running"])


def parse_timestamp(payload):
    value = payload.get("timestamp", payload.get("period", 5))
    if isinstance(value, bool):
        return None, ({"error": "timestamp must be a number of seconds."}, 400)
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None, ({"error": "timestamp must be a number of seconds."}, 400)
    if seconds <= 0 or seconds > 86400:
        return None, ({"error": "timestamp must be between 0 and 86400 seconds."}, 400)
    return seconds, None


def store_watch_result(result, cycle):
    """Rend le dernier cycle disponible pour la page verification_temp."""
    modified, new, deleted, duplicates, permission_denied = result
    with WATCH_LOCK:
        WATCH_STATE["cycles"] = cycle
        WATCH_STATE["last_result"] = {
            "modified": modified,
            "new": new,
            "deleted": deleted,
            "duplicates": duplicates,
            "permission_denied": permission_denied,
            "counts": {
                "modified": len(modified),
                "new": len(new),
                "deleted": len(deleted),
                "duplicate_groups": len(duplicates),
                "permission_denied": len(permission_denied),
            },
            "cycle": cycle,
            "at": now_iso(),
        }


def watch_loop(engine, timestamp, run_log, run_id, seq, started):
    """Boucle periodique : check + baseline conditionnel, hors du thread HTTP.

    On pilote le moteur ici plutot que via engine.verification_tmp() afin que
    le resultat de chaque cycle reste dans le processus Flask et puisse etre
    renvoye a l'interface (les enfants multiprocess ne partagent pas la memoire).
    """
    rc = 2
    cycles = 0
    try:
        if engine.stop.abort_requested():
            run_log.warning("abort already requested -> watcher exits")
            rc = 1
            return
        if not engine.First_run():
            run_log.warning("initial baseline not written -> watcher exits")
            rc = 1
            return

        while not engine.stop.abort_requested():
            cycles += 1
            run_log.info("cycle start i=%d", cycles)
            result = engine.check_run()
            if result is None or engine.stop.abort_requested():
                break
            store_watch_result(result, cycles)
            engine.save_baseline()
            run_log.info(
                "cycle end i=%d complete=%s", cycles, engine.scan_complete()
            )
            if engine.stop.wait_abort_requested(timestamp):
                break
        rc = 1 if engine.stop.abort_requested() else 0
        run_log.info("watch end cycles=%d rc=%d", cycles, rc)
    except Exception:
        run_log.exception("verification_temp failed")
        rc = 2
    finally:
        finish_run(
            run_log, run_id, "watch", seq, rc, time.perf_counter() - started,
            timestamp=timestamp, cycles=cycles,
        )
        with ENGINE_LOCK:
            if CURRENT_ENGINE[0] is engine:
                CURRENT_ENGINE[0] = None
        with WATCH_LOCK:
            WATCH_STATE.update({
                "running": False,
                "engine": None,
                "thread": None,
                "stop_requested": rc == 1,
                "last_run_id": run_id,
                "last_rc": rc,
                "ended_at": now_iso(),
            })


@app.route("/scan", methods=["POST"])
def scan():
    directory, mode, workers, error = parse_payload()
    if error:
        return error

    if watcher_running():
        log.warning("scan rejected root=%s reason=watcher", directory)
        return {"error": "Verification temp is running."}, 409

    if not SCAN_LOCK.acquire(blocking=False):
        log.warning("scan rejected root=%s reason=busy", directory)
        return {"error": "A scan is already running."}, 409

    seq, run_id, run_log = begin_run("check", directory, mode, workers)
    started = time.perf_counter()
    rc = 2
    try:
        try:
            engine = build_engine(mode, directory, workers)
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
    directory, mode, workers, error = parse_payload()
    if error:
        return error

    if watcher_running():
        log.warning("baseline rejected root=%s reason=watcher", directory)
        return {"error": "Verification temp is running."}, 409

    if not SCAN_LOCK.acquire(blocking=False):
        log.warning("baseline rejected root=%s reason=busy", directory)
        return {"error": "A scan is already running."}, 409

    seq, run_id, run_log = begin_run("baseline", directory, mode, workers)
    started = time.perf_counter()
    rc = 2
    try:
        try:
            engine = build_engine(mode, directory, workers)
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


@app.route("/verification_temp/start", methods=["POST"])
def verification_start():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return {"error": "Request body must be a JSON object."}, 400

    directory, mode, workers, error = parse_payload()
    if error:
        return error
    timestamp, error = parse_timestamp(payload)
    if error:
        return error

    if watcher_running():
        return {"error": "Verification temp is already running."}, 409
    if not SCAN_LOCK.acquire(blocking=False):
        return {"error": "A scan is already running."}, 409
    with WATCH_LOCK:
        WATCH_STATE["running"] = True
    SCAN_LOCK.release()

    try:
        engine = build_engine(mode, directory, workers)
    except ValueError as exc:
        with WATCH_LOCK:
            WATCH_STATE["running"] = False
        return {"error": str(exc)}, 400

    seq, run_id, run_log = begin_run("watch", directory, mode, workers)
    engine.run_id = run_id
    started = time.perf_counter()
    with WATCH_LOCK:
        WATCH_STATE.update({
            "engine": engine,
            "run_id": run_id,
            "directory": directory,
            "mode": mode,
            "timestamp": timestamp,
            "workers": workers,
            "started_at": now_iso(),
            "stop_requested": False,
            "ended_at": None,
            "last_run_id": None,
            "last_rc": None,
            "cycles": 0,
            "last_result": None,
        })
    with ENGINE_LOCK:
        CURRENT_ENGINE[0] = engine

    thread = threading.Thread(
        target=watch_loop,
        args=(engine, timestamp, run_log, run_id, seq, started),
        name=f"watch-{run_id}",
        daemon=True,
    )
    with WATCH_LOCK:
        WATCH_STATE["thread"] = thread
    thread.start()

    return {
        "status": "started",
        "run_id": run_id,
        "directory": directory,
        "mode": mode,
        "timestamp": timestamp,
        "workers": workers,
    }, 202


@app.route("/verification_temp/status")
def verification_status():
    with WATCH_LOCK:
        state = {
            key: value
            for key, value in WATCH_STATE.items()
            if key not in ("engine", "thread")
        }
        engine = WATCH_STATE["engine"]
    if engine is not None:
        state["stop_requested"] = engine.stop.abort_requested()
    return state, 200


@app.route("/verification_temp/stop", methods=["POST"])
def verification_stop():
    return clean_stoppage()


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
    actor_log = log
    with WATCH_LOCK:
        if WATCH_STATE["engine"] is engine:
            WATCH_STATE["stop_requested"] = True
            if WATCH_STATE["run_id"]:
                actor_log = get_task_logger("api", WATCH_STATE["run_id"])
    actor_log.warning("stop requested via API")
    return {"status": "stopping"}, 200


if __name__ == "__main__":
    app.run(debug=False, threaded=True)
