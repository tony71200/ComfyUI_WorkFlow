"""Structural self-check for the patched v4 workflow: link bookkeeping, types, filename %refs%, v4 wiring."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pipeline_v4 import TITLE  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
d = json.load(open(sys.argv[1], encoding="utf-8"))
KEYS = ["id", "origin_id", "origin_slot", "target_id", "target_slot", "type"]


def check(nodes, links, sub=None):
    N = {n["id"]: n for n in nodes}
    L = [l if isinstance(l, dict) else dict(zip(KEYS, l)) for l in links]
    for l in L:
        if l["origin_id"] == -10:
            assert l["id"] in sub["inputs"][l["origin_slot"]]["linkIds"], l
        else:
            assert l["id"] in (N[l["origin_id"]]["outputs"][l["origin_slot"]]["links"] or []), ("out missing", l)
        if l["target_id"] == -20:
            assert l["id"] in sub["outputs"][l["target_slot"]]["linkIds"], l
        else:
            i = N[l["target_id"]]["inputs"][l["target_slot"]]
            assert i["link"] == l["id"], ("in mismatch", l, i)
            assert i["type"] in (l["type"], "*"), ("type", l, i)
    ids = {l["id"] for l in L}
    for n in nodes:
        for i in n["inputs"]:
            assert i["link"] in (None, *ids), (n.get("title", n["type"]), i)
        for o in n["outputs"]:
            assert set(o["links"] or []) <= ids, n
    assert len(ids) == len(L), "duplicate link ids"
    assert len(N) == len(nodes), "duplicate node ids"
    return len(L)


print("root links", check(d["nodes"], d["links"]))
for sg in d["definitions"]["subgraphs"]:
    print(sg["name"], "links", check(sg["nodes"], sg["links"], sg))
assert d["last_node_id"] >= max(n["id"] for n in d["nodes"])
assert d["last_link_id"] >= max(l[0] for l in d["links"])

# filename %refs% must hit exactly one node (S&R name)
srs = [n["properties"].get("Node name for S&R") for n in d["nodes"]]
save = next(n for n in d["nodes"] if n["type"] == "SaveImageA1Metadata")
fp = save["widgets_values"][0]
for ref in re.findall(r"%([A-Za-z0-9_]+)\.", fp):
    assert srs.count(ref) == 1, (ref, srs.count(ref))
assert "%MainTrigger.value%" in fp and "_v4_" in fp, fp
print("filename refs ok:", fp)

# v4 wiring
T = {n.get("title"): n for n in d["nodes"]}
for t in TITLE.values():
    assert t in T, ("missing node", t)
for t in ("Prefix", "Suffix", "MainTrigger", "Regex – bảng tra", "README – Krea2 LoRA T2I v4"):
    assert t in T, ("missing node", t)
for gone in ("3c. Bỏ 'negative prompt…'", "5a. Có trigger?", "5b. Ghép trigger vào đầu", "5c. Chốt an toàn", "5d. Ghép trigger vào cuối"):
    assert gone not in T, ("should be removed", gone)
LINK = {l[0]: l for l in d["links"]}


def src(title_or_id, name):
    n = T[title_or_id] if isinstance(title_or_id, str) else next(x for x in d["nodes"] if x["id"] == title_or_id)
    i = next(i for i in n["inputs"] if i["name"] == name)
    assert i["link"] is not None, (n.get("title"), name, "not linked")
    return next(x for x in d["nodes"] if x["id"] == LINK[i["link"]][1]).get("title")


assert src(TITLE["4a"], "string") == TITLE["3b"]
assert src(TITLE["4b"], "string") == TITLE["4a"]
assert src(TITLE["4f"], "string") == TITLE["4a"]
assert src(TITLE["5a"], "string") == TITLE["4h"] and src(TITLE["5b"], "string") == TITLE["5a"]
assert src(TITLE["6a"], "string") == TITLE["5f"]
assert src(TITLE["6b"], "string") == TITLE["6a"] and src(TITLE["6c"], "string") == TITLE["6b"]
assert src(TITLE["6d"], "string") == TITLE["6c"]
assert src(TITLE["6e"], "string_a") == "MainTrigger" and src(TITLE["6e"], "string_b") == "Prefix"
assert src(TITLE["6f"], "string_a") == TITLE["6e"] and src(TITLE["6f"], "string_b") == TITLE["6d"]
assert src(TITLE["6g"], "string_a") == TITLE["6f"] and src(TITLE["6g"], "string_b") == "Suffix"
assert src(TITLE["7b"], "text") == TITLE["6g"] and src(TITLE["7b"], "replace_in") == TITLE["7a"]
assert src(TITLE["7c"], "string") == TITLE["7b"] and src(TITLE["7d"], "string") == TITLE["7c"]
assert src(TITLE["7e"], "string") == TITLE["7d"]
for nid, name in ((45, "prompt"), (46, "positive_prompt_override"), (44, "source")):
    assert src(nid, name) == TITLE["7e"], (nid, name)
fr = T[TITLE["7b"]]["widgets_values"]
assert fr[1] == "" and fr[2] is True, fr
sr = T[TITLE["7a"]]["widgets_values"]
assert sr[:-2] == ["tnga_brief", "lrcontour_brief", "stng_bikini", "hpstr_brief", "dblstrap_bikini"] and sr[-1] == "randomize", sr
for sp in ("System prompt SFW", "System prompt NSFW"):
    text = T[sp]["widgets_values"][0]
    assert text == T[sp]["widgets_values_named"]["value"], sp
    nums = [int(m) for m in re.findall(r"^(\d+)\. \*\*", text, re.M)]
    assert nums == list(range(1, 13)), (sp, nums)
    assert "11. **Camera Defaults:**" in text and "White balance 5500K" in text, sp
assert "Keep every clothing item" in T["System prompt SFW"]["widgets_values"][0]

# layout: every Prompt Builder node sits inside its column group
G = {g["title"]: g["bounding"] for g in d["groups"]}
for col in "1234567":
    gt = next(t for t in G if t.startswith(f"{col}. "))
    x, y, w, h = G[gt]
    for k, t in TITLE.items():
        if k[0] == col:
            px, py = T[t]["pos"]
            assert x <= px and px + T[t]["size"][0] <= x + w and y <= py <= y + h, (gt, t)
print("v4 checks ok")
