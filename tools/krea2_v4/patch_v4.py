"""Patch Krea2_LoRA_T2I_v4.json in place into the v4 Prompt Builder (spec 2026-10-29).

Works on the user's hand-edited file and refuses to run twice; to redo: git checkout Krea2_LoRA_T2I_v4.json."""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pipeline_v4 import (CAMERA_RULE, FILENAME_PREFIX, README_V4, REFUSE_EXTRA, REGEX_NOTE, RX_CHATTER,  # noqa: E402
                         RX_DEDUP, RX_DEDUP_REPL, RX_DOTS, RX_DOTS_REPL, RX_HAIR, RX_HAIR_DEDUP, RX_LEAD_CHAR,
                         RX_LEAD_POSS, RX_LEAD_SUBJ, RX_ONE_PARA, RX_SFW_COVERED, RX_SFW_EXPLICIT, RX_SFW_TIDY,
                         RX_THINK, SFW_COVER_TEXT, SFW_RULE7, SFW_RULE7_HEAD, SWAP_FIND, SWAP_ITEMS, TITLE, WF_PATH)

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
set_w(65, "regex_pattern", get_w(65, "regex_pattern") + RX_CHATTER)

# ---------- column 5: one paragraph always, fixed hair rules ----------
n5a = clone(66, TITLE["5a"], regex_pattern=RX_ONE_PARA, replace=" ", **RX_OFF)
link(71, 0, n5a, "string")
link(n5a, 0, 72, "string")
set_w(72, "regex_pattern", RX_HAIR)
set_w(73, "regex_pattern", RX_HAIR_DEDUP)

# ---------- column S: SFW guard, bypassed when nsfw is on (switches are lazy) ----------
nS1 = clone(65, TITLE["S1"], regex_pattern=RX_SFW_EXPLICIT, replace="", **{**RX_OFF, "case_insensitive": True})
nS2 = clone(65, TITLE["S2"], regex_pattern=RX_SFW_TIDY, replace="", **RX_OFF)
nS3 = clone(69, TITLE["S3"], regex_pattern=RX_SFW_COVERED, case_insensitive=True, multiline=False, dotall=False)
nS4 = clone(58, TITLE["S4"], string_a="", string_b=SFW_COVER_TEXT, delimiter=". ")
nS5 = clone(59, TITLE["S5"], switch=False)
nS6 = clone(59, TITLE["S6"], switch=False)
link(76, 0, nS1, "string"); link(nS1, 0, nS2, "string")
link(nS2, 0, nS3, "string"); link(nS2, 0, nS4, "string_a")
link(nS3, 0, nS5, "switch"); link(nS2, 0, nS5, "on_true"); link(nS4, 0, nS5, "on_false")
link(55, 0, nS6, "switch"); link(76, 0, nS6, "on_true"); link(nS5, 0, nS6, "on_false")

# ---------- column 6: leading {char}, then MainTrigger. Prefix. body. Suffix ----------
for nid in (78, 79, 80, 82):
    rm_node(nid)
n6a = clone(65, TITLE["6a"], regex_pattern=RX_LEAD_CHAR, replace="", **RX_OFF)
n6b = clone(65, TITLE["6b"], regex_pattern=RX_LEAD_POSS, replace="His", **RX_OFF)
n6c = clone(65, TITLE["6c"], regex_pattern=RX_LEAD_SUBJ, replace="He ", **RX_OFF)
link(nS6, 0, n6a, "string"); link(n6a, 0, n6b, "string"); link(n6b, 0, n6c, "string")
link(n6c, 0, 77, "string")
n6e, n6f, n6g = (clone(58, TITLE[k], string_a="", string_b="", delimiter=". ") for k in ("6e", "6f", "6g"))
link(38, 0, n6e, "string_a"); link(83, 0, n6e, "string_b")
link(n6e, 0, n6f, "string_a"); link(77, 0, n6f, "string_b")
link(n6f, 0, n6g, "string_a"); link(84, 0, n6g, "string_b")

# ---------- column 7: random clothing token swap + tidy ----------
n7a = add_tony("Select_Random", TITLE["7a"], [], SWAP_ITEMS + [0, "randomize"], [320, 230])
n7b = add_tony("Find_and_Replace", TITLE["7b"],
               [{"name": "text", "type": "STRING", "link": None},
                {"name": "replace_in", "shape": 7, "type": "STRING", "link": None}],
               [SWAP_FIND, "", True], [320, 130])
link(n6g, 0, n7b, "text")
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
lines = sfw.split("\n")
r7 = [k for k, line in enumerate(lines) if line.startswith(SFW_RULE7_HEAD)]
assert len(r7) == 1 and sfw.count("11. **Output Format:**") == 1, "SFW anchors not found"
lines[r7[0]] = SFW_RULE7
sfw = "\n".join(lines)
set_w(61, "value", sfw.replace("11. **Output Format:**", CAMERA_RULE + "12. **Output Format:**"))
nsfw = get_w(62, "value")
assert nsfw.count("12. **Output Format:**") == 1  # rule 11 was missing: the camera rule takes its place
set_w(62, "value", nsfw.replace("12. **Output Format:**", CAMERA_RULE + "12. **Output Format:**"))
N[47]["title"] = "README – Krea2 LoRA T2I v4"
set_w(47, "text", README_V4)
note = clone(47, "Regex – bảng tra", text=REGEX_NOTE)
N[note]["size"] = [560, 760]

KEEP = {"1": 56, "2a": 81, "2b": 57, "2c": 58, "2d": 59, "3a": 60, "3b": 63, "4b": 65, "4c": 66, "4d": 67, "4e": 68,
        "4f": 69, "4g": 70, "4h": 71, "5b": 72, "5c": 73, "5d": 74, "5e": 75, "5f": 76, "6d": 77}
for k, nid in KEEP.items():
    N[nid]["title"] = TITLE[k]
NEW = {"4a": n4a, "5a": n5a, "S1": nS1, "S2": nS2, "S3": nS3, "S4": nS4, "S5": nS5, "S6": nS6,
       "6a": n6a, "6b": n6b, "6c": n6c, "6e": n6e, "6f": n6f, "6g": n6g,
       "7a": n7a, "7b": n7b, "7c": n7c, "7d": n7d, "7e": n7e}
ID = {**KEEP, **NEW}

# ---------- layout: colored column groups inside "Prompt Builder", left to right (key prefix → column) ----------
COLS = [("1", "1. Nguồn", "#3f789e"), ("2", "2. {char}", "#8A8"), ("3", "3. LLM refine", "#a1309b"),
        ("4", "4. Dọn output LLM", "#b58b2a"), ("5", "5. Ép identity LoRA", "#88A"),
        ("S", "S. Chặn SFW (nsfw tắt)", "#a33"), ("6", "6. Ghép", "#3f789e"), ("7", "7. Random swap", "#b06634")]
pb = next(g for g in w["groups"] if g["title"] == "Prompt Builder")
X0, Y0 = pb["bounding"][0] + 30, pb["bounding"][1] + 50
GAP, PAD, TITLE_H = 70, 20, 40
x, bottom, new_groups = X0, Y0, []
next_gid = max(g.get("id", 0) for g in w["groups"]) + 1
for prefix, gtitle, color in COLS:
    ids = [ID[k] for k in TITLE if k[0] == prefix] + ([note] if prefix == "1" else [])
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
