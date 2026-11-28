# File Integrity Checker (FIC)

A local file integrity checking tool. It computes SHA‑256 hashes, keeps a
“baseline” per directory root, compares the current state with the baseline,
and displays five result categories:
**Modified Files**, **New Files**, **Deleted Files**, **Duplicate Files**, and
**Permission Denied Files**.

The application is provided as a Flask API plus two standalone HTML pages.
Three execution engines are available: `sequential`, `multiprocess`, and
`multithreaded`. An additional page provides **periodic verification**
(`verification_temp`) with a timestamp, a stop control, and the same results as
a normal check.

---

## 1. Features

- Baseline JSON indexed by canonical root (`realpath`): multiple roots can
  coexist in the same file without overwriting each other.
- Comparison: modified, new, deleted, duplicate, and permission-denied files.
- Three engines: sequential, multiprocess pipeline, and multithreaded pipeline.
- Configurable number of **workers** (1–64) for the parallel modes.
- Two-stage stop via Ctrl+C (CLI) or the **Stop** button / `/stop` endpoint
  (API).
- Centralized logging in `jornal.txt`, with one numbered block per scan,
  baseline, or periodic verification cycle.
- `verification_temp` page: start, stop, timestamp (seconds), execution mode,
  current state, **and results from the latest cycle**.
- Hamburger navigation between **Normal check** and **Verification temp**.

---

## 2. Web interface

Two pages are served by Flask:

| Page | URL | Role |
|---|---|---|
| Normal check | `http://127.0.0.1:5000/` | Create a baseline, run a one-off scan, view the 5 result sections. |
| Verification temp | `http://127.0.0.1:5000/verification_temp` | Start a periodic watcher, stop it, view the 5 result sections from the latest cycle. |

A hamburger button in the top-left opens the sidebar for switching between
pages. The active link is highlighted.

### “Normal check” page

Fields and buttons:

- `Enter Directory Path`: absolute path of the directory to analyze.
- `Execution mode`: `sequential`, `multiprocess`, `multithreaded`.
- `Number of workers`: integer 1–64, hidden in `sequential` mode, used as the
  number of processes or threads in the other modes (default `3`).
- **Create Baseline**: writes the reference snapshot for this root.
- **Run Check**: compares the directory with the baseline and displays the
  results.
- **Stop**: stops the current scan via `/stop`.
- Status banner and error banner visible in the results area.

The five sections are always present. When there are no differences, they show
`none` in the badge and `None` in the list.

### “Verification temp” page

Same fields, plus:

- `Timestamp (seconds)`: delay between two cycles (1–86400, default `5`).
- **Start check**: starts the watcher.
- **Stop**: requests shutdown; the current cycle finishes before exit.
- Status panel: state (`Running` / `Stopping…` / `Idle`), `run id`, directory,
  mode, workers, timestamp, start, end, `rc`, and cycle count.
- The five result sections are refreshed automatically every 2 seconds from
  `GET /verification_temp/status`.

A cycle = initial baseline + check + conditional baseline write, then a wait
of `timestamp` seconds.

---

## 3. Architecture

| File | Role |
|---|---|
| `osmod.py` | `Sequential` engine: traversal, comparison, baseline, invariant I1. |
| `multiProcess.py` | `MultiProcess(Sequential)`: producer + workers as processes. |
| `multiThreading.py` | `MultiTreaded(MultiProcess)`: same pipeline with threads. |
| `hashingFile.py` | SHA‑256 in 65,536-byte blocks, interruptible, `Error:<Type>` sentinel values. |
| `stop_control.py` | `abort` / `event` events and two-stage SIGINT handler. |
| `journal.py` | Only place that configures logging handlers. |
| `api/server.py` | Flask API, locks, watcher, block logging. |
| `api/templates/home.html` | Normal check page (markup only). |
| `api/templates/verification_temp.html` | Periodic watcher page (markup only). |
| `api/templates/app.css` | Shared stylesheet used by both pages. |
| `api/templates/api.js` | JavaScript for the normal check page. |
| `api/templates/verification_temp.js` | JavaScript for the periodic watcher page. |

The two HTML pages contain only markup. Styling lives in `app.css`, and the
page logic lives in `api.js` and `verification_temp.js`; Flask serves all three
assets with `Cache-Control: no-store`. Asset links are relative (`app.css`,
`api.js`, `verification_temp.js`), so the same HTML also works when opened from
`api/templates/` via Live Server or `file://`; under Flask they resolve to the
asset routes above. To change the layout, edit the HTML; to change styling,
edit `app.css`; to change behaviour, edit the matching JS file.
`TEMPLATES_AUTO_RELOAD = True` is enabled in Flask so template changes are
reloaded even with `debug=False`.

