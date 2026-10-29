"""v4 Prompt Builder: new patterns, node titles, note texts, and an offline copy of the string chain.

Run directly: pattern asserts always; with a patched workflow also simulates every paragraph of the
test .txt (refine off) and asserts the final-prompt invariants from the spec."""
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]            # .../Comfy/workflow
COMFY = ROOT.parent                                   # .../Comfy
WF_PATH = ROOT / "Krea2_LoRA_T2I_v4.json"
TEST_TXT = COMFY / "prompt" / "prompt_20261027_01.txt"
TONY_FR = COMFY / "ComfyUI" / "custom_nodes" / "Load_IO_Tony" / "nodes" / "find_replace_node.py"

RX_THINK = r"^[\s\S]*</think>\s*|</?think>"           # 4a: drop reasoning up to the last </think>, stray tags
# 6a-6c: trigger goes first. A leading {char} that stands alone ("{char}. …", "{char} A 25yo…") is dropped;
# one used as the subject ("{char} lies…", "{char}'s eyes…") becomes He / His so the sentence keeps a subject.
RX_LEAD_CHAR = r"^\s*\{char\}(?:\s*[.,:;]+\s*|\s+(?=[^a-z\s'])|\s*$)"
RX_LEAD_POSS = r"^\s*\{char\}'s\b"
RX_LEAD_SUBJ = r"^\s*\{char\}\s+(?=[a-z])"
RX_ONE_PARA = r"(?:\s*\n\s*)+"                         # 5a: one paragraph, also when refine is off
# 5b: v3 hair rule, but the "lighting word" guard stops at "hair" ("dark hair and light stubble" is hair color).
RX_HAIR = (r"\b(?:long|medium[- ]length|shoulder[- ]length|jet|black|dark|brown|chestnut|blond|blonde|platinum|silver"
           r"|grey|gray|greyish|grayish|white|red|ginger|auburn|brunette|ash)\b[\s/-]*(?=(?:[\w/-]+\s+){0,4}hair\b)"
           r"(?!(?:(?!hair\b)[\w/-]+\s+){0,3}?(?:light|lighting|backlight|rim\w*|glow\w*|highlights?)\b)")
# 5c: v3 "short short" merge, now also across a comma ("short, short hair").
RX_HAIR_DEDUP = r"\bshort[\s,]+(?=(?:[\w/-]+[\s,]+){0,3}?short\s+(?:[\w/-]+\s+){0,3}?hair\b)"
CAMERA_TEXT = ("White balance 5500K, 50mm lens, f/1.8 aperture. Slightly blur the background for portrait shots. "
               "Remove unnecessary details; keep shadows natural and soft.")
CAMERA_RULE = ("11. **Camera Defaults:** If the user's prompt already states camera settings (white balance, lens or "
               "focal length, aperture or f-stop), keep them and add nothing. Otherwise end the paragraph with exactly: "
               f"\"{CAMERA_TEXT}\"\n")
RX_DEDUP = r"\b(\w+_\w+)(?:[\s,]+\1\b)+"               # 7c: "tnga_brief tnga_brief" -> one (tokens with "_" only)
RX_DEDUP_REPL = r"\1"
RX_DOTS = r"(\.)(?:\s*\.)+|[\s,]+$"                    # 7d: ".." / ". ." -> ".", trailing ", " removed
RX_DOTS_REPL = r"\1"
REFUSE_EXTRA = "|You are a prompt rewriter|Follow these rules strictly|Main Character Token"  # 4f: echoed system prompt
SWAP_FIND = "brief|briefs|underwear|towel|pants|sweatpants|shorts|sweatshorts"
SWAP_ITEMS = ["tnga_brief", "lrcontour_brief", "stng_bikini", "hpstr_brief", "dblstrap_bikini"]
SFW_RULE7_HEAD = "7. **Respect the Human Form:**"
# The UNet is an NSFW fine-tune: anything not explicitly covered tends to be exposed, so SFW must state the cover.
SFW_RULE7 = ("7. **Always Keep the Groin Covered:** Treat depictions of people with dignity. In your output every "
             "person's groin and buttocks must be covered, and you must say so in words. If the input mentions nudity or "
             "intimate anatomy (nude, naked, undressed, bare, penis, testicles, genitals, pubic hair, erection, bare "
             "buttocks), delete those words and do one of: (a) dress the person in briefs and write \"wearing briefs that "
             "fully cover the groin\"; or (b) when underwear does not fit the scene, frame the shot so the groin is out "
             "of view (waist-up crop, seen from behind above the waist, or a solid object or thick fabric fully in front "
             "of the hips) and write that the groin is out of frame or fully hidden. If the input never says what covers "
             "the groin, add briefs the same way. Water, foam, steam, shadow and thin draped fabric do not count as "
             "covering. Keep every clothing item the user wrote (e.g. briefs, towel, shorts) with the same word.")
