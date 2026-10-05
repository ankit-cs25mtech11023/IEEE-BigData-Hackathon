"""Check the LLM endpoint: list models, send one prompt, report latency and throughput.

Usage: python scripts/llm_check.py [--model NAME]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from finreason.llm.client import LLMClient, Request  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    client = LLMClient.from_env(args.model)
    try:
        models = client.list_models()
        print("models on server:", *models, sep="\n  ")
    except Exception as error:
        print("could not list models:", error)
        models = []
    if not client.model:
        if not models:
            sys.exit("set LLM_MODEL in .env")
        client.model = models[0]
    print("using model:", client.model)

    prompt = "Write a Python function solve() that returns Fraction(7, 3) * 3 using fractions.Fraction. Code only."
    request = Request([{"role": "user", "content": prompt}], temperature=0.0, max_tokens=300,
                      extra={"user": f"check-{time.time()}"})  # unique so the cache is bypassed
    start = time.time()
    reply = client.chat(request)
    elapsed = time.time() - start
    tokens = client.stats["completion_tokens"]
    print(f"latency {elapsed:.1f}s, completion tokens {tokens}, ~{tokens / elapsed:.1f} tok/s")
    print("reply:\n" + reply[:800])


if __name__ == "__main__":
    main()
