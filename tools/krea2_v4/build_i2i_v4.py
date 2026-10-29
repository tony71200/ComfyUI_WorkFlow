"""Build Krea2_LoRA_I2I_v4.json: the I2I v3 frame (models, image sources, Sampler I2I) with the T2I v4 prompt side
(subgraph "Krea2 Prompt Builder v4", column 7 random swap, MainTrigger/Prefix/Suffix, refine/nsfw switches, notes).

Inputs are not modified: I2I v3 = the copy saved in ComfyUI (newest settings), T2I v4 = the repo file."""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pipeline_v4 import COMFY, ROOT, WF_PATH  # noqa: E402

I2I_V3 = COMFY / "ComfyUI" / "user" / "default" / "workflows" / "Krea2_LoRA_I2I_v3.json"
OUT = ROOT / "Krea2_LoRA_I2I_v4.json"
PB_NAME = "Krea2 Prompt Builder v4"
BRIEFS_LORA = "briefs-kreas2-ver2-further-krea-2-base-epoch-07.safetensors"
FILENAME_PREFIX = "Krea2_%date:yyyy_MM_dd%/Krea2_I2I_v4_%date:yyMMdd%_%MainTrigger.value%_%ImageBatch.index%_%Seed.value%"
# T2I v4 root nodes taken over: refine, nsfw, Prefix, Suffix, column 7 (7a-7e), regex note, Prompt Builder instance
T2I_TAKE = [54, 55, 83, 84, 99, 100, 101, 102, 103, 104, 105]

README_I2I = """## Krea-2 Turbo + LoRA — I2I v4

**Model:** krea2_turbo_fp8_scaled · qwen3vl_4b_fp8_scaled (type krea2) · qwen_image_vae. LoRA: Ivan_Ryo 1.15 · briefs-kreas2 1.0 (cho token quần lót random) · sweatySkin / shavedMalePubes tắt. 8 bước, euler/simple, CFG 1.

**Luồng:** Ảnh + prompt (tay / folder) → **Krea2 Prompt Builder v4** (giống T2I v4) → **7 Random swap** → **Krea2 Sampler I2I** → Save A1111.

**⚡ Dùng folder batch?** — 1 toggle đổi nguồn cho cả ảnh lẫn prompt. Bật: *ImageBatch* (folder ảnh + .txt cùng tên, *Start Auto Batch* chạy hết folder). Tắt: *Ảnh tay* + *Prompt tay*.

**Thứ tự prompt cuối:** `MainTrigger` → `Prefix` → prompt đã xử lý → `Suffix` (nối bằng `. `), rồi mọi từ `brief|briefs|underwear|towel|pants|sweatpants|shorts|sweatshorts` (kể cả trong Suffix) thành **1** token random từ *7a*.

**Switcher:** `refine` (Qwen3-VL-4B viết lại; lỗi/từ chối → prompt gốc) · `nsfw` (system prompt NSFW, bỏ qua lớp chặn SFW). Qwen **không** nhìn ảnh — chỉ viết lại chữ của .txt / Prompt tay.

**Krea2 Prompt Builder v4** (double-click để mở): 1 Nguồn · 2 `{char}` · 3 LLM refine (2 system prompt ở trên) · 4 Dọn output LLM · 5 Ép identity LoRA · S Chặn SFW (khi `nsfw` tắt: xoá chữ khoả thân, thêm câu che hông) · 6 Ghép. Bảng regex: note *Regex – bảng tra*.

**Krea2 Sampler I2I:** ảnh → scale theo `megapixels` → VAE Encode → KSampler → Decode. **`denoise`** chỉnh trên node: 0.5 giữ ảnh gốc nhiều, 0.75 vẽ lại nhiều.

**Lưu:** `Krea2_<ngày>/Krea2_I2I_v4_<yyMMdd>_<MainTrigger>_<ImageBatch.index>_<Seed>` — index đếm từ 0."""

sys.stdout.reconfigure(encoding="utf-8")
w = json.loads(I2I_V3.read_text(encoding="utf-8"))
t2i = json.loads(WF_PATH.read_text(encoding="utf-8"))
N = {n["id"]: n for n in w["nodes"]}
T2 = {n["id"]: n for n in t2i["nodes"]}
assert {48, 50, 53}.issubset(N) and N[53]["type"] == "Load_Image_Text_Batch", "unexpected I2I v3 layout"

