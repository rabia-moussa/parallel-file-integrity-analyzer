from urllib import response

from flask import render_template , Flask , request
from osmod import Sequential
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
  
    path = request.get_json()
    path = path.get("directory")
    print(f"Received directory path: {path}")
    seq = Sequential('hash_database.json', path)
    modified, new, deleted, duplicates, permission_denied=seq.check_run()
    return json.dumps({
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
    })    

if __name__=="__main__":
    app.run(debug=True)