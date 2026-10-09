"""Generate the Krea2 v3 workflows from the v2 ones (reuses loader / LoRA / TextSplitter / Save node configs).

Run from the workflow folder:
    python tools/krea2_v3/build_v3.py Krea2_LoRA_T2I_v2.json Krea2_LoRA_T2I_v3.json t2i
    python tools/krea2_v3/build_v3.py Krea2_LoRA_T2I_v2.json Krea2_LoRA_I2I_v3.json i2i
    python tools/krea2_v3/build_v3.py Krea2_LoRA_T2I_v2.json Krea2_LoRA_T2I_Story4_v3.json story4
    python tools/krea2_v3/check_v3.py Krea2_LoRA_I2I_v3.json
System prompts live in sysprompt_v3.py, cleanup / identity regexes in regex_v3.py (self-check: python regex_v3.py).
"""
import copy, json, os, sys, uuid

SRC, DST = sys.argv[1], sys.argv[2]
MODE = sys.argv[3] if len(sys.argv) > 3 else "t2i"  # t2i | i2i | story4
v2 = json.load(open(SRC, encoding="utf-8"))
V2 = {n["id"]: n for n in v2["nodes"]}
_I2I_SRC = os.path.join(os.path.dirname(SRC) or ".", "Krea2_LoRA_I2I_v2.json")
V2I = {n["id"]: n for n in json.load(open(_I2I_SRC, encoding="utf-8"))["nodes"]}
LORA_DEFAULTS = {"Ivan_Ryo_Krea2": (True, 1.15), "sweatySkin": (True, 0.8), "shavedMalePubes": (False, 0.3)}  # 2026-10-09 tests

# ---------------------------------------------------------------- system prompts
sys.path.insert(0, __import__('os').path.dirname(__file__))
from sysprompt_v3 import SYS_SFW, SYS_NSFW
from regex_v3 import RX_NEG, RX_MD, RX_WS, RX_LEAD, RX_META, RX_REFUSE, RX_HAIR, RX_HAIR_REPL, RX_HAIR_DEDUP, RX_FACE, RX_TIDY, RX_SPACE

README = """## Krea-2 Turbo + LoRA — T2I v3

**Model:** krea2_turbo_fp8_scaled · qwen3vl_4b_fp8_scaled (type krea2) · qwen_image_vae. 8 bước, euler/simple, CFG 1, negative = zero.

**Luồng:** Prompt (tay / .txt) → **Krea2 Prompt Builder** → **Krea2 Sampler T2I** → Save A1111. Double-click subgraph để xem bên trong.

**Nhân vật chính `{char}`:** viết `{char}` trong prompt để chỉ đúng nhân vật dùng LoRA (vd: `{char} sitting next to another man`). Prompt đã ghi sẵn chữ trigger (vd `Ivan_Ryo, an adult man…`) → được coi là `{char}`. Không có cả hai → tự ghép `{char}. ` vào đầu. Cuối cùng `{char}` được thay bằng node **Trigger**; nếu LLM làm rơi trigger thì tự ghép lại vào đầu.

**Toggle trên Prompt Builder:**
- `use_txt` — bật: đọc TextSplitter (.txt), tắt: dùng *Prompt tay*.
- `refine` — viết lại prompt bằng Qwen3-VL-4B (TextGenerate, thinking off, max_length 1024). Output được dọn (bỏ câu dẫn, markdown, "negative prompt"). Nếu Qwen từ chối, trả về rỗng hoặc chỉ bình luận → tự quay về prompt gốc. Tắt: dùng prompt gốc.
- `nsfw` — chọn *System prompt NSFW* thay vì *SFW* (chỉ có tác dụng khi `refine` bật).

**System prompt:** 2 node *System prompt SFW / NSFW* nằm **trong** subgraph Prompt Builder (double-click để mở và sửa). Rule 9–10: giữ `{char}`, không tả màu/độ dài tóc và cấu trúc mặt của nhân vật chính (LoRA lo phần đó). Thêm lớp regex cố định (chạy cả khi tắt refine): màu/độ dài tóc → `short hair` (giữ trạng thái: wet, messy…), xoá `sharp jawline / pointed chin / high cheekbones…`. Lưu ý: áp cho mọi người trong prompt.

**TextSplitter:** đoạn cách nhau 1 dòng trống. Phần negative sau `###` bị bỏ qua (Krea2 CFG 1). Bấm *Start Auto Batch* để chạy hết file.

**Seed:** node *Seed* (randomize / fixed / increment / decrement).

**Lưu:** `Krea2_<ngày>/Krea2_T2I_v3_<yyMMdd>_<Trigger>_<TextSplitter.index>_<Seed>` — index đếm từ 0. Metadata A1111: final prompt + LoRA + hash."""

README_STORY4 = """## Krea-2 Turbo + LoRA — Story4 v3 (Qwen viết tiếp câu chuyện)

**Model:** krea2_turbo_fp8_scaled · qwen3vl_4b_fp8_scaled (type krea2) · qwen_image_vae. 8 bước, euler/simple, CFG 1, negative = zero.

**Bạn nhập:** *Character sheet* (trang phục + bối cảnh + ánh sáng — ghép vào MỌI ảnh, sau trigger), *Beat 1 – anchor* (cảnh mở đầu), *Hướng câu chuyện* (tuỳ chọn, để trống = Qwen tự nối tiếp).

**Luồng:** Prompt 1 = `trigger. sheet. beat 1` → Sampler #1 → ảnh 1 → **Krea2 Story Writer** (Qwen3-VL-4B nhìn ảnh 1 + đọc sheet/beat 1/hướng → JSON `scene2–4`) → `trigger. sheet. cảnh N` → Sampler #2–4.

**Toggle trên Story Writer:** `use_qwen` (tắt = dùng 3 ô *Beat 2–4 gõ tay* trong subgraph, như Story4 cũ) · `see_image` (Qwen nhìn ảnh 1; tắt = chạy song song, nhanh hơn) · `nsfw` (chọn system prompt Story NSFW).

**Dự phòng:** Qwen từ chối / rỗng / chép system prompt → cả 3 cảnh dùng ô gõ tay. JSON hỏng / thiếu cảnh → riêng cảnh đó dùng ô gõ tay. Cảnh Qwen viết được dọn (negative prompt, câu bình luận) + regex tóc/mặt; sheet và beat 1 giữ nguyên.

**Seed:** *Seed1* = anchor (fixed — ưng rồi giữ), *Seed2–4* randomize → chạy lại tới khi ưng rồi đổi sang fixed.

**Preview:** 3 node *Preview prompt 2–4* để xem Qwen viết gì.

**Lưu:** `Krea2_<ngày>/Story4_v3_<yyMMdd>_<N>_<Trigger>_<SeedN>`."""