# every node / link id already used anywhere in I2I v3 (root + subgraphs); transplanted ids are shifted past them
all_nodes = w["nodes"] + [n for sg in w["definitions"]["subgraphs"] for n in sg["nodes"]]
all_links = [l[0] for l in w["links"]] + [l["id"] for sg in w["definitions"]["subgraphs"] for l in sg["links"]]
NOFF, LOFF = max(n["id"] for n in all_nodes), max(all_links)


# ---------- root graph helpers (list-style links) ----------
def new_link_id():
    w["last_link_id"] = max(w["last_link_id"], LOFF) + 1
    return w["last_link_id"]


def drop_link(lid):
    l = next(l for l in w["links"] if l[0] == lid)
    w["links"].remove(l)
    _, s, ss, d, ds, _ = l
    if s in N:
        N[s]["outputs"][ss]["links"].remove(lid)
    if d in N:
        N[d]["inputs"][ds]["link"] = None


def link(src, out, dst, name):
    ss = out if isinstance(out, int) else next(k for k, o in enumerate(N[src]["outputs"]) if o["name"] == out)
    ds = next(k for k, i in enumerate(N[dst]["inputs"]) if i["name"] == name)
    if N[dst]["inputs"][ds]["link"] is not None:
        drop_link(N[dst]["inputs"][ds]["link"])
    lid = new_link_id()
    typ = N[src]["outputs"][ss]["type"]
    w["links"].append([lid, src, ss, dst, ds, typ])
    N[src]["outputs"][ss]["links"] = (N[src]["outputs"][ss]["links"] or []) + [lid]
    N[dst]["inputs"][ds]["link"] = lid


def set_w(nid, name, value):
    named = N[nid].get("widgets_values_named")
    if named is not None:
        N[nid]["widgets_values"][list(named).index(name)] = value
        named[name] = value
    else:
        raise KeyError(name)


# ---------- remove Prompt Builder v3 (instance + definition) ----------
pb3 = N[48]
for l in [l for l in w["links"] if 48 in (l[1], l[3])]:
    drop_link(l[0])
w["nodes"].remove(N.pop(48))
w["definitions"]["subgraphs"] = [sg for sg in w["definitions"]["subgraphs"] if sg["id"] != pb3["type"]]

# ---------- add Prompt Builder v4 definition from T2I v4, ids shifted ----------
pb4 = copy.deepcopy(next(sg for sg in t2i["definitions"]["subgraphs"] if sg["name"] == PB_NAME))
for n in pb4["nodes"]:
    n["id"] += NOFF
    for i in n["inputs"]:
        if i.get("link") is not None:
            i["link"] += LOFF
    for o in n["outputs"]:
        o["links"] = [x + LOFF for x in (o.get("links") or [])]
for l in pb4["links"]:
    l["id"] += LOFF
    for k in ("origin_id", "target_id"):
        if l[k] > 0:
            l[k] += NOFF
for e in pb4["inputs"] + pb4["outputs"]:
    e["linkIds"] = [x + LOFF for x in e["linkIds"]]
w["definitions"]["subgraphs"].append(pb4)

# ---------- take over T2I v4 root nodes (links cleared, wired below) ----------
for old in T2I_TAKE:
    n = copy.deepcopy(T2[old])
    n["id"] = old + NOFF
    for i in n["inputs"]:
        i["link"] = None
    for o in n["outputs"]:
        o["links"] = []
    w["nodes"].append(n)
    N[n["id"]] = n
REFINE, NSFW, PREFIX, SUFFIX, S7A, S7B, S7C, S7D, S7E, NOTE, PB = (old + NOFF for old in T2I_TAKE)
w["last_node_id"] = max(n["id"] for n in w["nodes"] + pb4["nodes"])
w["last_link_id"] = max([l[0] for l in w["links"]] + [l["id"] for l in pb4["links"]] + [LOFF])

# ---------- I2I nodes: MainTrigger, LoRA, save, README ----------
N[45]["title"] = "MainTrigger"
N[45]["properties"]["Node name for S&R"] = "MainTrigger"
set_w(54, "filename_prefix", FILENAME_PREFIX)
N[55]["title"] = "README – Krea2 LoRA I2I v4"
set_w(55, "text", README_I2I)
lora = N[44]
entry = {"on": True, "lora": BRIEFS_LORA, "strength": 1, "strengthTwo": None}
pos = max(k for k, v in enumerate(lora["widgets_values"]) if isinstance(v, dict) and "lora" in v) + 1
lora["widgets_values"].insert(pos, entry)
named = lora["widgets_values_named"]
keys = list(named)
n_lora = sum(k.startswith("lora_") for k in keys)
cut = keys.index(f"lora_{n_lora}") + 1
lora["widgets_values_named"] = {**{k: named[k] for k in keys[:cut]}, f"lora_{n_lora + 1}": entry,
                                **{k: named[k] for k in keys[cut:]}}

