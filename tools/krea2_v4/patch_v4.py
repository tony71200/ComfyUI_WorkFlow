"""Patch Krea2_LoRA_T2I_v4.json in place into the v4 Prompt Builder (spec 2026-10-29).

Works on the user's hand-edited file and refuses to run twice; to redo: git checkout Krea2_LoRA_T2I_v4.json."""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pipeline_v4 import (FILENAME_PREFIX, README_V4, REFUSE_EXTRA, REGEX_NOTE, RX_DEDUP, RX_DEDUP_REPL,  # noqa: E402
                         RX_DOTS, RX_DOTS_REPL, RX_LEAD_CHAR, RX_THINK, SFW_ANCHOR, SFW_KEEP_CLOTHES, SWAP_FIND,
                         SWAP_ITEMS, TITLE, WF_PATH)

sys.stdout.reconfigure(encoding="utf-8")
w = json.loads(WF_PATH.read_text(encoding="utf-8"))
N = {n["id"]: n for n in w["nodes"]}
assert 64 in N and 80 in N, "already patched — git checkout Krea2_LoRA_T2I_v4.json first"


# ---------- graph helpers ----------
def drop_link(lid):
    l = next(l for l in w["links"] if l[0] == lid)
    w["links"].remove(l)
    _, s, ss, d, ds, _ = l
    if s in N:
        N[s]["outputs"][ss]["links"].remove(lid)
    if d in N:
        N[d]["inputs"][ds]["link"] = None


def rm_node(nid):
    for l in [l for l in w["links"] if nid in (l[1], l[3])]:
        drop_link(l[0])
    w["nodes"].remove(N.pop(nid))


def link(src, out_slot, dst, name):
    ins = N[dst]["inputs"]
    slot = next((k for k, i in enumerate(ins) if i["name"] == name), None)
    if slot is None:  # widget input that was never wired (core nodes only list wired widgets)
        ins.append({"name": name, "type": "STRING", "widget": {"name": name}, "link": None})
        slot = len(ins) - 1
    if ins[slot]["link"] is not None:
        drop_link(ins[slot]["link"])
    w["last_link_id"] += 1
    lid = w["last_link_id"]
    out = N[src]["outputs"][out_slot]
    w["links"].append([lid, src, out_slot, dst, slot, out["type"]])
    out["links"] = (out["links"] or []) + [lid]
    ins[slot]["link"] = lid


def set_w(nid, name, value):
    """Keep widgets_values and widgets_values_named in step (same key order)."""
    named = N[nid]["widgets_values_named"]
    N[nid]["widgets_values"][list(named).index(name)] = value
    named[name] = value


def get_w(nid, name):
    return N[nid]["widgets_values_named"][name]


def new_id():
    w["last_node_id"] += 1
    return w["last_node_id"]


def clone(tid, title, **vals):
    n = copy.deepcopy(N[tid])
    n["id"], n["title"], n["order"] = new_id(), title, 0
    for i in n["inputs"]:
        i["link"] = None
    for o in n["outputs"]:
        o["links"] = []
    w["nodes"].append(n)
    N[n["id"]] = n
    for k, v in vals.items():
        set_w(n["id"], k, v)
    return n["id"]


def add_tony(typ, title, inputs, values, size):
    nid = new_id()
    N[nid] = {"id": nid, "type": typ, "pos": [0, 0], "size": size, "flags": {}, "order": 0, "mode": 0,
              "inputs": inputs, "outputs": [{"name": "text", "type": "STRING", "links": []}], "title": title,
              "properties": {"Node name for S&R": typ}, "widgets_values": values}
    w["nodes"].append(N[nid])
    return nid


RX_OFF = dict(case_insensitive=False, multiline=False, dotall=False, count=0)

# ---------- column 4: thinking guard, drop 3c, refusal check reads cleaned text ----------
n4a = clone(65, TITLE["4a"], regex_pattern=RX_THINK, replace="", **RX_OFF)
rm_node(64)
link(63, 0, n4a, "string")
link(n4a, 0, 65, "string")
link(n4a, 0, 69, "string")
set_w(69, "regex_pattern", get_w(69, "regex_pattern") + REFUSE_EXTRA)

# ---------- column 6: assemble MainTrigger. Prefix. body. Suffix ----------
for nid in (78, 79, 80, 82):
    rm_node(nid)
n6a = clone(65, TITLE["6a"], regex_pattern=RX_LEAD_CHAR, replace="", **RX_OFF)
link(76, 0, n6a, "string")
link(n6a, 0, 77, "string")
n6c, n6d, n6e = (clone(58, TITLE[k], string_a="", string_b="", delimiter=". ") for k in ("6c", "6d", "6e"))
link(38, 0, n6c, "string_a"); link(83, 0, n6c, "string_b")
link(n6c, 0, n6d, "string_a"); link(77, 0, n6d, "string_b")
link(n6d, 0, n6e, "string_a"); link(84, 0, n6e, "string_b")

# ---------- column 7: random clothing token swap + tidy ----------
n7a = add_tony("Select_Random", TITLE["7a"], [], SWAP_ITEMS + [0, "randomize"], [320, 230])
n7b = add_tony("Find_and_Replace", TITLE["7b"],
               [{"name": "text", "type": "STRING", "link": None},
                {"name": "replace_in", "shape": 7, "type": "STRING", "link": None}],
               [SWAP_FIND, "", True], [320, 130])
