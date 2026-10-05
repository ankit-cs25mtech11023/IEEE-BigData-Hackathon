"""Exercise the LLM-driven paths end to end with a fake client (no network)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from finreason.hidden.solver import HiddenPathSolver  # noqa: E402
from finreason.io import load_split  # noqa: E402
from finreason.llm.client import extract_code, strip_reasoning  # noqa: E402
from finreason.scoring import score_cases  # noqa: E402
from finreason.solvers.generate import generate_solver  # noqa: E402
from finreason.solvers.registry import SolverRegistry  # noqa: E402

TEMPLATE = "fp.accounting_and_financial_reporting.balance_sheets.business_combination.advanced.v1"

GOOD_SOLVER = '''
def solve(text):
    n = numbers(text)
    cash, shares, price, land, inv, pat, borrow, ap = n[:8]
    consideration = cash + shares * price
    assets = land + inv + pat
    net = assets - borrow - ap
    return {"final": consideration - net, "steps": {"trace_1": consideration, "trace_2": assets, "trace_3": net}}
'''
BAD_SOLVER = GOOD_SOLVER.replace("consideration - net", "net - consideration")


class FakeClient:
    """Returns scripted replies in order, one per request."""

    model = "fake"
    concurrency = 3

    def __init__(self, replies):
        self.replies = list(replies)
        self.stats = {}
        self.seen = []

    def chat_many(self, requests):
        self.seen.extend(requests)
        return [self.replies.pop(0) if self.replies else None for _ in requests]


def _cases():
    return [c for c in load_split("train") if c.template_id == TEMPLATE]


def test_extract_code_and_reasoning():
    reply = "<think>hmm</think>Sketch:\n```python\nx=1\n```\nFinal:\n```python\ndef solve():\n    return 2\n```"
    assert extract_code(strip_reasoning(reply)) == "def solve():\n    return 2"


def test_generation_retries_with_feedback_then_verifies():
    wrap = lambda code: f"```python\n{code}\n```"  # noqa: E731
    client = FakeClient([wrap(BAD_SOLVER), "no code here", wrap(GOOD_SOLVER)])
    result, code = generate_solver(client, TEMPLATE, _cases(), rounds=3, samples_per_round=2)
    assert result.verified and result.rounds == 2 and code == GOOD_SOLVER.strip()
    feedback = client.seen[-1].messages[-1]["content"]
    assert "expected" in feedback and "got" in feedback


def test_hidden_path_votes_for_majority():
    case = load_split("dev")[0]
    final = case.gold["final_value"]
    steps = case.gold["slot_values"]
    right = f'```python\nfrom fractions import Fraction\ndef solve():\n    return {{"final": "{final}", "steps": {steps!r}}}\n```'
    if case.answer_spec["type"] == "decimal":
        right = right.replace(f'"final": "{final}"', f'"final": Fraction("{final}")')
    wrong = '```python\ndef solve():\n    return {"final": 123456789, "steps": {}}\n```'
    client = FakeClient([right, wrong, right, right, wrong, right, right])
    solver = HiddenPathSolver(client, load_split("train"), SolverRegistry(), first_samples=3, max_samples=7)
    predictions = solver([case])
    (result,) = score_cases([case], predictions)
    assert result.final_ok
    assert solver.log[case.case_id]["samples"] == 7  # disagreement triggered extra samples