# ---------- wiring ----------
for src, out, name in ((42, 0, "clip"), (53, "positive", "prompt_txt"), (47, 0, "prompt_tay"), (51, 0, "use_txt"),
                       (REFINE, 0, "refine"), (NSFW, 0, "nsfw"), (45, 0, "MainTrigger"), (PREFIX, 0, "Prefix"),
                       (SUFFIX, 0, "Suffix")):
    link(src, out, PB, name)
link(PB, "prompt", S7B, "text")
link(S7A, 0, S7B, "replace_in")
link(S7B, 0, S7C, "string"); link(S7C, 0, S7D, "string"); link(S7D, 0, S7E, "string")
for dst, name in ((50, "prompt"), (49, "source"), (54, "positive_prompt_override")):
    link(S7E, 0, dst, name)

# ---------- layout ----------
G = {g["title"]: g for g in w["groups"]}
PAD, GAP, TITLE_H = 20, 70, 40
model = G["Model + LoRA + Trigger + Seed"]
y = max(N[i]["pos"][1] + N[i]["size"][1] for i in (41, 42, 43, 44, 45, 46)) + 60
for nid in (PREFIX, SUFFIX):
    N[nid]["pos"] = [model["bounding"][0] + PAD, y]
    y += N[nid]["size"][1] + 60
model["bounding"][3] = max(model["bounding"][3], y - model["bounding"][1] + 20)

pb_group = G["Prompt Builder"]
x0, y0 = pb_group["bounding"][0] + PAD, pb_group["bounding"][1] + TITLE_H + PAD
N[PB]["pos"] = [x0, y0]
N[NOTE]["pos"] = [x0, y0 + N[PB]["size"][1] + 80]
N[49]["pos"] = [x0, N[NOTE]["pos"][1] + N[NOTE]["size"][1] + 60]   # Preview final prompt stays in this group
left_w = max(N[i]["size"][0] for i in (PB, NOTE, 49))
cx, cy = x0 + left_w + GAP, y0
for nid in (S7A, S7B, S7C, S7D, S7E):
    N[nid]["pos"] = [cx + PAD, cy]
    cy += N[nid]["size"][1] + 60
col7_w = max(N[i]["size"][0] for i in (S7A, S7B, S7C, S7D, S7E)) + 2 * PAD
next_gid = max(g.get("id", 0) for g in w["groups"]) + 1
w["groups"].append({"id": next_gid, "title": "7. Random swap (chỉnh token ở 7a)",
                    "bounding": [cx, y0 - TITLE_H, col7_w, cy - y0 + TITLE_H], "color": "#b06634", "font_size": 22, "flags": {}})
bottom = max(cy, N[49]["pos"][1] + N[49]["size"][1] + 40)
pb_group["bounding"] = [pb_group["bounding"][0], pb_group["bounding"][1],
                        cx + col7_w + PAD - pb_group["bounding"][0], bottom - pb_group["bounding"][1] + 20]

# Switcher above Prompt Builder
sw_x, sw_y = pb_group["bounding"][0], pb_group["bounding"][1] - 260
for k, nid in enumerate((REFINE, NSFW)):
    N[nid]["pos"] = [sw_x + PAD, sw_y + TITLE_H + PAD + k * 100]
w["groups"].append({"id": next_gid + 1, "title": "Switcher", "bounding": [sw_x, sw_y, 320, 240],
                    "color": "#3f789e", "font_size": 22, "flags": {}})

# Sampler + Output to the right
so = G["Sampler + Output"]
dx = pb_group["bounding"][0] + pb_group["bounding"][2] + 80 - so["bounding"][0]
so["bounding"][0] += dx
for nid in (50, 54):
    N[nid]["pos"][0] += dx

for sg in w["definitions"]["subgraphs"]:
    sg["state"]["lastNodeId"], sg["state"]["lastLinkId"] = w["last_node_id"], w["last_link_id"]
OUT.write_text(json.dumps(w, ensure_ascii=False, indent=2), encoding="utf-8")
print("built:", OUT, "root nodes", len(w["nodes"]), "links", len(w["links"]), "PB inner", len(pb4["nodes"]))
