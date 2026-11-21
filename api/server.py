from urllib import response

from flask import render_template , Flask , request
from osmod import Sequential
from multiProcess import MultiProcess
from multiThreading import MultiTreaded
import json

app=Flask(__name__)
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "http://127.0.0.1:5500"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response



@app.route("/scan",methods=["POST"])
def scan():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return {"error": "Request body must be a JSON object."}, 400

    directory = payload.get("directory")
    mode = payload.get("scanMode", "sequential")
    if not isinstance(directory, str) or not directory.strip():
        return {"error": "A directory path is required."}, 400

    if mode == "sequential":
        seq = Sequential("hash_database.json", directory)
    elif mode == "multiprocess":
        seq = MultiProcess("hash_database.json", 3, directory)
    elif mode == "multithreaded":
        seq = MultiTreaded("hash_database.json", 3, directory)
    else:
        return {"error": f"Unknown scan mode: {mode}"}, 400

    print(f"Received directory path: {directory}")
    print(f"the mode is {mode}")
    modified, new, deleted, duplicates, permission_denied=seq.check_run()
    return {
        "modified": modified,
        "new": new,
        "deleted": deleted,
        "permission_denied": permission_denied,
        "duplicates":duplicates,
        "counts": {
                "modified": len(modified),
                "new": len(new),
                "deleted": len(deleted),
                "duplicate_groups": len(duplicates),
                "permission_denied": len(permission_denied)
            },
    }

@app.route("/baseline", methods=["POST"])
def baseline():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return {"error": "Request body must be a JSON object."}, 400
    
    directory = payload.get("directory")
    mode = payload.get("scanMode", "sequential")
    if not isinstance(directory, str) or not directory.strip():
        return {"error": "A directory path is required."}, 400

    if mode == "sequential":
        scanner = Sequential("hash_database.json", directory)
    elif mode == "multiprocess":
        scanner = MultiProcess("hash_database.json", 3, directory)
    elif mode == "multithreaded":
        scanner = MultiTreaded("hash_database.json", 3, directory)
    else:
        return {"error": f"Unknown scan mode: {mode}"}, 400
    print(f"Received directory path: {directory}")
    print(f"the mode is {mode}")
    scanner.First_run(True)

    return {
        "status": "ok",
        "directory": directory,
        "mode": mode,
    }, 200

@app.route('/stop')
def clean_stoppage(): # stop the instance used now by changing the flag by set()
    pass


if __name__=="__main__":
    app.run(debug=True)