"""Run LLM-generated Python in a separate process with a timeout and a small import allowlist.

Generated code defines a function (default `solve`) that returns either
    {"final": value, "steps": {slot_id: value, ...}}
or just the final value. Values may be Fraction / int / Decimal / float / bool / str.
Numbers cross the process boundary as exact "p/q" strings so nothing is lost to floats.

This is a guard against accidents (infinite loops, stray file/network access), not a
security boundary for hostile code.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

ALLOWED_IMPORTS = {
    "__future__", "math", "fractions", "decimal", "re", "itertools", "functools", "statistics",
    "collections", "operator", "typing", "dataclasses",
}

_RUNNER = r'''
import builtins, json, sys, resource
from fractions import Fraction
from decimal import Decimal

resource.setrlimit(resource.RLIMIT_AS, (1 << 30, 1 << 30))
ALLOWED = set(json.loads(sys.argv[1]))
_real_import = builtins.__import__
def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    # Only police imports made by the generated code itself, not stdlib internals.
    if (globals or {}).get("__name__") == "generated" and name.split(".")[0] not in ALLOWED:
        raise ImportError(f"import of {name!r} is not allowed")
    return _real_import(name, globals, locals, fromlist, level)

def encode(value):
    if isinstance(value, bool):
        return {"t": "bool", "v": value}
    if isinstance(value, (int, Fraction)):
        value = Fraction(value)
        return {"t": "num", "v": f"{value.numerator}/{value.denominator}"}
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError(f"non-finite result {value}")
        value = Fraction(value)
        return {"t": "num", "v": f"{value.numerator}/{value.denominator}"}
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError(f"non-finite result {value}")
        value = Fraction(Decimal(repr(value)))
        return {"t": "num", "v": f"{value.numerator}/{value.denominator}", "float": True}
    if isinstance(value, str):
        return {"t": "str", "v": value}
    raise TypeError(f"unsupported result type {type(value).__name__}")

payload = json.loads(sys.stdin.read())
import types
module = types.ModuleType("generated")
sys.modules["generated"] = module  # dataclasses and friends look the module up by name
namespace = module.__dict__
builtins.__import__ = _guarded_import
outputs = []
try:
    exec(compile(payload["code"], "<generated>", "exec"), namespace)
    function = namespace[payload["entry"]]
except BaseException as error:
    outputs = [{"error": f"load: {type(error).__name__}: {error}"}] * len(payload["inputs"])
else:
    for args in payload["inputs"]:
        try:
            result = function(*args)
            if not isinstance(result, dict):
                result = {"final": result, "steps": {}}
            steps = result.get("steps") or {}
            outputs.append({
                "final": None if result.get("final") is None else encode(result["final"]),
                "steps": {str(k): encode(v) for k, v in steps.items() if v is not None},
            })
        except BaseException as error:
            outputs.append({"error": f"{type(error).__name__}: {error}"[:500]})
builtins.__import__ = _real_import
sys.stdout.write(json.dumps(outputs))
'''


@dataclass
class RunResult:
    final: Any = None  # Fraction, bool or str
    steps: dict[str, Any] | None = None
    error: str | None = None
    used_float: bool = False

    @property
    def ok(self) -> bool:
        return self.error is None


def _decode(item: dict[str, Any]) -> tuple[Any, bool]:
    if item["t"] == "num":
        numerator, denominator = item["v"].split("/")
        return Fraction(int(numerator), int(denominator)), bool(item.get("float"))
    return item["v"], False


def run_program(
    code: str,
    inputs: list[tuple[Any, ...]],
    *,
    entry: str = "solve",
    timeout: float = 10.0,
) -> list[RunResult]:
    """Execute `code` once and call `entry(*args)` for each args tuple in `inputs`."""
    payload = json.dumps({"code": code, "entry": entry, "inputs": [list(args) for args in inputs]})
    try:
        completed = subprocess.run(
            [sys.executable, "-I", "-c", _RUNNER, json.dumps(sorted(ALLOWED_IMPORTS))],
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return [RunResult(error="timeout") for _ in inputs]
    if completed.returncode != 0 or not completed.stdout:
        message = (completed.stderr or "no output").strip().splitlines()[-1:] or ["crash"]
        return [RunResult(error=f"process: {message[0][:300]}") for _ in inputs]
    results = []
    for item in json.loads(completed.stdout):
        if "error" in item:
            results.append(RunResult(error=item["error"]))
            continue
        used_float = False
        final = None
        if item["final"] is not None:
            final, used_float = _decode(item["final"])
        steps = {}
        for slot_id, encoded in item["steps"].items():
            steps[slot_id], step_float = _decode(encoded)
            used_float = used_float or step_float
        results.append(RunResult(final=final, steps=steps, used_float=used_float))
    return results