README_I2I = """## Krea-2 Turbo + LoRA — I2I v3

**Model:** krea2_turbo_fp8_scaled · qwen3vl_4b_fp8_scaled (type krea2) · qwen_image_vae. 8 bước, euler/simple, CFG 1, negative = zero.

**Luồng:** Ảnh + prompt (tay / folder) → **Krea2 Prompt Builder** (giống T2I v3) → **Krea2 Sampler I2I** → Save A1111. Double-click subgraph để xem bên trong.

**⚡ Dùng folder batch?** — 1 toggle đổi nguồn cho cả ảnh lẫn prompt. Bật: *ImageBatch* (folder ảnh + .txt cùng tên, bấm *Start Auto Batch* để chạy hết folder). Tắt: *Ảnh tay* + *Prompt tay*.

**Krea2 Sampler I2I:** ảnh → scale theo `megapixels` → VAE Encode → KSampler → Decode. Chỉnh **`denoise`** ngay trên node: 0.5 giữ ảnh gốc nhiều, 0.75 vẽ lại nhiều (mặc định 0.6).

**Prompt Builder:** `{char}` = nhân vật chính (chữ trigger có sẵn trong .txt cũng được coi là `{char}`; không có thì tự ghép trigger vào đầu), `refine` (Qwen3-VL-4B) + `nsfw` chọn system prompt (nằm trong subgraph), dọn output, Qwen từ chối/rỗng → quay về prompt gốc, regex tóc/mặt cho LoRA lo identity.

**LoRA mặc định (theo test 2026-10-09):** Ivan_Ryo 1.15 · sweatySkin 0.8 · shavedMalePubes tắt.

**Lưu:** `Krea2_<ngày>/Krea2_I2I_v3_<yyMMdd>_<Trigger>_<ImageBatch.index>_<Seed>` — index đếm từ 0."""

# ---------------------------------------------------------------- id counters
_nid, _lid = [0], [0]
def nid():
    _nid[0] += 1; return _nid[0]
def lid():
    _lid[0] += 1; return _lid[0]

CORE = {"cnr_id": "comfy-core", "ver": "0.39.0"}

def I(name, typ, widget=False, shape=None, label=None):
    d = {"localized_name": name.split(".")[-1], "name": name, "type": typ}
    if shape is not None: d["shape"] = shape
    if widget: d["widget"] = {"name": name}
    if label: d["label"] = label
    d["link"] = None
    return d

def O(name, typ):
    return {"localized_name": name, "name": name, "type": typ, "links": []}

def node(typ, pos, size, inputs, outputs, wv, title=None, sr=None, props=None, **extra):
    n = {"id": nid(), "type": typ, "pos": pos, "size": size, "flags": {}, "order": 0, "mode": 0,
         "inputs": inputs, "outputs": outputs,
         "properties": props or dict(CORE, **{"Node name for S&R": sr or typ})}
    if title: n["title"] = title
    if wv is not None: n["widgets_values"] = wv
    n.update(extra)
    return n

def reuse(v2_id, pos, title=None, sr=None, wv=None, src=None):
    n = copy.deepcopy((src or V2)[v2_id]); n["id"] = nid(); n["pos"] = pos
    n.pop("widgets_values_named", None)
    for i in n["inputs"]: i["link"] = None
    for o in n["outputs"]: o["links"] = []
    if title: n["title"] = title
    if sr: n["properties"]["Node name for S&R"] = sr
    if wv is not None: n["widgets_values"] = wv
    return n

def slot(n, name, outputs=False):
    lst = n["outputs" if outputs else "inputs"]
    return next(i for i, s in enumerate(lst) if s["name"] == name)

class Graph:
    """Collects nodes + links; links are stored list-style (root) or dict-style (subgraph)."""
    def __init__(self, sub=False):
        self.nodes, self.links, self.sub = [], [], sub
        self.sg_in, self.sg_out = [], []
    def add(self, *ns):
        self.nodes += ns; return ns[0] if len(ns) == 1 else ns
    def link(self, a, a_out, b, b_in, typ):
        l = lid()
        ao = a_out if isinstance(a_out, int) else slot(a, a_out, True)
        bi = b_in if isinstance(b_in, int) else slot(b, b_in)
        a["outputs"][ao]["links"].append(l)
        b["inputs"][bi]["link"] = l
        self._push(l, a["id"], ao, b["id"], bi, typ)
        return l
    def _push(self, l, o, os_, t, ts, typ):
        if self.sub:
            self.links.append({"id": l, "origin_id": o, "origin_slot": os_, "target_id": t, "target_slot": ts, "type": typ})
        else:
            self.links.append([l, o, os_, t, ts, typ])
    # subgraph boundary
    def sg_input(self, name, typ, targets, label=None):
        """targets: list of (node, input_name). Returns slot index."""
        idx = len(self.sg_in)
        ids = []
        for n, inp in targets:
            l = lid(); bi = slot(n, inp); n["inputs"][bi]["link"] = l
            self._push(l, -10, idx, n["id"], bi, typ); ids.append(l)
        widget = any("widget" in n["inputs"][slot(n, inp)] for n, inp in targets)
        e = {"id": str(uuid.uuid4()), "name": name, "type": typ, "linkIds": ids,
             "localized_name": name, "pos": [0, 0]}
        if label: e["label"] = label
        self.sg_in.append(e)
        return widget
    def sg_output(self, name, typ, src, src_out):
        idx = len(self.sg_out); l = lid(); so = src_out if isinstance(src_out, int) else slot(src, src_out, True)
        src["outputs"][so]["links"].append(l)
        self._push(l, src["id"], so, -20, idx, typ)
        self.sg_out.append({"id": str(uuid.uuid4()), "name": name, "type": typ, "linkIds": [l],
                            "localized_name": name, "pos": [0, 0]})

