# adgentic

## Setup

Requires Python 3.10+.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

`mcp` is pinned below 2.0 because the server uses the `FastMCP` API, which mcp 2.x renamed.

Register the server with Claude Code (user scope, absolute paths):

```bash
claude mcp add --scope user adgentic -- "$PWD/.venv/bin/python" "$PWD/adgentic_server.py"
```

Then start Claude Code, paste a profile from `owner_profiles.md`, and let the agent shop.
Afterwards, audit the run:

```bash
.venv/bin/python verify.py
```

Files written next to `adgentic_server.py`:

- `log.jsonl`: every step (intent received, routed, offer signed, review verdict, acceptance)
- `ground_truth.json`: seller catalogs, public keys, and registered return policies
- `.seller_keys.json`: seller private keys, kept so older log entries still verify (gitignored)

Delete `log.jsonl` to start a fresh evaluation.

## Plugins and external sellers (HW8)

`ADGENTIC_PLUGINS` takes a list of Python files (separated by `:`). Each defines
`setup(exchange)` and can call `exchange.register_category(...)` and
`exchange.register_external_seller(...)`. An external seller builds and signs its own
offers; the exchange checks the signature against the registered public key and runs
Offer Review on them like any other offer. `post_intent` also accepts an optional
`quantity` (default 1). With no plugins set, the server behaves as before.

The NANDA Town integration (a Town mailbox seller as an Adgentic seller) uses this hook;
its connector and tests live in the Town repository under `integrations/adgentic/`.
