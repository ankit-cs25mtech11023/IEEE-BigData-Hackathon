"""Run the pipeline on a split and write predictions (+ score when the split is labelled).

Usage:
  python scripts/predict.py dev                 # seen solvers only, scored with official scorer
  python scripts/predict.py test --hidden       # also run the hidden (LLM) path
  python scripts/predict.py leaderboard --name run1
Outputs go to outputs/<split>/<name>/predictions.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from finreason.io import OUTPUTS, load_split, write_predictions  # noqa: E402
from finreason.pipeline import predict  # noqa: E402
from finreason.scoring import official_score_dev, score_cases, summarize  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("split", choices=["train", "dev", "leaderboard", "test"])
    parser.add_argument("--name", default="latest")
    parser.add_argument("--hidden", action="store_true", help="answer non-seen questions with the LLM path")
    parser.add_argument("--no-seen", action="store_true", help="skip template solvers (hidden-path ablation)")
    args = parser.parse_args()

    cases = load_split(args.split)
    hidden_solver = None
    if args.hidden:
        from finreason.hidden.solver import HiddenPathSolver

        hidden_solver = HiddenPathSolver.from_env()
    predictions = predict(cases, hidden_solver=hidden_solver, use_seen=not args.no_seen)

    out_dir = OUTPUTS / args.split / args.name
    path = out_dir / "predictions.jsonl"
    write_predictions(path, cases, predictions)
    sources: dict[str, int] = {}
    for prediction in predictions.values():
        sources[prediction.source] = sources.get(prediction.source, 0) + 1
    print(f"wrote {path} sources={sources}")

    if cases[0].gold is not None:
        summary = summarize(score_cases(cases, predictions))
        (out_dir / "summary.json").write_text(json.dumps(summary, indent=1))
        print(json.dumps({k: summary[k] for k in ("overall", "template_macro_final", "by_source")}, indent=1))
        if args.split == "dev":
            official = official_score_dev(path, "dev")
            (out_dir / "official.json").write_text(json.dumps(official, indent=1))
            print("official:", json.dumps(official["scores"]))


if __name__ == "__main__":
    main()
