import json
import shutil

import pytest

from v2.ledger.ledger import HERE, Ledger, LedgerRefusal


@pytest.fixture
def L(tmp_path):
    shutil.copy(HERE / "budget.json", tmp_path / "budget.json")
    (tmp_path / "spend.jsonl").write_text("")
    return Ledger(tmp_path)


def test_budget_lines_from_the_plan():
    b = json.loads((HERE / "budget.json").read_text())
    assert b["owner_cap_usd"] == 100
    assert b["goals"]["phase0_foundation"]["cap_usd"] == 0
    assert b["goals"]["phase2_bakeoff"]["cap_usd"] == 17 and b["goals"]["phase3_lock_look"]["cap_usd"] == 8
    assert b["goals"]["phase4_city"]["cap_usd"] == 60
    assert sum(g["cap_usd"] for g in b["goals"].values()) <= 100
    assert Ledger().validate() == []


def test_quote_needs_owner_approval(L):
    q = L.quote("phase2_bakeoff", "runpod", "B materials", 4.0)
    with pytest.raises(LedgerRefusal, match="not approved"):
        L.authorise(q["id"])
    with pytest.raises(LedgerRefusal, match="owner"):
        L.approve(q["id"], by="agent")
    L.approve(q["id"], by="owner", note="ok for B")
    assert L.authorise(q["id"])["worst_usd"] == 4.0


def test_refuses_a_run_over_its_goal_cap(L):
    a = L.quote("phase2_bakeoff", "runpod", "C training", 12.0); L.approve(a["id"], by="owner")
    L.record_spend(a["id"], 11.5)
    b = L.quote("phase2_bakeoff", "runpod", "C test area", 6.0); L.approve(b["id"], by="owner")
    with pytest.raises(LedgerRefusal, match="cap 17"):
        L.authorise(b["id"])
    c = L.quote("phase0_foundation", "openai", "anything", 0.01); L.approve(c["id"], by="owner")
    with pytest.raises(LedgerRefusal):
        L.authorise(c["id"])                              # Phase 0 has a zero cap


def test_committed_quotes_count_against_the_cap(L):
    a = L.quote("phase3_lock_look", "openai", "night views", 5.0); L.approve(a["id"], by="owner")
    b = L.quote("phase3_lock_look", "modal", "portraits", 4.0); L.approve(b["id"], by="owner")
    with pytest.raises(LedgerRefusal):
        L.authorise(b["id"])                              # 5 committed + 4 > 8


def test_reconcile_blocks_until_billing_agrees(L):
    a = L.quote("phase2_bakeoff", "modal", "B", 3.0); L.approve(a["id"], by="owner")
    L.record_spend(a["id"], 2.0)
    assert L.reconcile("modal", "2026-11", 2.05)["ok"]
    L.reconcile("modal", "2026-11", 3.5)                  # the provider billed far more than recorded
    b = L.quote("phase2_bakeoff", "modal", "B again", 1.0); L.approve(b["id"], by="owner")
    with pytest.raises(LedgerRefusal, match="reconcil"):
        L.authorise(b["id"])


def test_spend_without_approval_is_invalid(L):
    q = L.quote("phase2_bakeoff", "runpod", "x", 1.0)
    with pytest.raises(LedgerRefusal):
        L.record_spend(q["id"], 1.0)
    L.path.write_text(L.path.read_text() + json.dumps({"type": "spend", "quote": q["id"], "goal": "phase2_bakeoff",
                                                       "provider": "runpod", "job": "x", "usd": 1.0}) + "\n")
    assert any("approved" in e for e in Ledger(L.folder).validate())


def test_a_released_quote_is_no_longer_committed_and_cannot_run(L):
    a = L.quote("phase3_lock_look", "openai", "night views", 5.0); L.approve(a["id"], by="owner")
    b = L.quote("phase3_lock_look", "modal", "portraits", 4.0); L.approve(b["id"], by="owner")
    assert L.committed("phase3_lock_look") == 9.0
    with pytest.raises(LedgerRefusal):
        L.authorise(b["id"])                              # 5 committed + 4 > 8
    with pytest.raises(LedgerRefusal, match="owner"):
        L.release(a["id"], by="agent")
    L.release(a["id"], by="owner", note="not needed")
    assert L.committed("phase3_lock_look") == 4.0 and L.status()["goals"]["phase3_lock_look"]["left_usd"] == 4.0
    assert L.authorise(b["id"])["id"] == b["id"]          # the room is free again
    with pytest.raises(LedgerRefusal, match="released"):
        L.authorise(a["id"])
    with pytest.raises(LedgerRefusal, match="released"):
        L.record_spend(a["id"], 1.0)
    with pytest.raises(LedgerRefusal, match="already released"):
        L.release(a["id"], by="owner")
    assert Ledger(L.folder).validate() == []


def test_a_quote_dropped_before_approval_can_no_longer_be_approved_or_run(L):
    q = L.quote("phase3_lock_look", "runpod", "palace and abbey", 0.9)
    with pytest.raises(LedgerRefusal, match="owner"):
        L.release(q["id"], by="agent")
    L.release(q["id"], by="owner", note="dropped, requote later")
    assert L.committed() == 0 and L.status()["goals"]["phase3_lock_look"]["left_usd"] == 8.0
    with pytest.raises(LedgerRefusal, match="released"):
        L.approve(q["id"], by="owner")
    with pytest.raises(LedgerRefusal):
        L.authorise(q["id"])
    with pytest.raises(LedgerRefusal):
        L.record_spend(q["id"], 0.1)
    assert Ledger(L.folder).validate() == []
    # an approval written by hand after the release is a file problem
    L.path.write_text(L.path.read_text() + json.dumps({"type": "approve", "quote": q["id"], "by": "owner"}) + "\n")
    assert any("released" in e for e in Ledger(L.folder).validate())


def test_only_an_unspent_quote_can_be_released(L):
    q = L.quote("phase2_bakeoff", "runpod", "x", 1.0)
    L.approve(q["id"], by="owner")
    L.record_spend(q["id"], 0.4)
    with pytest.raises(LedgerRefusal, match="already spent"):
        L.release(q["id"], by="owner")
    with pytest.raises(LedgerRefusal, match="no quote"):
        L.release("q9999", by="owner")
    # a release written by hand for a spent quote, or by someone else, is a file problem
    L.path.write_text(L.path.read_text() + json.dumps({"type": "release", "quote": q["id"], "by": "agent"}) + "\n")
    errs = Ledger(L.folder).validate()
    assert any("owner's only" in e for e in errs) and any("already spent" in e for e in errs)