def switch(pos, title, typ="STRING"):
    return node("ComfySwitchNode", pos, [320, 78],
                [I("on_false", typ, shape=7), I("on_true", typ, shape=7), I("switch", "BOOLEAN", True)],
                [O("output", typ)], [False], title)

def concat(pos, title, a="", b="", delim=""):
    return node("StringConcatenate", pos, [320, 160],
                [I("string_a", "STRING", True), I("string_b", "STRING", True), I("delimiter", "STRING", True)],
                [O("STRING", "STRING")], [a, b, delim], title)

def contains(pos, title, sub=""):
    return node("StringContains", pos, [320, 130],
                [I("string", "STRING", True), I("substring", "STRING", True), I("case_sensitive", "BOOLEAN", True)],
                [O("contains", "BOOLEAN")], ["", sub, True], title)

def prim_bool(pos, title, v):
    return node("PrimitiveBoolean", pos, [280, 58], [I("value", "BOOLEAN", True)], [O("BOOLEAN", "BOOLEAN")], [v], title)

def finish_subgraph(g, name, in_x, out_x, y=0):
    for k, e in enumerate(g.sg_in): e["pos"] = [in_x + 140, y + 24 + 20 * k]
    for k, e in enumerate(g.sg_out): e["pos"] = [out_x + 24, y + 24 + 20 * k]
    return {"id": str(uuid.uuid4()), "version": 1,
            "state": {"lastGroupId": 0, "lastNodeId": _nid[0], "lastLinkId": _lid[0], "lastRerouteId": 0},
            "revision": 0, "config": {}, "name": name,
            "inputNode": {"id": -10, "bounding": [in_x, y, 160, 40 + 20 * len(g.sg_in)]},
            "outputNode": {"id": -20, "bounding": [out_x, y, 140, 40 + 20 * len(g.sg_out)]},
            "inputs": g.sg_in, "outputs": g.sg_out, "widgets": [], "nodes": g.nodes, "groups": [],
            "links": g.links, "extra": {}}

# ================================================================ subgraph 1: Krea2 Prompt Builder
pb = Graph(sub=True)
b_txt = pb.add(prim_bool([0, 0], "use_txt (bật = .txt, tắt = tay)", True))
b_ref = pb.add(prim_bool([0, 100], "refine (LLM)", False))
b_nsfw = pb.add(prim_bool([0, 200], "nsfw", False))
sw_src = pb.add(switch([400, 0], "1. Nguồn: TXT / tay"))
has_char = pb.add(contains([400, 120], "2a. Có {char}?", "{char}"))
add_char = pb.add(concat([400, 290], "2b. Thêm {char} vào đầu", "{char}", "", ". "))
sw_char = pb.add(switch([400, 490], "2c. {char} có sẵn / đã thêm"))
# prompt already names the trigger (e.g. .txt says "Ivan_Ryo, an adult man") -> treat it as {char}, no double prefix.
# Empty trigger would make str.replace insert {char} between every character, so skip then.
trig_empty = pb.add(node("StringCompare", [0, 400], [320, 130],
                         [I("string_a", "STRING", True), I("string_b", "STRING", True), I("mode", "COMBO", True),
                          I("case_sensitive", "BOOLEAN", True)],
                         [O("BOOLEAN", "BOOLEAN")], ["", "", "Equal", True], "1b. Trigger trống?"))
norm = pb.add(node("StringReplace", [0, 560], [320, 160],
                   [I("string", "STRING", True), I("find", "STRING", True), I("replace", "STRING", True)],
                   [O("STRING", "STRING")], ["", "", "{char}"], "1c. Trigger có sẵn → {char}"))
sw_norm = pb.add(switch([0, 760], "1d. Trigger trống → giữ nguyên"))
pb.link(sw_src, 0, norm, "string", "STRING")
pb.link(norm, 0, sw_norm, "on_false", "STRING")
pb.link(sw_src, 0, sw_norm, "on_true", "STRING")
pb.link(trig_empty, 0, sw_norm, "switch", "BOOLEAN")
sw_sys = pb.add(switch([800, 0], "3a. System: NSFW / SFW"))
sys_sfw = pb.add(node("PrimitiveStringMultiline", [800, -1420], [520, 640], [I("value", "STRING", True)],
                      [O("STRING", "STRING")], [SYS_SFW], "System prompt SFW"))
sys_nsfw = pb.add(node("PrimitiveStringMultiline", [1360, -1420], [520, 640], [I("value", "STRING", True)],
                       [O("STRING", "STRING")], [SYS_NSFW], "System prompt NSFW"))
pb.link(sys_sfw, 0, sw_sys, "on_false", "STRING")
pb.link(sys_nsfw, 0, sw_sys, "on_true", "STRING")
tg = reuse(13, [800, 120], "3b. LLM refine (Qwen3-VL-4B)",
           wv=["", 1024, "on", 0.7, 64, 0.95, 0.05, 1.05, 0, 0, False, True, "auto"])
pb.add(tg)
def rx_replace(pos, title, rx, repl=""):
    p, ci, ml, da = rx
    return node("RegexReplace", pos, [320, 200],
                [I("string", "STRING", True), I("regex_pattern", "STRING", True), I("replace", "STRING", True),
                 I("case_insensitive", "BOOLEAN", True, 7), I("multiline", "BOOLEAN", True, 7),
                 I("dotall", "BOOLEAN", True, 7), I("count", "INT", True, 7)],
                [O("STRING", "STRING")], ["", p, repl, ci, ml, da, 0], title)
