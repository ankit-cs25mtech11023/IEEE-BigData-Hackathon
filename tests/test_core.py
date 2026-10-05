import sys
from fractions import Fraction
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from finreason.formatting import FormatError, render, render_exact  # noqa: E402
from finreason.io import load_split  # noqa: E402
from finreason.numbers import numbers  # noqa: E402
from finreason.sandbox import run_program  # noqa: E402
from finreason.scoring import value_matches  # noqa: E402
from finreason.templates import TemplateIndex  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "toolkit"))
from finreason_task1.contracts import _validate_decimal_text  # noqa: E402


@pytest.fixture(scope="module")
def labelled():
    return load_split("train") + load_split("dev")


def _gold_fraction(text):
    if "/" in text:
        numerator, denominator = text.split("/")
        return Fraction(int(numerator), int(denominator))
    return Fraction(text)


def test_render_roundtrips_every_gold_value(labelled):
    """Gold -> exact Fraction -> our renderer must be valid and match gold for every value."""
    checked = 0
    for case in labelled:
        pairs = [(case.gold["final_value"], case.answer_spec)]
        pairs += [(case.gold["slot_values"][s["slot_id"]], s["result_spec"]) for s in case.slots]
        for gold_text, spec in pairs:
            value = gold_text if spec["type"] == "enum" else _gold_fraction(gold_text)
            rendered = render(value, spec)
            if spec["type"] == "decimal":
                assert _validate_decimal_text(rendered, spec) is None, (case.case_id, rendered)
            assert value_matches(rendered, gold_text, spec), (case.case_id, gold_text, rendered)
            checked += 1
    assert checked > 3000


def test_render_rules():
    half_up_2 = {"type": "decimal", "unit": "usd", "rounding": {"mode": "half_up", "decimal_places": 2}}
    exact = {"type": "decimal", "unit": "usd", "rounding": {"mode": "exact"}}
    assert render(Fraction(1, 8), half_up_2) == "0.13"
    assert render(Fraction(-1, 8), half_up_2) == "-0.13"
    assert render(Fraction(-1, 1000), half_up_2) == "0.00"
    assert render(0.1, half_up_2) == "0.10"
    assert render(Fraction(1, 3), exact) == "1/3"
    assert render(Fraction(-1, 8), exact) == "-0.125"
    assert render(Fraction(5000), exact) == "5000"
    assert render_exact(Fraction(0)) == "0"
    enum = {"type": "enum", "allowed_values": ["false", "true"]}
    assert render(True, enum) == "true"
    assert render("False", enum) == "false"
    with pytest.raises(FormatError):
        render("maybe", enum)


def test_numbers():
    assert numbers("assets of 10000 USD and 1,200 USD") == [10000, 1200]
    assert numbers("liabilities of 1975/28 in USD millions") == [Fraction(1975, 28)]
    assert numbers("rate -3.5 and 0.46875.") == [Fraction(-7, 2), Fraction(46875, 100000)]
    assert numbers("CO2e emissions in Year-1 over a 30-day window, N(d1)") == [30]


def test_routing_dev_is_exact(labelled):
    train = [c for c in labelled if c.manifest["split"] == "train_public"]
    dev = [c for c in labelled if c.manifest["split"] != "train_public"]
    index = TemplateIndex(train)
    assert all(index.route(case) == case.template_id for case in dev)


def test_sandbox():
    code = "from fractions import Fraction\ndef solve(a, b):\n    return {'final': Fraction(a, b), 'steps': {'s': a > b}}"
    first, second = run_program(code, [(1, 3), (4, 2)])
    assert first.final == Fraction(1, 3) and first.steps == {"s": False}
    assert second.final == 2 and second.steps == {"s": True}
    assert run_program("import os\ndef solve():\n    return 1", [()])[0].error.startswith("load")
    assert run_program("def solve():\n    while True: pass", [()], timeout=1)[0].error == "timeout"
    assert run_program("def solve():\n    return 0.1", [()])[0].used_float
