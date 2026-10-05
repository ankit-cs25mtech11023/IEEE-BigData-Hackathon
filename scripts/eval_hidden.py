"""Leave-template-out evaluation of the hidden path — our proxy for the hidden half of the test score.

Takes dev cases of intermediate/advanced difficulty (hidden test templates only have those levels),
answers them with the hidden path only (no template solver) and never shows the LLM any example from
the same template family. Scores with the official matcher.

Usage: python scripts/eval_hidden.py [--n 60] [--name run1] [--model NAME] [--k 3] [--max-samples 7]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from finreason.hidden.solver import HiddenPathSolver  # noqa: E402
from finreason.io import OUTPUTS, load_split, write_predictions  # noqa: E402
from finreason.llm.client import LLMClient  # noqa: E402
from finreason.scoring import score_cases, summarize  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=60, help="number of dev cases (0 = all eligible)")
    parser.add_argument("--name", default="latest")
    parser.add_argument("--model", default=None)
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--first-samples", type=int, default=3)
    parser.add_argument("--max-samples", type=int, default=7)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    dev = [c for c in load_split("dev") if c.manifest["difficulty"] in {"intermediate", "advanced"}]
    random.Random(args.seed).shuffle(dev)
    cases = dev[: args.n] if args.n else dev
    solver = HiddenPathSolver(
        LLMClient.from_env(args.model), load_split("train"),
        k_examples=args.k, first_samples=args.first_samples, max_samples=args.max_samples,
        exclude_own_family=True,
    )
    print(f"leave-template-out eval on {len(cases)} dev cases with model {solver.client.model}")
    predictions = solver(cases)

    out_dir = OUTPUTS / "hidden_eval" / args.name
    write_predictions(out_dir / "predictions.jsonl", cases, predictions)
    results = score_cases(cases, predictions)
    summary = summarize(results)
    # Accuracy by agreement bucket tells us whether voting confidence is informative.
    buckets: dict[str, list[bool]] = {}
    for result in results:
        agreement = solver.log.get(result.case_id, {}).get("agreement", 0.0)
        key = "unanimous" if agreement == 1.0 else "majority" if agreement > 0.5 else "weak"
        buckets.setdefault(key, []).append(result.final_ok)
    summary["by_agreement"] = {k: {"n": len(v), "final": round(sum(v) / len(v), 3)} for k, v in buckets.items()}
    summary["llm_stats"] = solver.client.stats
    summary["config"] = vars(args)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1))
    (out_dir / "log.json").write_text(json.dumps(solver.log, indent=1))
    print(json.dumps({k: summary[k] for k in ("overall", "by_difficulty", "by_agreement", "llm_stats")}, indent=1))


if __name__ == "__main__":
    main()