rx_neg = pb.add(rx_replace([1260, 0], "3c. Bỏ 'negative prompt…'", RX_NEG))
rx_md = pb.add(rx_replace([1260, 240], "3d. Bỏ câu dẫn / markdown", RX_MD))
rx_ws = pb.add(rx_replace([1260, 480], "3e. Gộp 1 đoạn", RX_WS, " "))
rx_lead = pb.add(rx_replace([1660, 480], "3e2. Bỏ nhãn 'Final Output:'", RX_LEAD))
rx_meta = pb.add(rx_replace([2060, 1200], "3e3. Bỏ câu bình luận (LoRA / your prompt…)", RX_META))
trim = pb.add(node("StringTrim", [1260, 720], [320, 82], [I("string", "STRING", True), I("mode", "COMBO", True)],
                   [O("STRING", "STRING")], ["", "Both"], "3f. Trim"))
refused = pb.add(node("RegexMatch", [1260, 840], [320, 180],
                      [I("string", "STRING", True), I("regex_pattern", "STRING", True), I("case_insensitive", "BOOLEAN", True),
                       I("multiline", "BOOLEAN", True), I("dotall", "BOOLEAN", True)],
                      [O("matches", "BOOLEAN")], ["", RX_REFUSE[0], True, False, False], "3g. Qwen từ chối / bình luận?"))
sw_fb = pb.add(switch([1660, 0], "3h. Refine lỗi → prompt gốc"))
sw_ref = pb.add(switch([1660, 120], "3i. Prompt: refine / gốc"))
rx_hair = pb.add(rx_replace([1660, 720], "3j. Tóc: màu/độ dài → short", RX_HAIR, RX_HAIR_REPL))
rx_hair2 = pb.add(rx_replace([2060, 960], "3j2. Gộp 'short short'", RX_HAIR_DEDUP))
rx_face = pb.add(rx_replace([1660, 960], "3k. Bỏ jawline/chin/cheekbones…", RX_FACE))
rx_tidy = pb.add(rx_replace([1660, 1200], "3l. Dọn dấu phẩy thừa", RX_TIDY))
rx_space = pb.add(rx_replace([1660, 1440], "3m. Dọn khoảng trắng", RX_SPACE, " "))
rep = pb.add(node("StringReplace", [2060, 120], [320, 160],
                  [I("string", "STRING", True), I("find", "STRING", True), I("replace", "STRING", True)],
                  [O("STRING", "STRING")], ["", "{char}", ""], "4. {char} → trigger"))
has_trig = pb.add(contains([2060, 330], "5a. Có trigger?"))
add_trig = pb.add(concat([2060, 500], "5b. Ghép trigger vào đầu", "", "", ". "))
sw_safe = pb.add(switch([2060, 700], "5c. Chốt an toàn"))

pb.link(sw_norm, 0, has_char, "string", "STRING")
pb.link(sw_norm, 0, add_char, "string_b", "STRING")
pb.link(sw_norm, 0, sw_char, "on_true", "STRING")
pb.link(add_char, 0, sw_char, "on_false", "STRING")
pb.link(has_char, 0, sw_char, "switch", "BOOLEAN")
pb.link(b_txt, 0, sw_src, "switch", "BOOLEAN")
pb.link(b_nsfw, 0, sw_sys, "switch", "BOOLEAN")
pb.link(sw_sys, 0, tg, "system_prompt", "STRING")
pb.link(sw_char, 0, tg, "prompt", "STRING")
pb.link(sw_char, 0, sw_ref, "on_false", "STRING")
pb.link(tg, 0, rx_neg, "string", "STRING")
pb.link(rx_neg, 0, rx_md, "string", "STRING")
pb.link(rx_md, 0, rx_ws, "string", "STRING")
pb.link(rx_ws, 0, rx_lead, "string", "STRING")
pb.link(rx_lead, 0, rx_meta, "string", "STRING")
pb.link(rx_meta, 0, trim, "string", "STRING")
pb.link(tg, 0, refused, "string", "STRING")
pb.link(trim, 0, sw_fb, "on_false", "STRING")
pb.link(sw_char, 0, sw_fb, "on_true", "STRING")
pb.link(refused, 0, sw_fb, "switch", "BOOLEAN")
pb.link(sw_fb, 0, sw_ref, "on_true", "STRING")
pb.link(b_ref, 0, sw_ref, "switch", "BOOLEAN")
pb.link(sw_ref, 0, rx_hair, "string", "STRING")
pb.link(rx_hair, 0, rx_hair2, "string", "STRING")
pb.link(rx_hair2, 0, rx_face, "string", "STRING")
pb.link(rx_face, 0, rx_tidy, "string", "STRING")
pb.link(rx_tidy, 0, rx_space, "string", "STRING")
pb.link(rx_space, 0, rep, "string", "STRING")
pb.link(rep, 0, has_trig, "string", "STRING")
pb.link(rep, 0, add_trig, "string_b", "STRING")
pb.link(rep, 0, sw_safe, "on_true", "STRING")
pb.link(add_trig, 0, sw_safe, "on_false", "STRING")
pb.link(has_trig, 0, sw_safe, "switch", "BOOLEAN")

PB_IN = [  # name, type, targets, label, instance default (None = plain socket)
    ("clip", "CLIP", [(tg, "clip")], None, None),
    ("manual_prompt", "STRING", [(sw_src, "on_false")], None, None),
    ("txt_prompt", "STRING", [(sw_src, "on_true")], None, None),
    ("trigger", "STRING", [(rep, "replace"), (has_trig, "substring"), (add_trig, "string_a"),
                           (norm, "find"), (trig_empty, "string_a")], None, ""),
    ("use_txt", "BOOLEAN", [(b_txt, "value")], None, True),
    ("refine", "BOOLEAN", [(b_ref, "value")], None, False),
    ("nsfw", "BOOLEAN", [(b_nsfw, "value")], None, False),
    ("max_length", "INT", [(tg, "max_length")], None, 1024),
    ("temperature", "FLOAT", [(tg, "sampling_mode.temperature")], None, 0.7),
]
for name, typ, tgts, label, _ in PB_IN:
    pb.sg_input(name, typ, tgts, label)
