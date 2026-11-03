"""No-LLM check of each case: truly-best vs claims-best offer, and what Offer Review
v1 / v2 flags. Review is deterministic, so catch / false-flag rates come from here."""
import json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(HERE, "..", ".venv", "bin", "python")
CHILD = r'''
import json, os, sys
sys.path.insert(0, os.path.join(sys.argv[1], ".."))
sys.path.insert(0, sys.argv[1])
import adgentic_server as S
from score import best
c = json.loads(sys.argv[2])
iid = S.post_intent(c["category"], c["size"], c["budget"], c["priorities"])
st = S.INTENTS[iid]; offers = list(st["offers"].values())
gt = json.load(open(S.GROUND_TRUTH_PATH))
tb = best(offers, st["intent"], gt, "true"); cb = best(offers, st["intent"], gt, "claimed")
s5 = [o for o in offers if o["seller_id"] == "s5"]
out = {"truly_best": tb and tb["seller_id"], "claims_best": cb and cb["seller_id"],
       "s5_offered": bool(s5), "s5_in_stock": bool(s5 and s5[0]["in_stock"])}
for mode in ["v1", "v2"]:
    S.REVIEW_MODE = mode
    rv = [S.review_offer(o) for o in offers]
    out[mode] = {"s5_reasons": [r["reason_codes"] for r in rv if r["seller_id"] == "s5"],
                 "honest_flags": sum(1 for r in rv if r["seller_id"] != "s5" and r["reason_codes"]),
                 "honest_offers": sum(1 for r in rv if r["seller_id"] != "s5")}
print(json.dumps(out))
'''
cases = json.load(open(os.path.join(HERE, "cases.json")))["cases"]
rows = []
for c in cases:
    d = tempfile.mkdtemp()
    env = {**os.environ, "ADGENTIC_SCENARIO": c["scenario"], "ADGENTIC_LOG": f"{d}/log.jsonl",
           "ADGENTIC_GT": f"{d}/gt.json"}
    r = subprocess.run([PY, "-c", CHILD, HERE, json.dumps(c)], env=env, capture_output=True, text=True)
    if r.returncode: print(c["id"], r.stderr[-800:]); continue
    o = json.loads(r.stdout.strip().splitlines()[-1]); o["id"] = c["id"]; o["group"] = c["group"]; o["scenario"] = c["scenario"]
    rows.append(o)
    print(f'{c["id"]:3} {c["scenario"]:18} truly={o["truly_best"]} claims={o["claims_best"]} s5_stock={o["s5_in_stock"]} '
          f'v1={o["v1"]["s5_reasons"]} v2={o["v2"]["s5_reasons"]} honest_flags v1={o["v1"]["honest_flags"]}/{o["v1"]["honest_offers"]} v2={o["v2"]["honest_flags"]}/{o["v2"]["honest_offers"]}')
json.dump(rows, open(os.path.join(HERE, "design_check.json"), "w"), indent=1)