---

## 4. Prerequisites

- Python 3 (tested with Python 3.14.8 in the development environment).
- Flask (the only external dependency). The other modules use only the Python
  standard library.
- No `requirements.txt`, `pyproject.toml`, or `setup.py` is provided.


---

## 5. Installation

```bash
# go to the project directory

# optional but recommended
python3 -m venv .venv
source .venv/bin/activate

python3 -m pip install flask
```

No database needs to be installed: the baseline is a JSON file.

---

## 6. Configuration

All variables are optional.

| Variable | Default | Role |
|---|---|---|
| `FIC_BASELINE` | `<project>/hash_database.json` | Path to the baseline file used by the API. |
| `FIC_LOG_FILE` | `<project>/jornal.txt` | API log file. If set manually, the `SERVER LAUNCH` header is not rewritten. |
| `FIC_LOG_LEVEL` | `INFO` | Console handler level: `DEBUG`, `INFO`, `WARNING`, `ERROR`. The file handler is always `DEBUG`. |
| `FIC_LOG_JSON` | `0` | `1` writes one JSON object per line instead of the text format. |

Useful internal constants: `WORKERS = 3`, producer batch = 64 files, default
watcher timestamp = 5 seconds, API worker limits = 1–64 and timestamp =
0–86400 seconds.

---

## 7. Launching

### Flask server

From the project root:

```bash
python3 -m api.server
# equivalent:
python3 api/server.py
```

Then open:

- <http://127.0.0.1:5000/> — normal check;
- <http://127.0.0.1:5000/verification_temp> — periodic verification.

The server starts with `debug=False`, `threaded=True`, on Flask's default host
and port (`127.0.0.1:5000`). There is no CLI option to change the port. If the
port is already in use, stop the existing process before restarting.

`jornal.txt` is recreated on every launch: it contains only the logs from that
launch.

### With Live Server (port 5500)

The pages detect the port:

- on `:5000`, API calls are relative;
- on another port (e.g. `:5500` with Live Server), they call
  `http://127.0.0.1:5000`.

Flask must therefore already be running on port 5000. The server returns the
calling origin in `Access-Control-Allow-Origin` (or `*` if no origin is
provided), which also covers a page opened from `file://`.

### CLI demos

Three entry points exist, but they contain hardcoded paths and write to
`logs/fic.log` (not to `jornal.txt`):

```bash
python3 osmod.py           # Sequential on /home/moussa/Documents
python3 multiProcess.py    # MultiProcess(3) + verification_tmp(5)
python3 multiThreading.py  # MultiTreaded(3) + verification_tmp(5)
```

They need to be adapted before real use (paths, number of workers, timestamp).

---

## 8. Typical usage

1. Start the Flask server.
2. In **Normal check**, enter the directory to monitor.
3. Choose the mode, then the number of workers if the mode is parallel.
4. Click **Create Baseline** once for this root.
5. Modify / add / delete a few files.
6. Click **Run Check**: the five sections show the differences.

A scan with no changes legitimately shows `None` everywhere.

For periodic verification:

1. Open **Verification temp** from the sidebar.
2. Enter the directory, mode, workers, and timestamp.
3. Click **Start check**.
4. Modify files while waiting: on the next cycle, the results are updated
   automatically.
5. Click **Stop** to shut down cleanly.

---

## 9. HTTP API

All JSON responses are returned with CORS headers. Pages and assets are served
with `Cache-Control: no-store`.

### Routes

| Method | Route | Description |
|---|---|---|
| GET | `/` | Normal check page. |
| GET | `/verification_temp` | Periodic watcher page. |
| GET | `/app.css`, `/api.js`, `/verification_temp.js` | CSS and JS assets served by Flask. |
| POST | `/scan` | One-off scan. |
| POST | `/baseline` | Write the baseline for a root. |
| POST | `/verification_temp/start` | Start the watcher. |
| GET | `/verification_temp/status` | Watcher state + results from the latest cycle. |
| POST | `/verification_temp/stop` | Alias of `/stop` for the watcher. |
| GET, POST | `/stop` | Set the stop events on the current engine. |

### Common JSON body