pb.sg_output("final_prompt", "STRING", sw_safe, 0)
SG_PB = finish_subgraph(pb, "Krea2 Prompt Builder", -400, 1700)

# ================================================================ subgraph 2: sampler (T2I or I2I)
sp = Graph(sub=True)
enc = reuse(19, [0, 160], "CLIP Encode", wv=[""])
neg = reuse(20, [0, 340], "Negative = zero (Krea2 CFG 1)")
dec = reuse(39, [880, 0])
if MODE in ("t2i", "story4"):
    lat = reuse(18, [0, 0], "Empty latent", wv=[1024, 1024, 1])
    ks = reuse(21, [440, 0], "KSampler (CFG 1)", sr="KSampler", wv=[0, "fixed", 8, 1, "euler", "simple", 1])
    sp.add(lat, enc, neg, ks, dec)
    sp.link(lat, 0, ks, "latent_image", "LATENT")
    SP_IN = [
        ("model", "MODEL", [(ks, "model")], None),
        ("clip", "CLIP", [(enc, "clip")], None),
        ("vae", "VAE", [(dec, "vae")], None),
        ("prompt", "STRING", [(enc, "text")], ""),
        ("width", "INT", [(lat, "width")], 1024),
        ("height", "INT", [(lat, "height")], 1024),
        ("seed", "INT", [(ks, "seed")], 0),
        ("steps", "INT", [(ks, "steps")], 8),
        ("sampler_name", "COMBO", [(ks, "sampler_name")], "euler"),
        ("scheduler", "COMBO", [(ks, "scheduler")], "simple"),
    ]
    SP_NAME = "Krea2 Sampler T2I"
else:
    b_batch = prim_bool([-400, 0], "use_batch (bật = folder, tắt = ảnh tay)", True)
    sw_img = switch([0, -420], "1. Ảnh: batch / tay", "IMAGE")
    scale = reuse(19, [0, -300], "2. Scale ảnh (megapixels)", wv=["lanczos", 1, 16], src=V2I)
    venc = reuse(21, [0, -120], "3. VAE Encode ảnh gốc", src=V2I)
    ks = reuse(21, [440, 0], "4. KSampler I2I (CFG 1, denoise)", sr="KSampler",
               wv=[0, "fixed", 8, 1, "euler", "simple", 0.6])
    sp.add(b_batch, sw_img, scale, venc, enc, neg, ks, dec)
    sp.link(b_batch, 0, sw_img, "switch", "BOOLEAN")
    sp.link(sw_img, 0, scale, "image", "IMAGE")
    sp.link(scale, 0, venc, "pixels", "IMAGE")
    sp.link(venc, 0, ks, "latent_image", "LATENT")
    SP_IN = [
        ("model", "MODEL", [(ks, "model")], None),
        ("clip", "CLIP", [(enc, "clip")], None),
        ("vae", "VAE", [(venc, "vae"), (dec, "vae")], None),
        ("prompt", "STRING", [(enc, "text")], ""),
        ("image_manual", "IMAGE", [(sw_img, "on_false")], None),
        ("image_batch", "IMAGE", [(sw_img, "on_true")], None),
        ("use_batch", "BOOLEAN", [(b_batch, "value")], True),
        ("seed", "INT", [(ks, "seed")], 0),
        ("denoise", "FLOAT", [(ks, "denoise")], 0.6),
        ("megapixels", "FLOAT", [(scale, "megapixels")], 1.0),
        ("steps", "INT", [(ks, "steps")], 8),
        ("sampler_name", "COMBO", [(ks, "sampler_name")], "euler"),
        ("scheduler", "COMBO", [(ks, "scheduler")], "simple"),
    ]
    SP_NAME = "Krea2 Sampler I2I"
sp.link(enc, 0, neg, "conditioning", "CONDITIONING")
sp.link(enc, 0, ks, "positive", "CONDITIONING")
sp.link(neg, 0, ks, "negative", "CONDITIONING")
sp.link(ks, 0, dec, "samples", "LATENT")
for name, typ, tgts, _ in SP_IN:
    sp.sg_input(name, typ, tgts)
sp.sg_output("IMAGE", "IMAGE", dec, 0)
SG_SP = finish_subgraph(sp, SP_NAME, -800, 1200)

# ================================================================ root graph
g = Graph()

def instance(sg, spec, pos, size, title):
    ins, wv = [], []
    for name, typ, *_rest in spec:
        default = _rest[-1]
        d = {"name": name, "type": typ, "link": None}
        if default is not None:
            d["widget"] = {"name": name}; wv.append(default)
        ins.append(d)
    outs = [{"localized_name": o["name"], "name": o["name"], "type": o["type"], "links": []} for o in sg["outputs"]]
    return node(sg["id"], pos, size, ins, outs, wv, title, props=dict(CORE))

def grp(i, title, x, y, w, h, color):
    return {"id": i, "title": title, "bounding": [x, y, w, h], "color": color, "font_size": 24, "flags": {}}

unet = g.add(reuse(1, [0, 60]))
clip = g.add(reuse(2, [0, 200]))
vae = g.add(reuse(3, [0, 360]))
lora = g.add(reuse(4, [0, 560], "Power Lora Loader"))
for w in lora["widgets_values"]:
    k = isinstance(w, dict) and next((k for k in LORA_DEFAULTS if str(w.get("lora", "")).startswith(k)), None)
    if k:
        w["on"], w["strength"] = LORA_DEFAULTS[k]
trig = g.add(reuse(5, [0, 840], "Trigger", sr="Trigger"))

