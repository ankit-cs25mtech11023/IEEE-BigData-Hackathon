"""Verified per-template solvers for the seen path.

Each solver lives in `solvers/generated/<template_id>.py` and defines

    def solve(text: str) -> {"final": value, "steps": {slot_id: value}}

The helper `numbers(text)` (from finreason/numbers.py) is prepended so solvers can pull the
question's numbers as exact Fractions. A solver is only saved after it reproduces gold on every
labelled instance of its template; `index.json` records that verification.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..formatting import FormatError, render
from ..io import ROOT, Case, Prediction
from ..sandbox import RunResult, run_program
from ..scoring import value_matches

SOLVER_DIR = ROOT / "solvers" / "generated"
INDEX_PATH = SOLVER_DIR / "index.json"
PREAMBLE = (Path(__file__).resolve().parents[1] / "numbers.py").read_text()


def with_preamble(code: str) -> str:
    return PREAMBLE + "\n\n# ---- solver ----\n" + code


def to_prediction(case: Case, result: RunResult, source: str) -> Prediction:
    """Render a sandbox result into a Prediction; values that fail formatting are dropped."""
    prediction = Prediction(case.case_id, case.question["dataset_version"], source=source)
    if not result.ok:
        return prediction
    if result.final is not None:
        try:
            prediction.final = render(result.final, case.answer_spec)
        except (FormatError, ValueError, ArithmeticError):
            pass
    for slot in case.slots:
        value = (result.steps or {}).get(slot["slot_id"])
        if value is None:
            continue
        try:
            prediction.steps[slot["slot_id"]] = render(value, slot["result_spec"])
        except (FormatError, ValueError, ArithmeticError):
            pass
    return prediction


@dataclass
class Verification:
    total: int
    final_ok: int
    slots_ok: int
    slots_total: int
    errors: list[str]

    @property
    def perfect(self) -> bool:
        return self.final_ok == self.total and self.slots_ok == self.slots_total

    def as_dict(self) -> dict[str, Any]:
        return {
            "total": self.total, "final_ok": self.final_ok,
            "slots_ok": self.slots_ok, "slots_total": self.slots_total,
        }


def verify(code: str, cases: list[Case]) -> tuple[Verification, list[tuple[Case, Prediction, RunResult]]]:
    """Run a solver on labelled cases and compare against gold with the official matcher."""
    results = run_program(with_preamble(code), [(case.body,) for case in cases])
    final_ok = slots_ok = slots_total = 0
    errors: list[str] = []
    details = []
    for case, result in zip(cases, results):
        prediction = to_prediction(case, result, "verify")
        details.append((case, prediction, result))
        if result.error:
            errors.append(result.error)
        if prediction.final is not None and value_matches(
            prediction.final, case.gold["final_value"], case.answer_spec
        ):
            final_ok += 1
        for slot in case.slots:
            slots_total += 1
            value = prediction.steps.get(slot["slot_id"])
            if value is not None and value_matches(
                value, case.gold["slot_values"][slot["slot_id"]], slot["result_spec"]
            ):
                slots_ok += 1
    return Verification(len(cases), final_ok, slots_ok, slots_total, errors), details


class SolverRegistry:
    def __init__(self, directory: Path = SOLVER_DIR):
        self.directory = directory
        self._lock = threading.Lock()
        self.index: dict[str, Any] = json.loads(INDEX_PATH.read_text()) if INDEX_PATH.exists() else {}

    def has(self, template_id: str) -> bool:
        return template_id in self.index and (self.directory / f"{template_id}.py").exists()

    def code(self, template_id: str) -> str:
        return (self.directory / f"{template_id}.py").read_text()

    def save(self, template_id: str, code: str, verification: Verification, meta: dict[str, Any]) -> None:
        with self._lock:
            self.directory.mkdir(parents=True, exist_ok=True)
            (self.directory / f"{template_id}.py").write_text(code)
            self.index[template_id] = {**verification.as_dict(), **meta}
            INDEX_PATH.write_text(json.dumps(self.index, indent=1, sort_keys=True))

    def solve(self, template_id: str, cases: list[Case]) -> list[Prediction]:
        results = run_program(with_preamble(self.code(template_id)), [(case.body,) for case in cases])
        return [to_prediction(case, result, "seen") for case, result in zip(cases, results)]
