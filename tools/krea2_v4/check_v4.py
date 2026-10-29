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

# subgraph "Krea2 Prompt Builder v4": columns 1-6 + S and the system prompts inside, column 7 outside
PB = next(sg for sg in d["definitions"]["subgraphs"] if sg["name"] == "Krea2 Prompt Builder v4")
INST = next(n for n in d["nodes"] if n["type"] == PB["id"])
assert INST.get("title") in (None, PB["name"])  # the frontend saves null when the node shows the subgraph name
assert [i["name"] for i in INST["inputs"]] == [i["name"] for i in PB["inputs"]], "instance inputs != subgraph inputs"
assert [o["name"] for o in INST["outputs"]] == [o["name"] for o in PB["outputs"]] == ["prompt"]
assert all(i["link"] is not None for i in INST["inputs"]), "unwired Prompt Builder input"
ROOT = {n["id"]: n for n in d["nodes"]}
INNER = {n["id"]: n for n in PB["nodes"]}
assert not ROOT.keys() & INNER.keys(), "node id used both at root and inside the subgraph"
T = {n.get("title"): n for n in [*ROOT.values(), *INNER.values()]}
for k, t in TITLE.items():
    assert t in T, ("missing node", t)
    assert (T[t]["id"] in INNER) == (k[0] in "123456S"), ("wrong side of the subgraph", t)
for t in ("System prompt SFW", "System prompt NSFW"):
    assert T[t]["id"] in INNER, t
for t in ("Prefix", "Suffix", "MainTrigger", "Regex – bảng tra", "README – Krea2 LoRA T2I v4"):
    assert T.get(t, {}).get("id") in ROOT, ("missing root node", t)
for gone in ("3c. Bỏ 'negative prompt…'", "5a. Có trigger?", "5b. Ghép trigger vào đầu", "5c. Chốt an toàn", "5d. Ghép trigger vào cuối"):
    assert gone not in T, ("should be removed", gone)
RL = {l[0]: dict(zip(KEYS, l)) for l in d["links"]}
IL = {l["id"]: l for l in PB["links"]}


def origin_title(link, inner):
    """Title of the real node a link comes from, looking through the subgraph boundary both ways."""
    if inner and link["origin_id"] == -10:
        return origin_title(RL[INST["inputs"][link["origin_slot"]]["link"]], False)
    if inner:
        return INNER[link["origin_id"]].get("title")
    if link["origin_id"] == INST["id"]:
        il = next(l for l in PB["links"] if l["target_id"] == -20 and l["target_slot"] == link["origin_slot"])
        return origin_title(il, True)
    return ROOT[link["origin_id"]].get("title")


def src(title_or_id, name):
    n = T[title_or_id] if isinstance(title_or_id, str) else ROOT[title_or_id]
    inner = n["id"] in INNER
    i = next(i for i in n["inputs"] if i["name"] == name)
    assert i["link"] is not None, (n.get("title"), name, "not linked")
    return origin_title((IL if inner else RL)[i["link"]], inner)


assert src(TITLE["4a"], "string") == TITLE["3b"]
assert src(TITLE["4b"], "string") == TITLE["4a"]
assert src(TITLE["4f"], "string") == TITLE["4a"]
assert src(TITLE["5a"], "string") == TITLE["4h"] and src(TITLE["5b"], "string") == TITLE["5a"]
assert src(TITLE["S1"], "string") == TITLE["5f"] and src(TITLE["S2"], "string") == TITLE["S1"]
assert src(TITLE["S3"], "string") == TITLE["S2"] and src(TITLE["S4"], "string_a") == TITLE["S2"]
assert (src(TITLE["S5"], "switch"), src(TITLE["S5"], "on_true"), src(TITLE["S5"], "on_false")) == (TITLE["S3"], TITLE["S2"], TITLE["S4"])
assert (src(TITLE["S6"], "switch"), src(TITLE["S6"], "on_true"), src(TITLE["S6"], "on_false")) == ("nsfw", TITLE["5f"], TITLE["S5"])
assert src(TITLE["6a"], "string") == TITLE["S6"]
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
sfw = T["System prompt SFW"]["widgets_values"][0]
assert "7. **Always Keep the Groin Covered:**" in sfw and "Keep every clothing item" in sfw and "Respect the Human Form" not in sfw
assert "let me know" in T[TITLE["4b"]]["widgets_values_named"]["regex_pattern"]

assert src(TITLE["3b"], "clip") == "Text encoder Qwen3-VL-4B (type krea2)"
assert src(TITLE["1"], "on_true") == "TextSplitter" and src(TITLE["1"], "switch").startswith("use_txt")
assert src(TITLE["4h"], "switch") == "refine (LLM)" and src(TITLE["3a"], "switch") == "nsfw"

# layout: every Prompt Builder node sits inside its column group (subgraph coordinates for columns 1-6 + S)
for col in "12345S67":
    G = {g["title"]: g["bounding"] for g in (PB["groups"] if col in "123456S" else d["groups"])}
    gt = next(t for t in G if t.startswith(f"{col}. "))
    x, y, w, h = G[gt]
    for k, t in TITLE.items():
        if k[0] == col:
            px, py = T[t]["pos"]
            assert x <= px and px + T[t]["size"][0] <= x + w and y <= py <= y + h, (gt, t)
print("v4 checks ok")