# S1-S6: SFW guard, only when nsfw is off (also when refine is off or fell back): the 4B LLM does not follow
# rule 7 reliably, so explicit words are deleted and a groin-cover sentence is added when none is there.
SFW_ADJ = (r"small|large|big|huge|thick|perfect|flaccid|erect|hard|circumcised|uncircumcised|visible|exposed"
           r"|fully|completely|totally|partially")
RX_SFW_EXPLICIT = (rf"(?:\b(?:including|with)\s+)?(?:\b(?:a|an|his)\s+)?(?:\b(?:{SFW_ADJ})\b[\s,]+)*"
                   r"\b(?:penis(?:es)?|cock|dick|testicles?|scrotum|genitals?|genitalia|pubic hair|pubes|foreskin"
                   r"|erection|nudity|nude|naked|undressed|unclothed|bare (?:buttocks|ass|butt)|buttocks|ass|erotic"
                   r"|male anatomy)\b"
                   r"(?:\s+with\s+(?:visible\s+)?testicles)?")
RX_SFW_TIDY = r"^[\s,;]+|(?<=[:,.;])\s*[,;]|\s+(?=[,.;])|(?<=\s)\s+"
RX_SFW_COVERED = (r"cover(?:s|ed|ing)?\s+(?:the\s+|his\s+)?groin|groin\s+(?:is\s+|stays\s+|remains\s+)?"
                  r"(?:fully\s+|completely\s+)?(?:covered|hidden|concealed|out\s+of\s+(?:the\s+)?frame)")
SFW_COVER_TEXT = "He wears briefs that fully cover the groin."
# 4b addition: trailing chat from the LLM ("Let me know if you want to adjust…") up to the end of the line.
RX_CHATTER = r"|\s*\b(?:let me know|feel free to|hope this helps|would you like)\b[^\n]*"
FILENAME_PREFIX = "Krea2_%date:yyyy_MM_dd%/Krea2_T2I_v4_%MainTrigger.value%_%TextSplitter.index%_%date:yyMMdd%_%Seed.value%"

TITLE = {
    "1": "1. Nguồn: TXT / tay",
    "2a": "2a. Trigger chữ → {char}", "2b": "2b. Có {char}?", "2c": "2c. Thêm {char} vào đầu", "2d": "2d. {char} có sẵn / đã thêm",
    "3a": "3a. System: NSFW / SFW", "3b": "3b. LLM refine (Qwen3-VL-4B)",
    "4a": "4a. Cắt suy luận </think>", "4b": "4b. Bỏ câu dẫn / markdown", "4c": "4c. Gộp 1 đoạn",
    "4d": "4d. Bỏ nhãn 'Final Output:'", "4e": "4e. Trim", "4f": "4f. Qwen từ chối / bình luận?",
    "4g": "4g. Refine lỗi → prompt gốc", "4h": "4h. Prompt: refine / gốc",
    "5a": "5a. Gộp 1 đoạn (luôn chạy)", "5b": "5b. Tóc: màu/độ dài → short", "5c": "5c. Gộp 'short short'",
    "5d": "5d. Bỏ jawline/chin/cheekbones…", "5e": "5e. Dọn dấu phẩy thừa", "5f": "5f. Dọn khoảng trắng",
    "S1": "S1. SFW: xoá chữ khoả thân/bộ phận", "S2": "S2. SFW: dọn dấu", "S3": "S3. SFW: đã có câu che hông?",
    "S4": "S4. SFW: thêm câu che hông", "S5": "S5. SFW: chọn câu che", "S6": "S6. nsfw bật → bỏ qua lớp SFW",
    "6a": "6a. Bỏ {char} đứng riêng đầu thân", "6b": "6b. {char}'s đầu → His", "6c": "6c. {char} chủ ngữ đầu → He",
    "6d": "6d. {char} → trigger", "6e": "6e. MainTrigger + Prefix", "6f": "6f. + thân prompt", "6g": "6g. + Suffix",
    "7a": "7a. Random token quần áo", "7b": "7b. Swap quần áo → token", "7c": "7c. Gộp token lặp",
    "7d": "7d. Dọn dấu chấm / cuối chuỗi", "7e": "7e. Trim",
}