link(n6e, 0, n7b, "text")
link(n7a, 0, n7b, "replace_in")
n7c = clone(65, TITLE["7c"], regex_pattern=RX_DEDUP, replace=RX_DEDUP_REPL, **{**RX_OFF, "case_insensitive": True})
n7d = clone(65, TITLE["7d"], regex_pattern=RX_DOTS, replace=RX_DOTS_REPL, **RX_OFF)
n7e = clone(68, TITLE["7e"])
link(n7b, 0, n7c, "string"); link(n7c, 0, n7d, "string"); link(n7d, 0, n7e, "string")
for dst, name in ((45, "prompt"), (46, "positive_prompt_override"), (44, "source")):
    link(n7e, 0, dst, name)

# ---------- primitives, save, prompts, notes ----------
for nid, title, val in ((38, "MainTrigger", None), (83, "Prefix", ""), (84, "Suffix", "good bulge, briefs")):
    N[nid]["title"] = title
    N[nid]["properties"]["Node name for S&R"] = title
    if val is not None:
        set_w(nid, "value", val)
set_w(46, "filename_prefix", FILENAME_PREFIX)
sfw = get_w(61, "value")
assert sfw.count(SFW_ANCHOR) == 1, "SFW rule 7 anchor not found"
set_w(61, "value", sfw.replace(SFW_ANCHOR, SFW_ANCHOR + SFW_KEEP_CLOTHES))
nsfw = get_w(62, "value")
assert "12. **Output Format:**" in nsfw
set_w(62, "value", nsfw.replace("12. **Output Format:**", "11. **Output Format:**"))
N[47]["title"] = "README – Krea2 LoRA T2I v4"
set_w(47, "text", README_V4)
note = clone(47, "Regex – bảng tra", text=REGEX_NOTE)
N[note]["size"] = [560, 760]

KEEP = {"1": 56, "2a": 81, "2b": 57, "2c": 58, "2d": 59, "3a": 60, "3b": 63, "4b": 65, "4c": 66, "4d": 67, "4e": 68,
        "4f": 69, "4g": 70, "4h": 71, "5a": 72, "5b": 73, "5c": 74, "5d": 75, "5e": 76, "6b": 77}
for k, nid in KEEP.items():
    N[nid]["title"] = TITLE[k]
NEW = {"4a": n4a, "6a": n6a, "6c": n6c, "6d": n6d, "6e": n6e, "7a": n7a, "7b": n7b, "7c": n7c, "7d": n7d, "7e": n7e}
ID = {**KEEP, **NEW}

# ---------- layout: 7 colored column groups inside "Prompt Builder", left to right ----------
COLS = [("1. Nguồn", "#3f789e"), ("2. {char}", "#8A8"), ("3. LLM refine", "#a1309b"), ("4. Dọn output LLM", "#b58b2a"),
        ("5. Ép identity LoRA", "#88A"), ("6. Ghép", "#3f789e"), ("7. Random swap", "#b06634")]
pb = next(g for g in w["groups"] if g["title"] == "Prompt Builder")
X0, Y0 = pb["bounding"][0] + 30, pb["bounding"][1] + 50
GAP, PAD, TITLE_H = 70, 20, 40
x, bottom, new_groups = X0, Y0, []
next_gid = max(g.get("id", 0) for g in w["groups"]) + 1
for ci, (gtitle, color) in enumerate(COLS, start=1):
    ids = [ID[k] for k in TITLE if k[0] == str(ci)] + ([note] if ci == 1 else [])
    colw = max(N[i]["size"][0] for i in ids)
    y = Y0 + TITLE_H + PAD
    for i in ids:
        N[i]["pos"] = [x + PAD, y]
        y += N[i]["size"][1] + 60
    new_groups.append({"id": next_gid, "title": gtitle, "bounding": [x, Y0, colw + 2 * PAD, y - Y0], "color": color,
                       "font_size": 22, "flags": {}})
    next_gid += 1
    bottom = max(bottom, y)
    x += colw + 2 * PAD + GAP
pb["bounding"] = [X0 - 30, Y0 - 50, x - GAP - X0 + 60, bottom - Y0 + 100]
w["groups"].extend(new_groups)

# system prompts stay above the group, aligned over column 3
c3 = new_groups[2]["bounding"][0]
N[61]["pos"][0] = c3
N[62]["pos"][0] = c3 + N[61]["size"][0] + 40

# move "Sampler + Output" (group + its nodes) to the right of Prompt Builder
so = next(g for g in w["groups"] if g["title"] == "Sampler + Output")
dx = pb["bounding"][0] + pb["bounding"][2] + 80 - so["bounding"][0]
so["bounding"][0] += dx
for nid in (44, 45, 46):
    N[nid]["pos"][0] += dx

WF_PATH.write_text(json.dumps(w, ensure_ascii=False, indent=2), encoding="utf-8")
print("patched:", WF_PATH, "nodes", len(w["nodes"]), "links", len(w["links"]))
