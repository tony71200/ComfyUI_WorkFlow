"""Structural self-check for the generated workflow: link bookkeeping, types, filename %refs%."""
import json, re, sys

d = json.load(open(sys.argv[1], encoding="utf-8"))
KEYS = ["id", "origin_id", "origin_slot", "target_id", "target_slot", "type"]

def check(nodes, links, sub=None):
    N = {n["id"]: n for n in nodes}
    L = [l if isinstance(l, dict) else dict(zip(KEYS, l)) for l in links]
    for l in L:
        if l["origin_id"] == -10:
            assert l["id"] in sub["inputs"][l["origin_slot"]]["linkIds"], l
        else:
            assert l["id"] in N[l["origin_id"]]["outputs"][l["origin_slot"]]["links"], ("out missing", l)
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
    return len(L)

print("root links", check(d["nodes"], d["links"]))
for sg in d["definitions"]["subgraphs"]:
    print(sg["name"], "links", check(sg["nodes"], sg["links"], sg), [i["name"] for i in sg["inputs"]])
    for inst in (n for n in d["nodes"] if n["type"] == sg["id"]):
        assert [i["name"] for i in inst["inputs"]] == [i["name"] for i in sg["inputs"]], "instance inputs != subgraph inputs"
        assert len(inst["widgets_values"]) == sum("widget" in i for i in inst["inputs"]), "widgets_values length"

srs = {n["properties"].get("Node name for S&R") for n in d["nodes"]}
PREFIX_SLOT = {"SaveImageA1Metadata": 0, "Save_Txt": 3}  # index of filename_prefix in widgets_values
for save in (n for n in d["nodes"] if n["type"] in PREFIX_SLOT):
    fp = save["widgets_values"][PREFIX_SLOT[save["type"]]]
    for ref in re.findall(r"%([A-Za-z0-9_]+)\.", fp):
        assert ref in srs, ref
    print("filename refs ok:", fp)
