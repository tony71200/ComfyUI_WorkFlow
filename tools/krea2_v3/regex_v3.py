"""Regexes used by the Prompt Builder cleanup nodes (RegexReplace / RegexMatch). Run directly to self-check on results.json."""
import re

# (pattern, case_insensitive, multiline, dotall) — mirrors the RegexReplace node flags
RX_NEG = (r"[\s,;.]*\bnegative prompts?\b.*$", True, False, True)  # drop "negative prompt: ..." to the end
RX_MD = (r"^\s*(?:\*\*)?\s*(?:here|sure|okay|below|final prompt|refined prompt|expanded prompt|this is)[^\n]*:\s*(?:\*\*)?\s*$"
         r"|\*\*|^\s*(?:-{3,}|#+\s*|[-*•]\s+)", True, True, False)  # preamble line, bold, rules, headings, bullets
RX_WS = (r"(?:\s*\n\s*)+", False, False, False)  # one paragraph
RX_LEAD = (r"^\s*(?:(?:final|refined|expanded|improved|polished)\s+(?:output|answer|prompt|version)|prompt|answer|output|user|assistant)\b\s*:?\s*",
           True, False, False)  # leading label left on the same line as the prompt
RX_META = (r"[^.;]*\b(?:LoRA|your (?:prompt|request|input|constraints))\b[^.;]*[.;]?\s*", True, False, False)  # "…respecting your LoRA constraints."
# Q24(b): LoRA owns identity. (A) every color/length word within 4 words before "hair" -> "short",
# (B) drop a "short" when another "short" follows in the same hair phrase. State words (wet, messy…) survive.
# ponytail: no notion of which person — also hits a secondary character's hair; per-person would need the LLM.
HAIR_WORDS = (r"long|medium[- ]length|shoulder[- ]length|jet|black|dark|brown|chestnut|blond|blonde|platinum|silver"
              r"|grey|gray|greyish|grayish|white|red|ginger|auburn|brunette|ash")
RX_HAIR = (rf"\b(?:{HAIR_WORDS})\b[\s/-]*(?=(?:[\w/-]+\s+){{0,4}}hair\b)"
           rf"(?!(?:[\w/-]+\s+){{0,3}}?(?:light|lighting|backlight|rim\w*|glow\w*|highlights?)\b)", True, False, False)
RX_HAIR_REPL = "short "
RX_HAIR_DEDUP = (r"\bshort\s+(?=(?:[\w/-]+\s+){0,3}?short\s+(?:[\w/-]+\s+){0,3}?hair\b)", True, False, False)
RX_FACE = (r"\b(?:sharp|defined|well-defined|strong|chiseled|chiselled|angular|square|pointed|high|prominent|sculpted|refined"
           r"|narrow|v-shaped|straight|small|button|aquiline)\s+(?:jaw\s*line|jaw|chin|cheekbones?|nose|face shape)\b"
           r"|\balmond[- ]shaped eyes\b", True, False, False)
RX_TIDY = (r"(?<=[:,.;])\s*,|\s+(?=[,.;])", False, False, False)  # " ," and ",," / ":," left by deletions
RX_SPACE = (r"[ \t]{2,}", False, False, False)

RX_REFUSE =(r"^\s*$|I'?m sorry|I am sorry|I can'?t|I cannot|must decline|unable to (?:help|assist|fulfill|comply)|against my (?:guidelines|policies)|prompt you'?ve provided|your prompt is already|as an AI"
             r"|You are a prompt rewriter|Follow these rules strictly|Main Character Token",  # echoed system prompt
             True, False, False)

def sub(rx, s, repl=""):
    p, i, m, d = rx
    return re.sub(p, repl, s, flags=(re.I if i else 0) | (re.M if m else 0) | (re.S if d else 0))

def clean(s):
    return sub(RX_META, sub(RX_LEAD, sub(RX_WS, sub(RX_MD, sub(RX_NEG, s)), " "))).strip()

def identity(s):
    return sub(RX_SPACE, sub(RX_TIDY, sub(RX_FACE, sub(RX_HAIR_DEDUP, sub(RX_HAIR, s, RX_HAIR_REPL)))), " ")

def refused(s):
    p, i, m, d = RX_REFUSE
    return re.search(p, s, re.I) is not None

if __name__ == "__main__":
    # python regex_v3.py [results.json]  — optional: a list of {"tag", "text"} raw Qwen outputs to spot-check
    import json, sys
    for r in json.load(open(sys.argv[1], encoding="utf-8")) if len(sys.argv) > 1 else []:
        c = clean(r["text"])
        assert "**" not in c and "\n" not in c and "negative prompt" not in c.lower(), r["tag"]
        print(f'{r["tag"]:8} refused={refused(r["text"])!s:5} | {c[:110]}')
    assert clean("**Final Prompt:**\n\n---\n\n{char}, a man. Negative prompt: blur") == "{char}, a man"
    assert refused("I'm sorry, but I can't fulfill that request.") and refused("The prompt you've provided is already detailed")
    for s_, want in [("Final Output: Ultra HD photo", "Ultra HD photo"), ("Final Answer\nIvan_Ryo, a man", "Ivan_Ryo, a man"),
                     ("user\n{char}. High-fashion", "{char}. High-fashion"), ("Prompt details matter", "details matter")]:
        assert clean(s_) == want, (s_, clean(s_))
    assert refused("") and refused("  \n") and not refused("{char}, a man")
    assert refused("You are a prompt rewriter for text-to-image models. You only rewrite text")
    assert clean("{char} by a wall, soft light. Shot on 35mm — while respecting your LoRA constraints for {char}.") \
        == "{char} by a wall, soft light."
    for s_, want in [
        ("short dark greyish brown textured hair with bangs", "short textured hair with bangs"),
        ("Dark naturally messy/tousled hair", "short naturally messy/tousled hair"),
        ("Messy, naturally tousled black medium-length hair", "Messy, naturally tousled short hair"),
        ("His dark hair is slightly tousled", "His short hair is slightly tousled"),
        ("fine body hair, black pants, hair light", "fine body hair, black pants, hair light"),
        ("Expression: Sharp jawline, calm eyes", "Expression: calm eyes"),
        ("high cheekbones and a defined jawline", " and a "),
        ("Chin slightly lowered", "Chin slightly lowered"),
        ("short thick straight black hair with soft side part", "thick straight short hair with soft side part"),
        ("wet dark hair", "wet short hair"),
        ("cool-white/blue backlight rimming hair", "cool-white/blue backlight rimming hair"),
        ("black running shorts, short sleeves", "black running shorts, short sleeves"),
        ("a faint rim light to separate hair from the wall", "a faint rim light to separate hair from the wall"),
    ]:
        assert identity(s_) == want, (s_, identity(s_))
    print("ok")
