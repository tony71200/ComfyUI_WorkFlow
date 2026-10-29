"""Build the v4 test report tables from passA/passB.

usage: report_v4.py passA.json passB.json OUT.md"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pipeline_v4 import TEST_TXT, WF_PATH, check_final, simulate, split_txt  # noqa: E402

RESULT = "D:/001_Personal_Proj/Comfy/ComfyResult/"


def fallback(wf, raw, r, prefix, suffix):
    """True when the final prompt equals the refine-off result, i.e. 4g fell back to the original prompt."""
    return r["final"] == simulate(wf, raw, prefix, suffix, r["token"])


def checks(r):
    return ", ".join(check_final(r["final"], "Ivan_Ryo.", r["token"])) or "ok"


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    A, B = (json.load(open(p, encoding="utf-8")) for p in sys.argv[1:3])
    wf = json.loads(WF_PATH.read_text(encoding="utf-8"))
    raws = split_txt(TEST_TXT)
    prefix, suffix = A[0]["api"]["83"]["inputs"]["value"], A[0]["api"]["84"]["inputs"]["value"]
    fa = [r["ts_index"] for r in A if fallback(wf, raws[r["ts_index"]], r, prefix, suffix)]
    fb = [r["ts_index"] for r in B if fallback(wf, raws[r["ts_index"]], r, prefix, suffix)]
    L = ["## Kết quả tự động", "",
         f"- Prefix: `{prefix}` · Suffix: `{suffix}`",
         f"- Pass A (SFW, Auto Batch): {len(A)} lượt, lỗi: {sum(r['status'] != 'success' for r in A)}",
         f"- Pass B (NSFW, phát lại): {len(B)} lượt, lỗi: {sum(r['status'] != 'success' for r in B)}",
         f"- Select_Random index pass A: {[r['select_index'] for r in A]} → {dict(Counter(r['token'] for r in A))}",
         f"- Fallback về prompt gốc (4f bắt lỗi): SFW {fa or 'không'}, NSFW {fb or 'không'}", "",
         "| # | token | seed | check SFW | check NSFW | ảnh SFW | ảnh NSFW |", "|---|---|---|---|---|---|---|"]
    img = lambda r: f"[png]({RESULT}{r['images'][0]})" if r["images"] else "—"
    for a, b in zip(A, B):
        L.append(f"| {a['ts_index']} | {a['token']} | {a['seed']} | {checks(a)} | {checks(b)} | {img(a)} | {img(b)} |")
    L += ["", "## Prompt cuối từng lượt", ""]
    for a, b in zip(A, B):
        L += [f"### #{a['ts_index']} — {a['token']}", "", "**SFW:** " + a["final"], "", "**NSFW:** " + b["final"], ""]
    Path(sys.argv[3]).parent.mkdir(parents=True, exist_ok=True)
    Path(sys.argv[3]).write_text("\n".join(L), encoding="utf-8")
    print("wrote", sys.argv[3])