```json
{
  "directory": "/home/user/Documents",
  "scanMode": "multiprocess",
  "workers": 4
}
```

- `scanMode`: `sequential` (default), `multiprocess`, `multithreaded`.
- `workers`: integer 1–64, default `3`, ignored by `sequential`.
- `/verification_temp/start` adds `timestamp` (seconds, default `5`).

### `/scan` response (200)

```json
{
  "directory": "/home/user/Documents",
  "mode": "multiprocess",
  "complete": true,
  "unprocessed": [],
  "modified": [],
  "new": [],
  "deleted": [],
  "permission_denied": [],
  "duplicates": {},
  "counts": {
    "modified": 0,
    "new": 0,
    "deleted": 0,
    "duplicate_groups": 0,
    "permission_denied": 0
  }
}
```

`duplicates` is an object `{ "<hash>": ["<path>", ...] }`.
`duplicate_groups` counts hash groups, not the number of files.

### `/verification_temp/status` response (200)

Contains `running`, `run_id`, `directory`, `mode`, `workers`, `timestamp`,
`started_at`, `stop_requested`, `last_run_id`, `last_rc`, `ended_at`, `cycles`,
and `last_result`. `last_result` contains the five lists, `counts`, `cycle`,
and `at`.

### HTTP codes

| Code | Meaning |
|---|---|
| 200 | Success, or watcher stopped. |
| 202 | Watcher started. |
| 400 | Invalid JSON, missing path or not a directory, invalid workers/timestamp, unknown mode, baseline missing for this root. |
| 409 | Scan already running, watcher already active, or operation refused because a watcher is running. |
| 500 | Unexpected error, details in `jornal.txt`. |

An interrupted scan returns `409` with `complete: false` and the `unprocessed`
list.

---

## 10. Baseline and invariant I1

`hash_database.json` is a nested object on disk, flat in memory per root:

```json
{
  "/home/user/Documents": {
    "/home/user/Documents/a.txt": "<sha256>",
    "/home/user/Documents/b.txt": "Error:PermissionError"
  },
  "/home/user/Autre": {
    "/home/user/Autre/c.txt": "<sha256>"
  }
}
```

- First-level keys are canonical roots (`realpath(abspath(path))`): `/data`,
  `/data/`, and a symbolic link all denote the same root.
- Each root maps an absolute path to its hash or to an `Error:<Type>` sentinel.
- `First_run()` always replaces the entry for the requested root and preserves
  the other roots.
- Writing uses `open(..., "w")` + `json.dump(indent=2)`: it is **not atomic**. If
  the process is interrupted during the write, repeat the action.
- A root missing from the JSON raises `KeyError` during a check; the frontend
  then displays the error in the banner.

**Invariant I1**: the baseline is written only by a complete scan.
`save_baseline()` is the only write point and refuses to write if
`unprocessed`, `interrupted`, `walk_failed`, `abort_requested`, or
`producer_failed` indicate an incomplete run. The API watcher uses the same
function.

---

## 11. Engines, stop, and return codes

### Engines

- `sequential`: simple traversal with `os.walk(onerror=...)`.
- `multiprocess`: producer + workers (processes), bounded queues, end-of-stream
  sentinels, dead-worker detection, `SIGINT → SIG_IGN` in children.
- `multithreaded` (`MultiTreaded`): same logic with `threading.Thread` and
  `queue.Queue`.

### Stop

`StopController` exposes two events:

- 1st Ctrl+C: `abort` — the producer stops admitting new files, workers drain
  the queue;
- 2nd Ctrl+C: `event` — workers stop at the file / hash-block boundary.

The SIGINT handler is installed only in the main thread. The sequential engine
installs no handler: Ctrl+C raises `KeyboardInterrupt` there. Under Flask, no
engine installs a handler, so Ctrl+C keeps its role for the server; stopping is
done with the **Stop** button or `POST /stop`, which sets `abort` and `event`
directly. `/stop` does not stop Flask itself.

### Codes

- Log: `rc=0` success, `rc=1` incomplete/cancelled, `rc=2` error.
- HTTP: see the code table above.
- The `complete` field of `/scan` reflects `engine.scan_complete()`.

---

## 12. Logging

`journal.py` is the only module that configures handlers. The other modules use
`get_task_logger(task, run)`; each child process calls `setup_logging()` at the
start of its task.

Text format (one line per event):