if MODE == "story4":
    from sysprompt_v3 import SYS_STORY_SFW, SYS_STORY_NSFW
    V2S = {n["id"]: n for n in json.load(open(os.path.join(os.path.dirname(SRC) or ".", "Krea2_LoRA_T2I_Story4.json"),
                                              encoding="utf-8"))["nodes"]}

    def multiline(pos, title, text, size=(420, 200)):
        return node("PrimitiveStringMultiline", pos, list(size), [I("value", "STRING", True)],
                    [O("STRING", "STRING")], [text], title)

    def regex_match(pos, title, pattern):
        return node("RegexMatch", pos, [320, 180],
                    [I("string", "STRING", True), I("regex_pattern", "STRING", True), I("case_insensitive", "BOOLEAN", True),
                     I("multiline", "BOOLEAN", True), I("dotall", "BOOLEAN", True)],
                    [O("matches", "BOOLEAN")], ["", pattern, True, False, False], title)

    # ------------------------------------------------ subgraph: Krea2 Story Writer
    sw = Graph(sub=True)
    b_qwen = sw.add(prim_bool([0, 0], "use_qwen (bật = Qwen viết cảnh 2–4)", True))
    b_img = sw.add(prim_bool([0, 100], "see_image (Qwen nhìn ảnh 1)", True))
    b_ns = sw.add(prim_bool([0, 200], "nsfw", False))
    sys_s = sw.add(multiline([0, -1500], "System prompt Story SFW", SYS_STORY_SFW, (520, 640)))
    sys_n = sw.add(multiline([560, -1500], "System prompt Story NSFW", SYS_STORY_NSFW, (520, 640)))
    sw_sys = sw.add(switch([400, 0], "2a. System: NSFW / SFW"))
    sw_img = sw.add(switch([400, 120], "2b. Nhìn ảnh 1? (tắt = không chờ ảnh)", "IMAGE"))
    m1 = sw.add(concat([0, 320], "1a. CHARACTER SHEET", "CHARACTER SHEET:\n", "", ""))
    m2 = sw.add(concat([0, 520], "1b. + nhãn SCENE 1", "", "SCENE 1:\n", "\n\n"))
    m3 = sw.add(concat([0, 720], "1c. + scene 1", "", "", ""))
    m4 = sw.add(concat([0, 920], "1d. + nhãn STORY DIRECTION", "", "STORY DIRECTION:\n", "\n\n"))
    m5 = sw.add(concat([0, 1120], "1e. + direction", "", "", ""))
    tg = sw.add(reuse(13, [400, 300], "2c. Qwen3-VL-4B viết cảnh 2–4 (JSON)",
                      wv=["", 1024, "on", 0.7, 64, 0.95, 0.05, 1.05, 0, 0, False, True, "auto"]))
    refused_s = sw.add(regex_match([400, 800], "2d. Qwen từ chối / rỗng / chép system?", RX_REFUSE[0]))
    ts = sw.add(concat([2800, 0], "7a. trigger + sheet", "", "", ". "))
    for a, b in ((m1, m2), (m2, m3), (m3, m4), (m4, m5)):
        sw.link(a, 0, b, "string_a", "STRING")
    sw.link(m5, 0, tg, "prompt", "STRING")
    sw.link(sys_s, 0, sw_sys, "on_false", "STRING")
    sw.link(sys_n, 0, sw_sys, "on_true", "STRING")
    sw.link(b_ns, 0, sw_sys, "switch", "BOOLEAN")
    sw.link(sw_sys, 0, tg, "system_prompt", "STRING")
    sw.link(b_img, 0, sw_img, "switch", "BOOLEAN")
    sw.link(sw_img, 0, tg, "image", "IMAGE")
    sw.link(tg, 0, refused_s, "string", "STRING")

    scene_out = {}
    for k, v2s_id in ((2, 17), (3, 23), (4, 29)):
        x, y = 800, (k - 2) * 1700
        manual = sw.add(reuse(v2s_id, [x, y], f"Beat {k} gõ tay (dự phòng)", src=V2S))
        jx = sw.add(node("JsonExtractString", [x + 440, y], [320, 100],
                         [I("json_string", "STRING", True), I("key", "STRING", True)],
                         [O("STRING", "STRING")], ["", f"scene{k}"], f"3. scene{k} từ JSON"))
        chain = [rx_replace([x + 440, y + 140], f"4a. scene{k}: bỏ 'negative prompt'", RX_NEG),
                 rx_replace([x + 440, y + 380], f"4b. scene{k}: bỏ câu bình luận", RX_META),
                 rx_replace([x + 840, y], f"5a. scene{k}: tóc → short", RX_HAIR, RX_HAIR_REPL),
                 rx_replace([x + 840, y + 240], f"5b. scene{k}: gộp 'short short'", RX_HAIR_DEDUP),
                 rx_replace([x + 840, y + 480], f"5c. scene{k}: bỏ jawline/chin…", RX_FACE),
                 rx_replace([x + 840, y + 720], f"5d. scene{k}: dọn dấu phẩy", RX_TIDY),
                 rx_replace([x + 840, y + 960], f"5e. scene{k}: dọn khoảng trắng", RX_SPACE, " ")]
        trim_k = node("StringTrim", [x + 1240, y], [320, 82], [I("string", "STRING", True), I("mode", "COMBO", True)],
                      [O("STRING", "STRING")], ["", "Both"], f"5f. scene{k}: trim")
        empty_k = regex_match([x + 1240, y + 120], f"6a. scene{k} rỗng?", r"^\s*$")
        s_empty = switch([x + 1640, y], f"6b. scene{k}: rỗng → gõ tay")
        s_ref = switch([x + 1640, y + 120], f"6c. scene{k}: Qwen lỗi → gõ tay")
        s_use = switch([x + 1640, y + 240], f"6d. scene{k}: use_qwen / gõ tay")
        p_k = concat([x + 2000, y], f"7b. prompt {k} = trigger. sheet. scene{k}", "", "", ". ")
        sw.add(jx, *chain, trim_k, empty_k, s_empty, s_ref, s_use, p_k)
        sw.link(tg, 0, jx, "json_string", "STRING")
        prev = jx
        for r in chain + [trim_k]:
            sw.link(prev, 0, r, "string", "STRING")
            prev = r
        sw.link(trim_k, 0, empty_k, "string", "STRING")
        sw.link(trim_k, 0, s_empty, "on_false", "STRING")
        sw.link(manual, 0, s_empty, "on_true", "STRING")
        sw.link(empty_k, 0, s_empty, "switch", "BOOLEAN")
        sw.link(s_empty, 0, s_ref, "on_false", "STRING")
        sw.link(manual, 0, s_ref, "on_true", "STRING")
        sw.link(refused_s, 0, s_ref, "switch", "BOOLEAN")
        sw.link(s_ref, 0, s_use, "on_true", "STRING")
        sw.link(manual, 0, s_use, "on_false", "STRING")
        sw.link(b_qwen, 0, s_use, "switch", "BOOLEAN")
        sw.link(ts, 0, p_k, "string_a", "STRING")
        sw.link(s_use, 0, p_k, "string_b", "STRING")
        scene_out[k] = p_k

    SW_IN = [
        ("clip", "CLIP", [(tg, "clip")], None),
        ("image1", "IMAGE", [(sw_img, "on_true")], None),
        ("trigger", "STRING", [(ts, "string_a")], ""),
        ("sheet", "STRING", [(m1, "string_b"), (ts, "string_b")], ""),
        ("beat1", "STRING", [(m3, "string_b")], ""),
        ("direction", "STRING", [(m5, "string_b")], ""),
        ("use_qwen", "BOOLEAN", [(b_qwen, "value")], True),
        ("see_image", "BOOLEAN", [(b_img, "value")], True),
        ("nsfw", "BOOLEAN", [(b_ns, "value")], False),
        ("max_length", "INT", [(tg, "max_length")], 1024),
        ("temperature", "FLOAT", [(tg, "sampling_mode.temperature")], 0.7),
    ]
    for name, typ, tgts, _ in SW_IN:
        sw.sg_input(name, typ, tgts)
    for k, p_k in scene_out.items():
        sw.sg_output(f"prompt{k}", "STRING", p_k, 0)
    SG_SW = finish_subgraph(sw, "Krea2 Story Writer", -800, 4800)

    # ------------------------------------------------ root graph (story4)
    size = g.add(reuse(17, [0, 960], "Kích thước"))
    seeds = {k: g.add(node("PrimitiveInt", [0, 1100 + (k - 1) * 120], [420, 82], [I("value", "INT", True)],
                           [O("INT", "INT")], [20261008 + k, "fixed" if k == 1 else "randomize"],
                           f"Seed{k}", sr=f"Seed{k}")) for k in (1, 2, 3, 4)}
    sheet = g.add(reuse(6, [500, 60], "Character sheet (ghép vào MỌI ảnh)", src=V2S))
    beat1 = g.add(reuse(10, [500, 420], "Beat 1 – anchor", src=V2S))
    direction = g.add(multiline([500, 700], "Hướng câu chuyện (để trống = Qwen tự nối tiếp)", ""))
    p_ts = g.add(concat([1000, 60], "trigger + sheet", "", "", ". "))
    p1 = g.add(concat([1000, 280], "Prompt 1 = trigger. sheet. beat 1", "", "", ". "))
    inst_sw = g.add(instance(SG_SW, SW_IN, [1000, 560], [420, 480], "Krea2 Story Writer"))
    samplers, saves = {}, {}
    for k in (1, 2, 3, 4):
        x, y = 1500 + (k - 1) * 460, 60
        samplers[k] = g.add(instance(SG_SP, SP_IN, [x, y], [420, 420], f"Krea2 Sampler T2I #{k}"))
        saves[k] = g.add(reuse(40, [x, y + 480], f"Save {k}", wv=[
            f"Krea2_%date:yyyy_MM_dd%/Story4_v3_%date:yyMMdd%_{k}_%Trigger.value%_%Seed{k}.value%", "", "", "", True, False]))
    previews = {k: g.add(reuse(16, [1000 + (k - 2) * 460, 1100], f"Preview prompt {k}")) for k in (2, 3, 4)}
    g.add(node("MarkdownNote", [-560, 60], [520, 900], [], [], [README_STORY4], "README – Krea2 LoRA T2I Story4 v3", props={}))

    g.link(unet, 0, lora, "model", "MODEL")
    g.link(trig, 0, p_ts, "string_a", "STRING")
    g.link(sheet, 0, p_ts, "string_b", "STRING")
    g.link(p_ts, 0, p1, "string_a", "STRING")
    g.link(beat1, 0, p1, "string_b", "STRING")
    g.link(clip, 0, inst_sw, "clip", "CLIP")
    g.link(trig, 0, inst_sw, "trigger", "STRING")
    g.link(sheet, 0, inst_sw, "sheet", "STRING")
    g.link(beat1, 0, inst_sw, "beat1", "STRING")
    g.link(direction, 0, inst_sw, "direction", "STRING")
    g.link(samplers[1], 0, inst_sw, "image1", "IMAGE")
    for k in (1, 2, 3, 4):
        s = samplers[k]
        g.link(lora, 0, s, "model", "MODEL")
        g.link(clip, 0, s, "clip", "CLIP")
        g.link(vae, 0, s, "vae", "VAE")
        g.link(size, "width", s, "width", "INT")
        g.link(size, "height", s, "height", "INT")
        g.link(seeds[k], 0, s, "seed", "INT")
        src_prompt, src_out = (p1, 0) if k == 1 else (inst_sw, f"prompt{k}")
        g.link(src_prompt, src_out, s, "prompt", "STRING")
        g.link(src_prompt, src_out, saves[k], "positive_prompt_override", "STRING")
        g.link(s, 0, saves[k], "images", "IMAGE")
        if k > 1:
            g.link(inst_sw, f"prompt{k}", previews[k], "source", "STRING")

    out = {
        "id": str(uuid.uuid4()), "revision": 0, "last_node_id": _nid[0], "last_link_id": _lid[0],
        "nodes": g.nodes, "links": g.links,
        "groups": [grp(1, "Model + LoRA + Trigger + Size + Seed", -20, 0, 460, 1620, "#3f789e"),
                   grp(2, "Sheet + Beat 1 + Hướng câu chuyện", 480, 0, 460, 960, "#a1309b"),
                   grp(3, "Prompt 1 + Story Writer", 980, 0, 460, 1060, "#b06634"),
                   grp(4, "Sampler + Save (4 cảnh)", 1480, 0, 1840, 1020, "#88A")],
        "definitions": {"subgraphs": [SG_SP, SG_SW]},
        "config": {}, "extra": {"ds": {"scale": 0.45, "offset": [700, 100]}, "frontendVersion": "1.53.10"},
        "version": 0.4,
    }
    json.dump(out, open(DST, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("ok", DST, "nodes", len(g.nodes), "links", _lid[0])
    sys.exit(0)
seed = g.add(node("PrimitiveInt", [0, 960], [420, 82], [I("value", "INT", True)], [O("INT", "INT")],
                  [630833735766694, "randomize"], "Seed", sr="Seed"))
manual = g.add(reuse(6, [500, 60], "Prompt tay",
                     wv=["photorealistic photo of {char}, a young handsome East Asian man, cinematic light"]))
inst_pb = g.add(instance(SG_PB, PB_IN, [1000, 60], [420, 420], "Krea2 Prompt Builder"))
preview = g.add(reuse(16, [1000, 560], "Preview final prompt"))
inst_sp = g.add(instance(SG_SP, SP_IN, [1500, 60], [420, 460], SP_NAME))

if MODE == "t2i":
    size = g.add(reuse(17, [0, 1100], "Kích thước"))
    src_txt = g.add(reuse(9, [500, 300], "TextSplitter", sr="TextSplitter"))
    g.link(src_txt, "positive_prompt", inst_pb, "txt_prompt", "STRING")
    g.link(size, "width", inst_sp, "width", "INT")
    g.link(size, "height", inst_sp, "height", "INT")
    fname = "Krea2_%date:yyyy_MM_dd%/Krea2_T2I_v3_%date:yyMMdd%_%Trigger.value%_%TextSplitter.index%_%Seed.value%"
    readme, note_title = README, "README – Krea2 LoRA T2I v3"
    groups = [grp(1, "Model + LoRA + Trigger + Seed", -20, 0, 460, 1260, "#3f789e"),
              grp(2, "Prompt nguồn (tay / .txt)", 480, 0, 460, 1180, "#a1309b")]
else:
    toggle = g.add(node("PrimitiveBoolean", [500, 60], [420, 58], [I("value", "BOOLEAN", True)],
                        [O("BOOLEAN", "BOOLEAN")], [True],
                        "⚡ Dùng folder batch? (bật = ảnh + .txt cùng tên, tắt = Ảnh tay + Prompt tay)"))
    manual["pos"] = [500, 180]
    img_manual = g.add(reuse(9, [500, 400], "Ảnh tay", src=V2I))
    batch = g.add(reuse(10, [500, 900], "ImageBatch", sr="ImageBatch", src=V2I))
    g.link(toggle, 0, inst_pb, "use_txt", "BOOLEAN")
    g.link(toggle, 0, inst_sp, "use_batch", "BOOLEAN")
    g.link(batch, "positive", inst_pb, "txt_prompt", "STRING")
    g.link(img_manual, "image", inst_sp, "image_manual", "IMAGE")
    g.link(batch, "image", inst_sp, "image_batch", "IMAGE")
    fname = "Krea2_%date:yyyy_MM_dd%/Krea2_I2I_v3_%date:yyMMdd%_%Trigger.value%_%ImageBatch.index%_%Seed.value%"
    readme, note_title = README_I2I, "README – Krea2 LoRA I2I v3"
    groups = [grp(1, "Model + LoRA + Trigger + Seed", -20, 0, 460, 1120, "#3f789e"),
              grp(2, "Ảnh + prompt nguồn (tay / folder)", 480, 0, 460, 1500, "#a1309b")]

save = g.add(reuse(40, [1500, 600], "Save (A1111 metadata)", wv=[fname, "", "", "", True, False]))
note = g.add(node("MarkdownNote", [-560, 60], [520, 900], [], [], [readme], note_title, props={}))

g.link(unet, 0, lora, "model", "MODEL")
g.link(lora, 0, inst_sp, "model", "MODEL")
g.link(clip, 0, inst_pb, "clip", "CLIP")
g.link(clip, 0, inst_sp, "clip", "CLIP")
g.link(vae, 0, inst_sp, "vae", "VAE")
g.link(manual, 0, inst_pb, "manual_prompt", "STRING")
g.link(trig, 0, inst_pb, "trigger", "STRING")
g.link(inst_pb, 0, inst_sp, "prompt", "STRING")
g.link(inst_pb, 0, preview, "source", "STRING")
g.link(inst_pb, 0, save, "positive_prompt_override", "STRING")
g.link(seed, 0, inst_sp, "seed", "INT")
g.link(inst_sp, 0, save, "images", "IMAGE")

out = {
    "id": str(uuid.uuid4()), "revision": 0, "last_node_id": _nid[0], "last_link_id": _lid[0],
    "nodes": g.nodes, "links": g.links,
    "groups": groups + [grp(4, "Prompt Builder", 980, 0, 460, 800, "#b06634"),
                        grp(5, "Sampler + Output", 1480, 0, 460, 1100, "#88A")],
    "definitions": {"subgraphs": [SG_PB, SG_SP]},
    "config": {}, "extra": {"ds": {"scale": 0.5, "offset": [700, 100]}, "frontendVersion": "1.53.10"},
    "version": 0.4,
}
json.dump(out, open(DST, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("ok", DST, "nodes", len(g.nodes), "links", _lid[0])