README_V4 = """## Krea-2 Turbo + LoRA — T2I v4

**Model:** homofidelis Krea2 NSFW turbo int8 · qwen3-vl-4b-heretic fp8 (type krea2) · qwen_image_vae. 8 bước, euler/simple, CFG 1.

**Thứ tự prompt cuối:** `MainTrigger` → `Prefix` → prompt đã xử lý → `Suffix` (nối bằng `. `). Rồi mọi từ `brief|briefs|underwear|towel|pants|sweatpants|shorts|sweatshorts` (kể cả trong Suffix) được thay bằng **1** token random từ *7a* (khớp nguyên từ).

**Prompt Builder (trái → phải):** 1 Nguồn · 2 `{char}` · 3 LLM refine · 4 Dọn output LLM · 5 Ép identity LoRA · 6 Ghép · 7 Random swap. Bảng regex: note *Regex – bảng tra*.

**`{char}`:** chữ trigger trong prompt (vd `Ivan_Ryo.`) được đổi thành `{char}`; không có thì tự thêm vào đầu. `{char}` đứng riêng ở đầu (`{char}. …`, `{char} A 25yo…`) bị bỏ vì trigger đã đứng đầu chuỗi; `{char}` làm chủ ngữ đầu câu thành `He` / `His` (`{char} lies…` → `He lies…`); `{char}` giữa câu đổi thành trigger. **MainTrigger không được để trống.**

**Camera mặc định (rule 11 của cả 2 system prompt, chỉ khi refine bật):** prompt chưa có white balance / lens / khẩu độ thì LLM thêm `White balance 5500K, 50mm lens, f/1.8 aperture. Slightly blur the background for portrait shots. Remove unnecessary details; keep shadows natural and soft.`; đã có thì giữ nguyên.

**Toggle:** `use_txt` (bật: .txt, tắt: Prompt tay) · `refine` (Qwen3-VL-4B viết lại; lỗi/từ chối → prompt gốc) · `nsfw` (System prompt NSFW thay SFW, chỉ khi refine bật).

**SFW (rule 7):** LLM phải ghi rõ vùng kín được che — nude/naked → mặc briefs hoặc chọn góc máy giấu hông (waist-up, từ sau lưng, vật che). UNet là bản NSFW nên chỗ nào không ghi "che" thì dễ bị lộ.

**Lớp chặn SFW (cột S, chỉ khi `nsfw` tắt — chạy cả khi refine tắt/lỗi):** S1 xoá chữ khoả thân/bộ phận (nude, naked, penis, testicles, pubic hair, erection, buttocks…, kèm tính từ đi theo); S3–S5 ghép `He wears briefs that fully cover the groin.` nếu prompt chưa có câu che hông (`briefs` sau đó thành token random). Không đụng Trigger/Prefix/Suffix — `good bulge` trong Suffix và LoRA `krea_good_bulge` vẫn đẩy ảnh về phía hở; muốn SFW chắc hơn thì giảm LoRA đó.

**Thinking:** text encoder dùng chung cho Krea2 và LLM — **không** thay bằng bản Qwen3-VL Thinking. Muốn LLM thinking thì cần loader riêng (chưa có), bật `thinking`, `max_length ≥ 2048`. Node *4a* cắt mọi thứ đến `</think>`. Giới hạn: suy luận bị cắt ngang mà không mở bằng `<think>` vẫn có thể lọt vào prompt.

**Negative prompt:** không còn regex bỏ "negative prompt" — khi refine tắt, chữ `Negative prompt: …` trong .txt đi thẳng vào prompt.

**TextSplitter:** đoạn cách nhau 1 dòng trống, phần sau `###` bị bỏ. *Start Auto Batch* chạy hết file; *7a* và *Seed* random lại mỗi lượt.

**Lưu:** `Krea2_<ngày>/Krea2_T2I_v4_<MainTrigger>_<TextSplitter.index>_<yyMMdd>_<Seed>`."""

