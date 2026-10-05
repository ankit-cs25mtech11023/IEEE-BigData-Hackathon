"""Validate predictions and build submission.zip with the official toolkit CLI.

Usage: python scripts/package.py {leaderboard,test} PREDICTIONS.jsonl [--output DIR]
Stops with a non-zero exit unless validate -> package -> validate-zip all pass.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from finreason.io import SPLITS  # noqa: E402

CLI = ROOT / "toolkit" / "scripts" / "task1_cli.py"


def run(*args: str) -> dict:
    completed = subprocess.run([sys.executable, str(CLI), *args], capture_output=True, text=True)
    output = completed.stdout.strip() or completed.stderr.strip()
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        parsed = {"raw": output}
    if completed.returncode != 0:
        print(json.dumps(parsed, indent=1)[:4000])
        sys.exit(f"official CLI failed: {args[0]}")
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("split", choices=["leaderboard", "test"])
    parser.add_argument("predictions")
    parser.add_argument("--output", default=None, help="directory for submission.zip (default: next to predictions)")
    args = parser.parse_args()

    predictions = Path(args.predictions).resolve()
    questions = str(SPLITS[args.split][0])
    out_dir = Path(args.output) if args.output else predictions.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / "submission.zip"
    if zip_path.exists():
        zip_path.unlink()

    # The official packager requires the file inside the ZIP to be named predictions.jsonl.
    canonical = out_dir / "predictions.jsonl"
    if canonical.resolve() != predictions:
        canonical.write_bytes(predictions.read_bytes())

    validated = run("validate", "--questions", questions, "--predictions", str(canonical))
    if not validated.get("valid"):
        print(json.dumps(validated, indent=1)[:4000])
        sys.exit("validation failed")
    packaged = run("package", "--questions", questions, "--predictions", str(canonical), "--output", str(zip_path))
    if packaged.get("status") != "PASS":
        print(json.dumps(packaged, indent=1)[:4000])
        sys.exit("packaging failed")
    zipped = run("validate-zip", "--questions", questions, "--submission-zip", str(zip_path))
    if not zipped.get("valid"):
        print(json.dumps(zipped, indent=1)[:4000])
        sys.exit("zip validation failed")
    print(f"OK {args.split}: {zip_path}")


if __name__ == "__main__":
    main()
