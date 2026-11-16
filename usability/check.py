#!/usr/bin/env python3
"""Check cold-start runs from the Agora audit log + transcript (not the agent's claims).

  python check.py runs/round1
Prints per-run calls, outcome vs tasks.json, and writes <round>/summary.json.
"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASKS = {t["id"]: t for t in json.load(open(HERE / "tasks.json"))["tasks"]}


def tool_calls(transcript: Path):
    calls, results = [], {}
    for line in transcript.read_text().splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        msg = e.get("message") or {}
        for c in msg.get("content") or [] if isinstance(msg.get("content"), list) else []:
            if c.get("type") == "tool_use":
                calls.append({"id": c["id"], "name": c["name"].replace("mcp__agora__", ""), "input": c["input"]})
            elif c.get("type") == "tool_result":
                content = c.get("content")
                text = content if isinstance(content, str) else " ".join(
                    x.get("text", "") for x in content or [] if isinstance(x, dict))
                results[c["tool_use_id"]] = {"is_error": bool(c.get("is_error")), "text": text}
    for c in calls:
        c["result"] = results.get(c["id"], {})
    return calls


def check_run(d: Path):
    res = json.load(open(d / "result.json"))
    task = TASKS[res["task"]]
    log = [json.loads(l) for l in open(d / "agora_log.jsonl")] if (d / "agora_log.jsonl").exists() else []
    acc = [e for e in log if e["event"] == "offer_accepted"]
    intents = [e["intent"] for e in log if e["event"] == "intent_received"]
    calls = tool_calls(d / "transcript.jsonl")
    accepted = acc[0]["receipt"] if acc else None
    want = task["check"]
    ok = (accepted is None) if want["accept_seller"] is None else bool(
        accepted and accepted["seller_id"] == want["accept_seller"]
        and accepted["product"]["size"] == want.get("accept_size", accepted["product"]["size"]))
    return {
        "run": d.name, "task": res["task"], "model": res["model"],
        "outcome_ok": ok,
        "accepted": None if not accepted else {k: accepted[k] for k in ("seller_id", "all_in_price", "review_status")}
                    | {"size": accepted["product"]["size"], "category_sku": accepted["product"]["sku"]},
        "intents_posted": [{k: i[k] for k in ("category", "size", "max_total_price", "priorities")} for i in intents],
        "tool_calls": [f"{c['name']}({json.dumps(c['input'])[:110]}){' -> ERROR' if c['result'].get('is_error') else ''}"
                       for c in calls],
        "errors": [c["result"].get("text", "")[:200] for c in calls if c["result"].get("is_error")],
        "n_calls": len(calls), "cost_usd": res["cost_usd"], "wall_s": res["wall_s"],
        "final_message": res["final_message"],
    }


if __name__ == "__main__":
    rnd = HERE / sys.argv[1]
    rows = [check_run(d) for d in sorted(rnd.iterdir()) if (d / "result.json").exists()]
    json.dump(rows, open(rnd / "summary.json", "w"), indent=1)
    for r in rows:
        print(f"\n== {r['run']}  outcome={'OK' if r['outcome_ok'] else 'FAIL'}  accepted={r['accepted']}  "
              f"calls={r['n_calls']} ${r['cost_usd']:.3f} {r['wall_s']}s")
        for c in r["tool_calls"]:
            print("   ", c)
        for e in r["errors"]:
            print("    error:", e)
    print(f"\n{sum(r['outcome_ok'] for r in rows)}/{len(rows)} runs met the pre-set check")