REGEX_NOTE = """## Regex – bảng tra (R = chỉ khi refine bật, A = luôn chạy)

| Node | Tìm | Thay | Mục đích | |
|---|---|---|---|---|
| 2a | chữ MainTrigger | `{char}` | trigger trong .txt → `{char}` | A |
| 4a | `^[\\s\\S]*</think>\\s*` · `</?think>` | rỗng | cắt suy luận thinking | R |
| 4b | dòng "Here is…:" · `**` · `---` · `#` · gạch đầu dòng | rỗng | câu dẫn / markdown | R |
| 4c | xuống dòng | 1 dấu cách | 1 đoạn | R |
| 4d | nhãn đầu "Final Output:", "Prompt:"… | rỗng | bỏ nhãn | R |
| 4f | rỗng · I'm sorry · I can't · as an AI · chép system prompt… | (đúng/sai) | lỗi → dùng prompt gốc | R |
| 5a | xuống dòng | 1 dấu cách | 1 đoạn (cả khi refine tắt) | A |
| 5b | màu/độ dài trong 4 từ trước `hair` (trừ khi có light/rim/glow trước `hair`) | `short ` | LoRA giữ tóc | A |
| 5c | `short` thừa trước `hair` (kể cả `short, short`) | rỗng | gộp short short | A |
| 5d | sharp/defined/strong… + jawline/chin/cheekbones/nose | rỗng | LoRA giữ mặt | A |
| 5e | ` ,` · `,,` · ` .` | rỗng | dọn dấu phẩy | A |
| 5f | 2+ dấu cách | 1 dấu cách | dọn khoảng trắng | A |
| S1 | nude/naked/penis/testicles/pubic hair/erection/buttocks/erotic (+ tính từ, mạo từ đi trước) | rỗng | chặn SFW | nsfw tắt |
| S2 | `, ,` · ` ;` · khoảng trắng thừa | rỗng | dọn sau S1 | nsfw tắt |
| S3 | "cover(s) the groin" · "groin is covered/hidden/out of frame" | (đúng/sai) | đã có câu che? | nsfw tắt |
| S4–S5 | — | + `He wears briefs that fully cover the groin.` | thêm câu che nếu thiếu | nsfw tắt |
| 6a | `{char}` đứng riêng đầu thân | rỗng | trigger đã đứng đầu | A |
| 6b | `{char}'s` đầu thân | `His` | giữ chủ ngữ | A |
| 6c | `{char}` + chữ thường đầu thân | `He ` | giữ chủ ngữ | A |
| 6d | `{char}` | MainTrigger | `{char}` giữa câu | A |
| 7b | brief/briefs/underwear/towel/pants/sweatpants/shorts/sweatshorts | token 7a | token LoRA quần áo (nguyên từ) | A |
| 7c | token `_` lặp liền nhau | 1 token | gộp lặp | A |
| 7d | `..` · `. .` · dấu thừa cuối | `.` | dọn sau khi ghép | A |

Vì sao không để trong system prompt: refine tắt thì không có LLM; Qwen3-VL-4B không tuân luật đều tay; lỗi định dạng là output của chính model; token LoRA không nên đưa cho LLM. System prompt vẫn giữ các luật này — LLM làm đúng thì regex không làm gì."""


