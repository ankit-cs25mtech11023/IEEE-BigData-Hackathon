"""Loading Task 1 data files and writing prediction files."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "task1"
DEV_DIR = DATA / "development"
TEST_DIR = DATA / "test"
OUTPUTS = ROOT / "outputs"

PREDICTION_SCHEMA_VERSION = "finreason.task1.prediction/1.0.0"

# split name -> (questions file, gold file or None, manifest file or None)
SPLITS: dict[str, tuple[Path, Path | None, Path | None]] = {
    "train": (DEV_DIR / "train_questions.jsonl", DEV_DIR / "train_gold.jsonl", DEV_DIR / "train_manifest.jsonl"),
    "dev": (DEV_DIR / "dev_questions.jsonl", DEV_DIR / "dev_gold.jsonl", DEV_DIR / "dev_manifest.jsonl"),
    "leaderboard": (DEV_DIR / "leaderboard_questions.jsonl", None, None),
    "test": (TEST_DIR / "test_questions.jsonl", None, None),
}


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: str | Path, rows: Iterable[dict[str, Any]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


@dataclass
class Case:
    """One question, joined with its gold answer and manifest row when available."""

    question: dict[str, Any]
    gold: dict[str, Any] | None = None
    manifest: dict[str, Any] | None = None

    @property
    def case_id(self) -> str:
        return self.question["case_id"]

    @property
    def text(self) -> str:
        return self.question["question"]

    @property
    def body(self) -> str:
        """Question text without the trailing 'Answer format' instructions."""
        return self.text.split("\n\nAnswer format")[0]

    @property
    def answer_spec(self) -> dict[str, Any]:
        return self.question["answer_spec"]

    @property
    def slots(self) -> list[dict[str, Any]]:
        return self.question["trace_spec"]["slots"]

    @property
    def template_id(self) -> str | None:
        return self.manifest["template_id"] if self.manifest else None


def load_split(name: str) -> list[Case]:
    questions_path, gold_path, manifest_path = SPLITS[name]
    questions = read_jsonl(questions_path)
    gold = {row["case_id"]: row for row in read_jsonl(gold_path)} if gold_path else {}
    manifest = {row["case_id"]: row for row in read_jsonl(manifest_path)} if manifest_path else {}
    return [Case(q, gold.get(q["case_id"]), manifest.get(q["case_id"])) for q in questions]


@dataclass
class Prediction:
    case_id: str
    dataset_version: str
    final: str | None = None
    steps: dict[str, str] = field(default_factory=dict)
    source: str = "abstain"  # which path produced it (not written to the submission)

    def to_record(self, slot_order: list[str]) -> dict[str, Any]:
        return {
            "schema_version": PREDICTION_SCHEMA_VERSION,
            "dataset_version": self.dataset_version,
            "case_id": self.case_id,
            "final_answer": None if self.final is None else {"value": self.final},
            "steps": [
                {"slot_id": slot_id, "value": self.steps[slot_id]}
                for slot_id in slot_order
                if slot_id in self.steps
            ],
        }


def abstain(case: Case) -> Prediction:
    return Prediction(case.case_id, case.question["dataset_version"])


def write_predictions(path: str | Path, cases: list[Case], predictions: dict[str, Prediction]) -> None:
    rows = []
    for case in cases:
        prediction = predictions.get(case.case_id) or abstain(case)
        rows.append(prediction.to_record([slot["slot_id"] for slot in case.slots]))
    write_jsonl(path, rows)
