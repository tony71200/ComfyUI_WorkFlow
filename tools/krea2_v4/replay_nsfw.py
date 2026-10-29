"""Replay every pass-A run with only nsfw flipped to true (same seed, same TextSplitter and Select_Random index).

usage: replay_nsfw.py passA.json passB.json"""
import copy
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from collect_history import API, get, record  # noqa: E402


def post(path, body):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=30))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    runs = json.load(open(sys.argv[1], encoding="utf-8"))
    out = []
    for r in runs:
        api = copy.deepcopy(r["api"])
        api["55"]["inputs"]["value"] = True
        api["46"]["inputs"]["filename_prefix"] += "_nsfw"
        pid = post("/prompt", {"prompt": api, "extra_data": r["extra"], "client_id": "krea2-v4-replay"})["prompt_id"]
        while True:
            time.sleep(5)
            try:
                h = get(f"/history/{pid}").get(pid)
            except OSError:
                continue
            if h and h.get("status", {}).get("completed") is not None:
                break
        out.append(record(pid, h))
        print(f"{len(out)}/{len(runs)} ts={out[-1]['ts_index']} {out[-1]['status']}", flush=True)
    Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", sys.argv[2])
