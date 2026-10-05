"""Generate verified seen-template solvers with the LLM.

Usage:
  python scripts/gen_solvers.py                    # all templates without a solver, verify on train only
  python scripts/gen_solvers.py --include-dev      # also require dev instances to pass (final run)
  python scripts/gen_solvers.py --limit 10         # first 10 missing templates (smoke test)
  python scripts/gen_solvers.py --templates ID ... # specific templates
  python scripts/gen_solvers.py --force ...        # regenerate even if a solver exists
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from finreason.io import load_split  # noqa: E402
from finreason.llm.client import LLMClient  # noqa: E402
from finreason.solvers.generate import generate_all  # noqa: E402
from finreason.solvers.registry import SolverRegistry  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-dev", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--templates", nargs="*", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--parallel", type=int, default=2, help="templates processed at once")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    cases = load_split("train") + (load_split("dev") if args.include_dev else [])
    groups = defaultdict(list)
    for case in cases:
        groups[case.template_id].append(case)
    registry = SolverRegistry()
    if args.templates:
        groups = {t: groups[t] for t in args.templates}
    todo = sorted(t for t in groups if args.force or not registry.has(t))
    if args.limit:
        todo = todo[: args.limit]
    groups = {t: groups[t] for t in todo}
    print(f"generating {len(groups)} solvers ({len(registry.index)} already verified)")

    client = LLMClient.from_env(args.model)
    results = generate_all(client, groups, registry, parallel_templates=args.parallel, force=args.force)
    ok = sum(r.verified for r in results)
    print(f"verified {ok}/{len(results)} this run; registry now has {len(registry.index)} / 290")
    print("llm stats:", client.stats)


if __name__ == "__main__":
    main()
