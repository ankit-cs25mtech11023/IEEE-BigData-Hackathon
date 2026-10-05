"""Score predictions with the official toolkit's per-case logic, plus breakdowns.

`official_score_dev` shells out to the unmodified official CLI and is the number to trust.
`score_cases` reuses the official `value_matches` for fast per-case diagnostics.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .io import ROOT, SPLITS, Case, Prediction

TOOLKIT = ROOT / "toolkit"
if str(TOOLKIT) not in sys.path:
    sys.path.insert(0, str(TOOLKIT))

from finreason_task1.scoring import value_matches  # noqa: E402  (official, unmodified)


@dataclass
class CaseResult:
    case_id: str
    final_ok: bool
    matched_slots: int
    total_slots: int
    template_id: str | None
    difficulty: str | None
    source: str


def score_case(case: Case, prediction: Prediction | None) -> CaseResult:
    gold = case.gold
    assert gold is not None, f"{case.case_id} has no gold"
    final_ok = False
    matched = 0
    if prediction is not None and prediction.final is not None:
        try:
            final_ok = value_matches(prediction.final, gold["final_value"], case.answer_spec)
        except Exception:
            final_ok = False
    for slot in case.slots:
        value = prediction.steps.get(slot["slot_id"]) if prediction else None
        if value is None:
            continue
        try:
            matched += value_matches(value, gold["slot_values"][slot["slot_id"]], slot["result_spec"])
        except Exception:
            pass
    manifest = case.manifest or {}
    return CaseResult(
        case.case_id,
        final_ok,
        matched,
        len(case.slots),
        manifest.get("template_id"),
        manifest.get("difficulty"),
        prediction.source if prediction else "missing",
    )


def score_cases(cases: list[Case], predictions: Mapping[str, Prediction]) -> list[CaseResult]:
    return [score_case(case, predictions.get(case.case_id)) for case in cases]


def summarize(results: list[CaseResult]) -> dict[str, Any]:
    """Micro accuracy overall, macro over templates, and breakdowns by difficulty and source."""

    def block(items: list[CaseResult]) -> dict[str, Any]:
        slots = sum(item.total_slots for item in items)
        return {
            "n": len(items),
            "final": round(sum(item.final_ok for item in items) / len(items), 4) if items else None,
            "steps": round(sum(item.matched_slots for item in items) / slots, 4) if slots else None,
        }

    by_template: dict[str, list[CaseResult]] = defaultdict(list)
    by_difficulty: dict[str, list[CaseResult]] = defaultdict(list)
    by_source: dict[str, list[CaseResult]] = defaultdict(list)
    for item in results:
        by_template[item.template_id or "?"].append(item)
        by_difficulty[item.difficulty or "?"].append(item)
        by_source[item.source].append(item)
    template_finals = [sum(i.final_ok for i in v) / len(v) for v in by_template.values()]
    return {
        "overall": block(results),
        "template_macro_final": round(sum(template_finals) / len(template_finals), 4) if template_finals else None,
        "by_difficulty": {key: block(value) for key, value in sorted(by_difficulty.items())},
        "by_source": {key: block(value) for key, value in sorted(by_source.items())},
        "failed_templates": sorted(
            key for key, value in by_template.items() if not all(i.final_ok for i in value)
        ),
    }


def official_score_dev(predictions_path: str | Path, split: str = "dev") -> dict[str, Any]:
    """Run the official `score-dev` CLI (works for any labelled split: train or dev)."""
    questions, gold, manifest = SPLITS[split]
    completed = subprocess.run(
        [
            sys.executable, str(TOOLKIT / "scripts" / "task1_cli.py"), "score-dev",
            "--questions", str(questions), "--gold", str(gold),
            "--manifest", str(manifest), "--predictions", str(predictions_path),
        ],
        capture_output=True, text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr or completed.stdout)
    return json.loads(completed.stdout)
