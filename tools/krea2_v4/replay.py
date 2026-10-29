"""Replay recorded runs (same seed, TextSplitter index, Select_Random index) with nsfw set, optionally taking the
system prompts and string-processing widgets from the current workflow file.

usage: replay.py IN.json OUT.json --nsfw {true,false} --tag NAME [--sync]"""
import argparse
import copy
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from collect_history import API, get, record  # noqa: E402
from pipeline_v4 import WF_PATH  # noqa: E402

SYNC_TYPES = {"RegexReplace", "RegexMatch", "StringReplace", "StringConcatenate", "StringTrim"}
SYNC_TITLES = {"System prompt SFW", "System prompt NSFW"}


def post(path, body):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=30))


def sync(api, wf):
    """Copy widget values of the prompt-logic nodes from the workflow file; wired inputs (lists) stay as they are.
    Nodes inside a subgraph appear in the API prompt as "<instance id>:<inner id>"."""
    subs = wf["definitions"]["subgraphs"]
    keyed = [(str(n["id"]), n) for n in wf["nodes"]]
    for inst in wf["nodes"]:
        for sg in subs:
            if inst["type"] == sg["id"]:
                keyed += [(f"{inst['id']}:{n['id']}", n) for n in sg["nodes"]]
    for key, n in keyed:
        if key in api and (n["type"] in SYNC_TYPES or n.get("title") in SYNC_TITLES):
            inputs = api[key]["inputs"]
            for k, v in n["widgets_values_named"].items():
                if k in inputs and not isinstance(inputs[k], list):
                    inputs[k] = v


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("out")
    ap.add_argument("--nsfw", choices=["true", "false"], required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--sync", action="store_true")
    a = ap.parse_args()
    wf = json.loads(WF_PATH.read_text(encoding="utf-8"))
    out = []
    for r in json.load(open(a.src, encoding="utf-8")):
        api = copy.deepcopy(r["api"])
        api["55"]["inputs"]["value"] = a.nsfw == "true"
        api["46"]["inputs"]["filename_prefix"] += f"_{a.tag}"
        if a.sync:
            sync(api, wf)
        pid = post("/prompt", {"prompt": api, "extra_data": r["extra"], "client_id": f"krea2-v4-{a.tag}"})["prompt_id"]
        while True:
            time.sleep(5)
            try:
                h = get(f"/history/{pid}").get(pid)
            except OSError:
                continue
            if h and h.get("status", {}).get("completed") is not None:
                break
        out.append(record(pid, h))
        print(f"{len(out)} ts={out[-1]['ts_index']} {out[-1]['status']}", flush=True)
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", a.out)