def _load_find_replace():
    spec = importlib.util.spec_from_file_location("tony_find_replace", TONY_FR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._find_replace


find_replace = _load_find_replace()


def split_txt(path):
    """Same split as TonyIO Text_Splitter with defaults (\\n\\n paragraphs, ### negative dropped)."""
    blocks = [b.strip() for b in Path(path).read_text(encoding="utf-8-sig").split("\n\n") if b.strip()]
    return [b.split("###", 1)[0].strip() for b in blocks]


def _named(wf, title):
    return next(n for n in wf["nodes"] if n.get("title") == title)["widgets_values_named"]


def _rx(wf, title, s):
    """Core RegexReplace."""
    v = _named(wf, title)
    flags = (re.I if v["case_insensitive"] else 0) | (re.M if v["multiline"] else 0) | (re.S if v["dotall"] else 0)
    return re.sub(v["regex_pattern"], v["replace"], s, count=v["count"], flags=flags)


def simulate(wf, raw, prefix, suffix, token, refined=None, nsfw=True):
    """Final prompt of the patched workflow. refined=None means refine off; else the raw LLM output."""
    trig = next(n for n in wf["nodes"] if n.get("title") == "MainTrigger")["widgets_values_named"]["value"]
    s = raw.replace(trig, "{char}")                                   # 2a
    if "{char}" not in s:                                             # 2b / 2c / 2d
        s = "{char}. " + s
    body = s
    if refined is not None:
        out = _rx(wf, TITLE["4a"], refined)
        m = _named(wf, TITLE["4f"])
        if not re.search(m["regex_pattern"], out, re.I if m["case_insensitive"] else 0):
            for k in ("4b", "4c", "4d"):
                out = _rx(wf, TITLE[k], out)
            body = out.strip()                                        # 4e
    for k in ("5a", "5b", "5c", "5d", "5e", "5f"):
        body = _rx(wf, TITLE[k], body)
    if not nsfw:                                                      # S1-S6
        body = _rx(wf, TITLE["S2"], _rx(wf, TITLE["S1"], body))
        m = _named(wf, TITLE["S3"])
        if not re.search(m["regex_pattern"], body, re.I if m["case_insensitive"] else 0):
            body = body + ". " + _named(wf, TITLE["S4"])["string_b"]
    for k in ("6a", "6b", "6c"):
        body = _rx(wf, TITLE[k], body)
    body = body.replace("{char}", trig)                               # 6d
    s = ". ".join([trig, prefix, body, suffix])                       # 6e / 6f / 6g
    s = find_replace(s, SWAP_FIND, "", token, whole_word=True)       # 7b
    s = _rx(wf, TITLE["7c"], s)
    return _rx(wf, TITLE["7d"], s).strip()                            # 7d / 7e


def check_final(final, trig, token):
    """Spec invariants for a final prompt; returns a list of failures (empty = ok)."""
    bad = []
    if not final.startswith(trig):
        bad.append("not starting with trigger")
    for needle in ("{char}", "<think>", "</think>", "..", "tnga_tnga", "short, short", "short short", "\n"):
        if needle in final:
            bad.append(f"contains {needle!r}")
    if re.search(RX_DEDUP, final, re.I):
        bad.append("repeated token")
    if re.search(r"(?<!\w)(?:" + SWAP_FIND + r")(?!\w)", final, re.I):
        bad.append("unswapped clothing word")
    if token not in final:
        bad.append("token missing")
    return bad


def check_sfw(final):
    """SFW invariants: no explicit words left, a groin-cover sentence present."""
    bad = [f"explicit {w!r}" for w in re.findall(RX_SFW_EXPLICIT, final, re.I) if w.strip()]
    if not re.search(RX_SFW_COVERED, final, re.I):
        bad.append("no groin cover")
    return bad


def _pattern_asserts():
    sfw = lambda s: re.sub(RX_SFW_TIDY, "", re.sub(RX_SFW_EXPLICIT, "", s, flags=re.I))
    assert sfw("stands nude and barefoot") == "stands and barefoot"
    assert sfw("anatomy including a flaccid, circumcised penis with visible testicles; wearing briefs") == "anatomy; wearing briefs"
    assert sfw("naked, nude, pubic hair, flaccid penis, testicles, bare feet") == "bare feet"
    assert sfw("bare-chested, a soccer ball") == "bare-chested, a soccer ball"
    assert re.search(RX_SFW_COVERED, "tnga_brief that fully cover the groin", re.I)
    assert re.search(RX_SFW_COVERED, "the groin is out of frame", re.I)
    assert not re.search(RX_SFW_COVERED, "white briefs", re.I)
    assert re.sub(RX_THINK, "", "plan...</think>\n\nFinal text <think>") == "Final text "
    assert re.sub(RX_THINK, "", "no reasoning here") == "no reasoning here"
    assert re.sub(RX_LEAD_CHAR, "", "{char}. A man, {char} smiles") == "A man, {char} smiles"
    assert re.sub(RX_LEAD_CHAR, "", "{char} A 25yo man") == "A 25yo man"
    assert re.sub(RX_LEAD_CHAR, "", "{char} lies on a float") == "{char} lies on a float"
    assert re.sub(RX_LEAD_SUBJ, "He ", "{char} lies on a float") == "He lies on a float"
    assert re.sub(RX_LEAD_POSS, "His", "{char}'s eyes are closed") == "His eyes are closed"
    hair = lambda s: re.sub(RX_HAIR_DEDUP, "", re.sub(RX_HAIR, "short ", s, flags=re.I), flags=re.I)
    assert hair("with short, dark brown hair and light stubble.") == "with short hair and light stubble."
    assert hair("He has short, dark hair, reclining") == "He has short hair, reclining"
    assert hair("white rim light on his black hair") == "white rim light on his short hair"
    assert hair("golden light on his hair") == "golden light on his hair"
    assert re.sub(RX_ONE_PARA, " ", "line one\nline two\n\n") == "line one line two "
    assert re.sub(RX_CHATTER[1:], "", "soft shadows. Let me know if you want to adjust it!", flags=re.I) == "soft shadows."
    assert re.sub(RX_DEDUP, RX_DEDUP_REPL, "white tnga_brief tnga_brief, x", flags=re.I) == "white tnga_brief, x"
    assert re.sub(RX_DEDUP, RX_DEDUP_REPL, "very very tall") == "very very tall"
    assert re.sub(RX_DOTS, RX_DOTS_REPL, "Ivan_Ryo.. . body.. . ").strip() == "Ivan_Ryo. body."
    assert re.sub(RX_DOTS, RX_DOTS_REPL, "soft. good bulge, ") == "soft. good bulge"
    assert find_replace("Calvin Klein tnga_brief underwear", SWAP_FIND, "", "stng_bikini") == "Calvin Klein tnga_brief stng_bikini"
    assert find_replace("cotton sweatshorts", SWAP_FIND, "", "X") == "cotton X"
    print("pattern asserts ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    _pattern_asserts()
    wf = json.loads(WF_PATH.read_text(encoding="utf-8"))
    if not any(n.get("title") == TITLE["7e"] for n in wf["nodes"]):
        print("workflow not patched yet — skipped simulation")
        sys.exit(0)
    clothing = re.compile(r"(?<!\w)(?:" + SWAP_FIND + r")(?!\w)", re.I)
    for prefix, suffix in (("an Asian 25yo young man", "good bulge, briefs"), ("", "")):
        for i, raw in enumerate(split_txt(TEST_TXT)):
            token = SWAP_ITEMS[i % len(SWAP_ITEMS)]
            final = simulate(wf, raw, prefix, suffix, token)
            bad = check_final(final, "Ivan_Ryo.", token)
            if not suffix and not clothing.search(raw):  # nothing to swap and no suffix: no token expected
                bad = [b for b in bad if b != "token missing"]
            assert not bad, (i, bad, final[:300])
            print(f"[{i:02d}] {final[:160]}")
    for i, raw in enumerate(split_txt(TEST_TXT)):                    # SFW guard on, refine off / fallback
        token = SWAP_ITEMS[i % len(SWAP_ITEMS)]
        final = simulate(wf, raw, "an Asian 25yo young man", "good bulge, briefs", token, nsfw=False)
        bad = check_final(final, "Ivan_Ryo.", token) + check_sfw(final)
        assert not bad, (i, bad, final[:400])
        print(f"[sfw {i:02d}] …{final[-150:]}")
    fake_llm = ("plan: keep it short</think>\n\nHere is the refined prompt:\n"
                "**{char}** lies on a float in black swim shorts, sharp jawline. Let me know if you want changes!")
    llm = simulate(wf, "{char} on a float", "", "good bulge, briefs", "hpstr_brief", refined=fake_llm)
    print("[llm]", llm)
    assert llm.startswith("Ivan_Ryo. He lies on a float") and "**" not in llm and "plan" not in llm and "jawline" not in llm, llm
    assert llm.endswith("good bulge, hpstr_brief") and "swim hpstr_brief" in llm and "Let me" not in llm, llm
    assert simulate(wf, "{char} sits on a float", "", "", "x", refined="I'm sorry, I can't help.") == "Ivan_Ryo. He sits on a float."
    print("simulation ok")
