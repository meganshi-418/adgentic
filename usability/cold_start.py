#!/usr/bin/env python3
"""Cold-start runs: a fresh Claude Code session per run, given only the Agora guide,
the agora MCP tools and the owner's request. Records the full transcript
(stream-json: every tool call and result) and the Agora audit log, then checks the
outcome against tasks.json.

  python cold_start.py --tasks T1,T2 --repeats 3 --out runs/round1 [--guide ../docs/AGENT_GUIDE.md]
"""
import argparse, concurrent.futures as cf, json, shutil, subprocess, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
PY = str(REPO / ".venv" / "bin" / "python")
TOOLS = "Read,mcp__agora__post_intent,mcp__agora__get_offers,mcp__agora__accept_offer,mcp__agora__explain_intent"

PROMPT = """You are a shopping agent acting for your owner. You can use Agora, an exchange for agent shopping, through the connected `agora` MCP tools. Its documentation is in ./AGORA_GUIDE.md.

Your owner's request: "{request}"

Handle this on your owner's behalf and buy something if that is the right call. Your owner is not available to answer questions during this task. Finish with a short message to your owner saying what you did and why."""


def run(task, rep, out, guide, model):
    d = out / f"{task['id']}_r{rep}"
    if (d / "result.json").exists():
        return
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(guide, d / "AGORA_GUIDE.md")
    cfg = {"mcpServers": {"agora": {"command": PY, "args": [str(REPO / "adgentic_server.py")],
                                    "env": {"ADGENTIC_LOG": str(d / "agora_log.jsonl"),
                                            "ADGENTIC_GT": str(d / "agora_ground_truth.json")}}}}
    (d / "mcp.json").write_text(json.dumps(cfg, indent=1))
    prompt = PROMPT.format(request=task["request"])
    (d / "prompt.txt").write_text(prompt)
    t0 = time.time()
    r = subprocess.run(["claude", "-p", prompt, "--output-format", "stream-json", "--verbose",
                        "--model", model, "--mcp-config", str(d / "mcp.json"), "--strict-mcp-config",
                        "--tools", "Read", "--allowedTools", TOOLS, "--no-session-persistence"],
                       cwd=d, capture_output=True, text=True, timeout=900)
    (d / "transcript.jsonl").write_text(r.stdout)
    (d / "stderr.txt").write_text(r.stderr)
    final = {}
    for line in r.stdout.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("type") == "result":
            final = e
    res = {"task": task["id"], "rep": rep, "model": model, "wall_s": round(time.time() - t0, 1),
           "cost_usd": final.get("total_cost_usd"), "num_turns": final.get("num_turns"),
           "final_message": final.get("result", "")}
    (d / "result.json").write_text(json.dumps(res, indent=1))
    print(f"{d.name}: {res['wall_s']}s ${res['cost_usd']}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", required=True); ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--out", required=True); ap.add_argument("--guide", default=str(REPO / "docs" / "AGENT_GUIDE.md"))
    ap.add_argument("--model", default="claude-sonnet-5-5"); ap.add_argument("--workers", type=int, default=5)
    a = ap.parse_args()
    tasks = {t["id"]: t for t in json.load(open(HERE / "tasks.json"))["tasks"]}
    out = HERE / a.out
    jobs = [(tasks[t], r, out, a.guide, a.model) for r in range(1, a.repeats + 1) for t in a.tasks.split(",")]
    with cf.ThreadPoolExecutor(a.workers) as ex:
        for f in [ex.submit(run, *j) for j in jobs]:
            f.result()
