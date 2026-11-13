"""The v2 spend ledger: one record of every quote, approval, spend and billing reconciliation, for all providers
(spec: v2/docs/specs/ledger.md; V1_RETRO P9).

Files (in git, small):
  budget.json   the owner's total cap and one line per goal (cap, plan, phase), from PLAN_V2 section 10
  spend.jsonl   append-only events, one JSON object per line:
                quote      {id, goal, provider, job, worst_usd, note}
                approve    {quote, by, note}                 only the owner approves; recorded with their words
                spend      {quote, goal, provider, job, usd, measured_by}
                reconcile  {provider, period, billed_usd, ledger_usd, ok}
                release    {quote, by, note}                 the owner gives up a quote that was never spent,
                                                             approved or not: it no longer counts as committed
                                                             and can no longer be approved or authorised (a later
                                                             run needs a new quote)

Rules enforced by `authorise()` (call it before any paid run):
  1. the run has a quote, and the quote has an approval;
  2. spent + committed (approved quotes not yet spent) + this run's worst case <= the goal's cap;
  3. the total over all goals stays <= the owner's cap;
  4. the provider's last reconciliation, if any, was within the tolerance (5%) - otherwise reconcile first.
A refusal raises LedgerRefusal with the reason; nothing is spent.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOLERANCE = 0.05


class LedgerRefusal(Exception):
    pass


class Ledger:
    def __init__(self, folder: Path = HERE):
        self.folder = Path(folder)
        self.budget = json.loads((self.folder / "budget.json").read_text())
        self.path = self.folder / "spend.jsonl"
        self.events = []
        if self.path.exists():
            for i, line in enumerate(self.path.read_text().splitlines()):
                if line.strip():
                    self.events.append(json.loads(line))

    # ------------------------------------------------------------------ reading
    def goal(self, name):
        g = self.budget["goals"].get(name)
        if g is None:
            raise LedgerRefusal(f"unknown goal {name!r}; goals: {', '.join(self.budget['goals'])}")
        return g

    def quotes(self):
        return {e["id"]: e for e in self.events if e["type"] == "quote"}

    def approved(self):
        return {e["quote"] for e in self.events if e["type"] == "approve"}

    def released(self):
        """Quotes the owner released unspent: no longer committed, no longer runnable."""
        return {e["quote"] for e in self.events if e["type"] == "release"}

    def spent(self, goal=None):
        return round(sum(e["usd"] for e in self.events if e["type"] == "spend" and (goal is None or e["goal"] == goal)), 4)

    def committed(self, goal=None):
        """Worst cases of approved quotes with no spend recorded yet."""
        q, ap = self.quotes(), self.approved()
        done = {e["quote"] for e in self.events if e["type"] == "spend"} | self.released()
        return round(sum(q[i]["worst_usd"] for i in ap if i in q and i not in done and (goal is None or q[i]["goal"] == goal)), 4)

    def status(self):
        out = {"owner_cap_usd": self.budget["owner_cap_usd"], "spent_usd": self.spent(), "committed_usd": self.committed(),
               "goals": {}}
        for name, g in self.budget["goals"].items():
            out["goals"][name] = {"cap_usd": g["cap_usd"], "spent_usd": self.spent(name), "committed_usd": self.committed(name),
                                  "left_usd": round(g["cap_usd"] - self.spent(name) - self.committed(name), 4)}
        return out

    def validate(self):
        """Problems with the files themselves (bad events, caps over the owner's cap, spends without approval)."""
        errs = []
        caps = sum(g["cap_usd"] for g in self.budget["goals"].values())
        if caps > self.budget["owner_cap_usd"] + 1e-9:
            errs.append(f"goal caps add up to {caps}, over the owner's cap {self.budget['owner_cap_usd']}")
        q, ap = self.quotes(), self.approved()
        need = {"quote": {"id", "goal", "provider", "job", "worst_usd"}, "approve": {"quote", "by"},
                "spend": {"quote", "goal", "provider", "job", "usd"}, "reconcile": {"provider", "period", "billed_usd", "ledger_usd"},
                "release": {"quote", "by"}}
        gone = set()
        for i, e in enumerate(self.events):
            t = e.get("type")
            if t not in need:
                errs.append(f"event {i}: unknown type {t!r}"); continue
            miss = need[t] - set(e)
            if miss:
                errs.append(f"event {i}: missing {sorted(miss)}")
            if t == "approve" and e.get("by") != "owner":
                errs.append(f"event {i}: approvals are the owner's only")
            if t == "approve" and e.get("quote") in gone:
                errs.append(f"event {i}: approval of a released quote")
            if t == "spend" and e.get("quote") not in ap:
                errs.append(f"event {i}: spend without an approved quote")
            if t == "spend" and e.get("quote") in gone:
                errs.append(f"event {i}: spend on a released quote")
            if t == "release":
                if e.get("by") != "owner":
                    errs.append(f"event {i}: releases are the owner's only")
                if e.get("quote") not in self.quotes():
                    errs.append(f"event {i}: release of a quote that does not exist")
                if any(x["type"] == "spend" and x.get("quote") == e.get("quote") for x in self.events[:i]):
                    errs.append(f"event {i}: release of a quote that is already spent")
                gone.add(e.get("quote"))
            if t in ("quote", "spend") and e.get("goal") not in self.budget["goals"]:
                errs.append(f"event {i}: unknown goal {e.get('goal')!r}")
        for name, g in self.budget["goals"].items():
            if self.spent(name) > g["cap_usd"] + 1e-9:
                errs.append(f"goal {name}: spent {self.spent(name)} over its cap {g['cap_usd']}")
        return errs

    # ------------------------------------------------------------------ writing
    def _append(self, ev):
        ev = {"ts": datetime.datetime.now().isoformat(timespec="seconds"), **ev}
        with self.path.open("a") as f:
            f.write(json.dumps(ev, separators=(",", ":")) + "\n")
        self.events.append(ev)
        return ev

    def quote(self, goal, provider, job, worst_usd, note=""):
        self.goal(goal)
        if worst_usd < 0:
            raise LedgerRefusal("a quote is a positive worst case")
        qid = f"q{sum(1 for e in self.events if e['type'] == 'quote') + 1:04d}"
        return self._append({"type": "quote", "id": qid, "goal": goal, "provider": provider, "job": job,
                             "worst_usd": round(float(worst_usd), 4), "note": note})

    def approve(self, quote_id, by, note=""):
        if by != "owner":
            raise LedgerRefusal("only the owner approves a quote")
        if quote_id not in self.quotes():
            raise LedgerRefusal(f"no quote {quote_id}")
        if quote_id in self.released():
            raise LedgerRefusal(f"quote {quote_id} was released by the owner: quote again")
        return self._append({"type": "approve", "quote": quote_id, "by": by, "note": note})

    def release(self, quote_id, by, note=""):
        """The owner gives up an unspent quote. Approved: its worst case stops counting as committed. Not yet
        approved: it is dropped, and can no longer be approved. Either way a later run needs a new quote."""
        if by != "owner":
            raise LedgerRefusal("only the owner releases a quote")
        if quote_id not in self.quotes():
            raise LedgerRefusal(f"no quote {quote_id}")
        if any(e["type"] == "spend" and e["quote"] == quote_id for e in self.events):
            raise LedgerRefusal(f"quote {quote_id} is already spent")
        if quote_id in self.released():
            raise LedgerRefusal(f"quote {quote_id} is already released")
        return self._append({"type": "release", "quote": quote_id, "by": by, "note": note})

    def authorise(self, quote_id):
        """Raises LedgerRefusal unless the quoted run may start now."""
        q = self.quotes().get(quote_id)
        if q is None:
            raise LedgerRefusal(f"no quote {quote_id}: quote the run first")
        if quote_id not in self.approved():
            raise LedgerRefusal(f"quote {quote_id} is not approved by the owner")
        if any(e["type"] == "spend" and e["quote"] == quote_id for e in self.events):
            raise LedgerRefusal(f"quote {quote_id} is already spent: quote again")
        if quote_id in self.released():
            raise LedgerRefusal(f"quote {quote_id} was released by the owner: quote again")
        g = self.goal(q["goal"])
        others = self.committed(q["goal"]) - q["worst_usd"]
        total = self.spent(q["goal"]) + others + q["worst_usd"]
        if total > g["cap_usd"] + 1e-9:
            raise LedgerRefusal(f"goal {q['goal']}: spent {self.spent(q['goal'])} + committed {round(others, 4)} + this run "
                                f"{q['worst_usd']} = {round(total, 4)} > cap {g['cap_usd']}")
        all_total = self.spent() + self.committed()
        if all_total > self.budget["owner_cap_usd"] + 1e-9:
            raise LedgerRefusal(f"all goals: {all_total} > the owner's cap {self.budget['owner_cap_usd']}")
        rec = [e for e in self.events if e["type"] == "reconcile" and e["provider"] == q["provider"]]
        if rec and not rec[-1]["ok"]:
            raise LedgerRefusal(f"{q['provider']}: last reconciliation off by more than {TOLERANCE:.0%}: reconcile first")
        return q

    def record_spend(self, quote_id, usd, measured_by="provider billing"):
        q = self.quotes().get(quote_id)
        if q is None or quote_id not in self.approved():
            raise LedgerRefusal(f"spend needs an approved quote ({quote_id})")
        if quote_id in self.released():
            raise LedgerRefusal(f"quote {quote_id} was released by the owner: nothing may be spent on it")
        return self._append({"type": "spend", "quote": quote_id, "goal": q["goal"], "provider": q["provider"],
                             "job": q["job"], "usd": round(float(usd), 4), "over_quote": usd > q["worst_usd"],
                             "measured_by": measured_by})

    def reconcile(self, provider, period, billed_usd):
        ledger_usd = round(sum(e["usd"] for e in self.events if e["type"] == "spend" and e["provider"] == provider), 4)
        ok = abs(billed_usd - ledger_usd) <= TOLERANCE * max(billed_usd, ledger_usd, 0.01) or abs(billed_usd - ledger_usd) < 0.05
        return self._append({"type": "reconcile", "provider": provider, "period": period, "billed_usd": round(float(billed_usd), 4),
                             "ledger_usd": ledger_usd, "ok": bool(ok)})


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m v2.ledger.ledger", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("validate")
    q = sub.add_parser("quote"); q.add_argument("goal"); q.add_argument("provider"); q.add_argument("job"); q.add_argument("worst_usd", type=float); q.add_argument("--note", default="")
    a = sub.add_parser("approve"); a.add_argument("quote"); a.add_argument("--by", required=True); a.add_argument("--note", default="")
    rl = sub.add_parser("release"); rl.add_argument("quote"); rl.add_argument("--by", required=True); rl.add_argument("--note", default="")
    c = sub.add_parser("authorise"); c.add_argument("quote")
    s = sub.add_parser("spend"); s.add_argument("quote"); s.add_argument("usd", type=float); s.add_argument("--measured-by", default="provider billing")
    r = sub.add_parser("reconcile"); r.add_argument("provider"); r.add_argument("period"); r.add_argument("billed_usd", type=float)
    x = ap.parse_args(argv)
    L = Ledger()
    try:
        if x.cmd == "status":
            print(json.dumps(L.status(), indent=1))
        elif x.cmd == "validate":
            errs = L.validate()
            print("\n".join(errs) or "ledger ok")
            return 1 if errs else 0
        elif x.cmd == "quote":
            print(L.quote(x.goal, x.provider, x.job, x.worst_usd, x.note))
        elif x.cmd == "approve":
            print(L.approve(x.quote, x.by, x.note))
        elif x.cmd == "release":
            print(L.release(x.quote, x.by, x.note))
        elif x.cmd == "authorise":
            print("authorised:", L.authorise(x.quote))
        elif x.cmd == "spend":
            print(L.record_spend(x.quote, x.usd, x.measured_by))
        elif x.cmd == "reconcile":
            print(L.reconcile(x.provider, x.period, x.billed_usd))
    except LedgerRefusal as ex:
        print("REFUSED:", ex, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
