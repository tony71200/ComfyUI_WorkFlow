"""Wait until N new runs finish in ComfyUI /history, then dump the fields the v4 report needs.

usage: collect_history.py OUT.json N"""
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pipeline_v4 import SWAP_ITEMS  # noqa: E402

API = "http://127.0.0.1:8188"


def get(path):
    return json.load(urllib.request.urlopen(API + path, timeout=30))


def record(pid, h):
    api, extra = h["prompt"][2], h["prompt"][3]
    sel = next(k for k, v in api.items() if v.get("class_type") == "Select_Random")
    idx = api[sel]["inputs"]["index"]
    out = h.get("outputs", {})
    return {"prompt_id": pid, "ts_index": api["42"]["inputs"]["index"], "seed": api["39"]["inputs"]["value"],
            "nsfw": api["55"]["inputs"]["value"], "select_index": idx, "token": SWAP_ITEMS[min(idx, len(SWAP_ITEMS) - 1)],
            "final": "".join(out.get("44", {}).get("text", [""])),
            "images": [f'{i["subfolder"]}/{i["filename"]}' for i in out.get("46", {}).get("images", [])],
            "status": h.get("status", {}).get("status_str"), "api": api, "extra": extra}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    out_path, n = Path(sys.argv[1]), int(sys.argv[2])
    seen = set(get("/history"))
    done = {}
    while len(done) < n:
        time.sleep(5)
        try:
            hist = get("/history")
        except OSError as e:  # server busy or restarting: keep waiting
            print("history fetch failed:", e, flush=True)
            continue
        for pid, h in hist.items():
            if pid not in seen and pid not in done and h.get("status", {}).get("completed") is not None:
                done[pid] = r = record(pid, h)
                print(f"{len(done)}/{n} ts={r['ts_index']} sel={r['select_index']} {r['token']} {r['status']}", flush=True)
    runs = sorted(done.values(), key=lambda r: r["ts_index"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(runs, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", out_path)
