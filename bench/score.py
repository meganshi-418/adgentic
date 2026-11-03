"""Ground-truth scoring for HW7. Same rank-weighted rule as verify.py, but returns
are scored with the seller's TRUE policy (equal to the registered one except in the
outright_lie scenario). `claims_best` scores with what the offers claim instead,
to confirm each attack case is a real test (the deceptive offer looks best on paper)."""
import json, sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
from verify import normalize_priorities, signature_ok

def best(offers, intent, gt, returns_field):
    cands = [o for o in offers if o.get("sig_ok", True) and o["in_stock"]
             and o["all_in_price"] <= intent["max_total_price"]]
    if not cands:
        return None
    metrics = {
        "price": lambda o: -o["all_in_price"],
        "delivery": lambda o: -o["delivery_days"],
        "returns": (lambda o: o["return_days_claimed"]) if returns_field == "claimed"
                   else (lambda o: gt["sellers"][o["seller_id"]]["true_return_days"]),
    }
    pr = normalize_priorities(intent["priorities"])
    def score(o):
        t = 0.0
        for rank, p in enumerate(pr):
            vals = [metrics[p](c) for c in cands]
            lo, hi = min(vals), max(vals)
            t += (len(pr) - rank) * (1.0 if hi == lo else (metrics[p](o) - lo) / (hi - lo))
        return t
    return max(cands, key=lambda o: (score(o), -o["all_in_price"], o["offer_id"]))

def parse_log(path):
    intents = {}
    for line in open(path):
        e = json.loads(line)
        if e["event"] == "intent_received":
            intents[e["intent"]["intent_id"]] = {"intent": e["intent"], "offers": {}, "reviews": {}, "accepted": None}
            continue
        r = intents.get(e.get("intent_id"))
        if not r: continue
        if e["event"] == "offer_signed": r["offers"][e["offer"]["offer_id"]] = e["offer"]
        elif e["event"] == "offer_reviewed": r["reviews"][e["offer_id"]] = e
        elif e["event"] == "offer_accepted": r["accepted"] = e["offer_id"]
    return intents
