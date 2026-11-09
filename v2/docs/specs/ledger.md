# Spend ledger

**Purpose.** One record of all money for v2, every provider (RunPod, Modal, OpenAI, Cloudflare R2), so a run cannot
start without a quote, the owner's OK and room under its goal's cap, and the billing is reconciled (V1_RETRO P9:
v1 spent ~$130–150 against plans of ~$10–60, most of it unlogged). Code: `v2/ledger/ledger.py`.

**Files (in git).**
- `budget.json`: the owner's cap ($100) and one line per goal from PLAN_V2 section 10: phase 0 $0, phase 1 $0,
  bake-off ≤ $17, lock the look ≤ $8, the city ≤ $60, launch ≤ $3 (R2's first month). Caps add up to $88; the
  other $12 needs a new line from the owner.
- `spend.jsonl`: append-only events — `quote` (goal, provider, job, worst case), `approve` (by the owner only),
  `spend` (measured cost against an approved quote), `reconcile` (provider's billing vs the ledger).

**Rules** (`Ledger.authorise(quote)`, called before any paid run):
1. The run has a quote and the quote has the owner's approval.
2. Spent + committed (approved, not yet spent) + this run's worst case ≤ the goal's cap.
3. All goals together ≤ the owner's cap.
4. The provider's last reconciliation agreed within 5%; otherwise reconcile first.
5. A batch over $5 starts with a pilot of ≤ 10% whose measured cost sets the cap for the rest (PLAN_V2 principle 7;
   enforced by quoting the pilot and the rest separately).
A refusal raises `LedgerRefusal` and nothing runs. CLI: `python -m v2.ledger.ledger status | quote | approve |
authorise | spend | reconcile | validate`.

**Checks.** L1 (gate) the ledger validates (events well formed, every spend has an owner-approved quote, no goal over
its cap) · L2 (gate) total ≤ $100 · L3 (gate) Phase 0 spend = $0. Unit tests: `v2/ledger/tests/test_ledger.py`.
