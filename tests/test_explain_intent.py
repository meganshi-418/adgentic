"""Regression tests for explain_intent (HW9). Run: .venv/bin/python -m pytest -q tests"""
import os, sys, tempfile
from pathlib import Path

tmp = tempfile.mkdtemp()
os.environ["ADGENTIC_LOG"] = f"{tmp}/log.jsonl"
os.environ["ADGENTIC_GT"] = f"{tmp}/gt.json"
os.environ.pop("ADGENTIC_PLUGINS", None)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import adgentic_server as S  # noqa: E402


def test_budget_below_every_offer_reports_cheapest_price():
    i = S.post_intent("t-shirt", "L", 20, ["price"])
    assert S.get_offers(i) == []
    r = S.explain_intent(i)
    assert r["summary"]["cheapest_in_stock_for_requested_size_ignoring_budget"] == 21.25
    assert {s["status"] for s in r["sellers"]} == {"over_budget"}


def test_nonexistent_size_is_named_as_such():
    i = S.post_intent("running shoes", "10.5", 100, ["price"])
    r = S.explain_intent(i)
    assert r["summary"]["requested_size_exists"] is False
    assert r["summary"]["cheapest_in_stock_by_size_ignoring_budget"]["10"]["all_in_price"] == 85.0
    assert all(s["status"] == "size_not_carried" for s in r["sellers"])


def test_cheapest_skips_sellers_out_of_stock_for_that_size():
    i = S.post_intent("t-shirt", "XL", 20, ["price"])  # BudgetBasics has no XL
    r = S.explain_intent(i)
    assert r["summary"]["cheapest_in_stock_for_requested_size_ignoring_budget"] == 25.5


def test_normal_purchase_unchanged():
    i = S.post_intent("running shoes", "10", 120, ["returns", "price"])
    offers = S.get_offers(i)
    assert len(offers) == 5
    r = S.explain_intent(i)
    assert r["summary"]["usable_offers"] == 5
    receipt = S.accept_offer(i, next(o["offer_id"] for o in offers if o["seller_id"] == "s3"))
    assert receipt["seller_id"] == "s3"


def test_flagged_seller_is_marked():
    i = S.post_intent("rain jacket", "M", 115, ["returns"])
    rows = {s["seller_id"]: s for s in S.explain_intent(i)["sellers"]}
    assert rows["s5"]["claim_differs_from_registered_policy"] is True
    assert rows["s1"]["claim_differs_from_registered_policy"] is False