```text
2026-11-28T11:32:31.192+0000 INFO     pid=55991 tid=140510749546176 run=bae773f6 task=baseline written root=/tmp/data entries=42 roots=1
```

Fields: ISO timestamp with milliseconds before the timezone, level, PID, thread
id, 8-hex-digit `run`, `task`, message. Start/end lines carry a duration and
`rc=`.

### `jornal.txt`

- Recreated on every server launch, with a `SERVER LAUNCH` header (timestamp
  and PID).
- Then each `/scan`, `/baseline`, and watcher opens a numbered block:

```text
==============================================================================
... CHECK #1 START run=f6273d57 directory=/home/user/Documents mode=sequential workers=3
==============================================================================
... run=f6273d57 task=hashing permission denied path=...
... run=f6273d57 task=check done files=10 modified=0 new=0 deleted=0 denied=1 duplicates=1 duration=0.003s
==============================================================================
... CHECK #1 END run=f6273d57 rc=0 duration=0.003s
==============================================================================
... CHECK #2 START run=a9a89f1e ...
```

- All lines in a block share the same `run=...`, including those from workers
  and threads.
- Multiprocess children write to the same file in append mode (`O_APPEND`);
  there is no rotation.
- CLI demos write to `logs/fic.log`, not to `jornal.txt`.

---

## 13. Quick verification

Once the server is running:

```bash
# pages
curl -i http://127.0.0.1:5000/
curl -i http://127.0.0.1:5000/verification_temp

# create a baseline
curl -X POST http://127.0.0.1:5000/baseline \
  -H 'Content-Type: application/json' \
  -d '{"directory":"/home/user/Documents","scanMode":"sequential","workers":3}'

# run a check
curl -X POST http://127.0.0.1:5000/scan \
  -H 'Content-Type: application/json' \
  -d '{"directory":"/home/user/Documents","scanMode":"multiprocess","workers":4}'

# periodic watcher
curl -X POST http://127.0.0.1:5000/verification_temp/start \
  -H 'Content-Type: application/json' \
  -d '{"directory":"/home/user/Documents","scanMode":"sequential","timestamp":5,"workers":3}'

curl http://127.0.0.1:5000/verification_temp/status
curl -X POST http://127.0.0.1:5000/verification_temp/stop
```

`jornal.txt` should contain a single `SERVER LAUNCH` and properly closed
`CHECK #n`, `BASELINE #n`, or `VERIFICATION_TEMP #n` blocks.

---

## 14. Project tree

```text
osProject/
├── api/
│   ├── server.py                  # Flask API
│   └── templates/
│       ├── home.html              # normal check (markup only)
│       ├── verification_temp.html # periodic watcher (markup only)
│       ├── api.js                 # normal check JavaScript
│       ├── verification_temp.js   # periodic watcher JavaScript
│       └── app.css                # shared stylesheet
├── dicTest.py                     # sandbox
├── hash_database.json             # actual baseline
├── hashingFile.py                 # interruptible SHA-256
├── journal.py                     # logging configuration
├── jornal.txt                     # logs from the latest server launch
├── logs/fic.log                   # CLI logs (git-ignored)
├── multiProcess.py                # multiprocess engine
├── multiThreading.py              # multithread engine
├── osmod.py                       # sequential engine + baseline
├── rapport-corrections.md         # corrections analysis
├── rapport-engine.md              # engine analysis
├── stop_control.py                # events and SIGINT
├── test.py, test2.py              # sandboxes / demos
└── README.md
```

No `benchmarks/` folder is provided: no performance figures are published in
this README.

---

## 15. Limits and points to verify

- [TO VERIFY] The sidebar setup is duplicated in `api.js` and
  `verification_temp.js`; it could be moved to a third shared file.
- [TO VERIFY] Baseline writing is not atomic.
- [TO VERIFY] `hash_database.json` is versioned and contains local absolute
  paths; for a clean deployment, delete it and regenerate it via
  **Create Baseline**.
- [TO VERIFY] `First_run(force=False)` and `check_run(baseline=False)` accept
  an unused parameter.
- [TO VERIFY] `WATCH_STATE.run_id` keeps the last watcher's ID after it stops;
  the interface shows `run_id` before `last_run_id`.
- [TO VERIFY] CLI demos use hardcoded paths and `logs/fic.log`.
- [TO VERIFY] `test2.py` requires `rich` (not declared); `dicTest.py` is not
  executable as-is.
- [TO VERIFY] No versioned automated tests are provided in the repository.
