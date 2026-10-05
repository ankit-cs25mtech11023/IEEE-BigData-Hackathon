"""Generate and verify one deterministic solver per seen template.

Loop per template:
  1. Prompt the LLM with the template's distinct phrasings, specs and gold answers.
  2. Extract `solve(text)` code, run it on every labelled instance (train + dev) in the sandbox.
  3. Accept only if every final answer and every slot matches gold exactly.
  4. Otherwise send back the failing instances (expected vs got, errors) and retry.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from ..io import Case
from ..llm.client import LLMClient, Request, extract_code
from ..scoring import value_matches
from ..templates import skeleton
from .registry import SolverRegistry, Verification, verify

SYSTEM = """You write small, exact Python solvers for templated financial word problems.

Contract:
- Define `def solve(text: str) -> dict` returning {"final": value, "steps": {slot_id: value, ...}}.
- `text` is the question body. A helper `numbers(text) -> list[Fraction]` is already defined: it returns
  every standalone number in order of appearance as an exact Fraction (handles 1,200 / -3.5 / 1975/28;
  skips numbers glued to words like CO2e, d1, Year-1).
  It is injected into your module's globals before your code runs: call it directly. Do NOT import,
  redefine, stub, or re-implement it, and do not write your own number-extraction regex.
- Use fractions.Fraction for ALL arithmetic. Never use float, round(), or Decimal rounding: the caller
  applies the required rounding. Return exact Fractions/ints for numbers, and Python bool or the exact
  allowed string for enum answers.
- Include every listed slot_id in "steps" with the exact (unrounded) intermediate value it describes,
  unless the slot's spec says it is rounded, in which case still return the exact value.
- Percent-unit values are in percent points (5.76 means 5.76%), as in the gold answers shown.
- The wording varies between instances. If the number positions are not identical across all phrasings,
  locate each number by nearby keywords with `re` instead of relying on position.
- Allowed imports: fractions, math, re, decimal, itertools, functools, statistics, collections.
- Keep comments to a few short lines; do not write your reasoning into the code.
- Reply with one ```python code block containing the full solver and nothing else."""


def _case_block(case: Case) -> str:
    slots = {s["slot_id"]: s["description"] for s in case.slots}
    return (
        f"QUESTION:\n{case.body}\n"
        f"GOLD final: {case.gold['final_value']}\n"
        f"GOLD steps: {json.dumps(case.gold['slot_values'])}\n"
        + (f"SLOT DESCRIPTIONS: {json.dumps(slots)}\n" if slots else "")
    )


def build_prompt(cases: list[Case], max_examples: int = 5) -> str:
    # Prefer one example per distinct phrasing, then fill up to max_examples.
    chosen: list[Case] = []
    seen_skeletons: set[str] = set()
    for case in cases:
        if skeleton(case) not in seen_skeletons:
            seen_skeletons.add(skeleton(case))
            chosen.append(case)
    for case in cases:
        if len(chosen) >= max_examples:
            break
        if case not in chosen:
            chosen.append(case)
    chosen = chosen[: max(max_examples, len(seen_skeletons))]
    first = cases[0]
    header = (
        f"answer_spec: {json.dumps(first.answer_spec)}\n"
        f"slots: {json.dumps(first.slots)}\n"
        f"Distinct phrasings in this template: {len(seen_skeletons)}\n\n"
    )
    return header + "\n".join(_case_block(case) for case in chosen)


def _feedback(details, limit: int = 4) -> str:
    lines = []
    for case, prediction, result in details:
        if result.error:
            lines.append(f"QUESTION:\n{case.body}\nERROR: {result.error}\n")
        else:
            bad_final = prediction.final is None or not value_matches(
                prediction.final, case.gold["final_value"], case.answer_spec)
            bad_slots = {
                s["slot_id"]: (prediction.steps.get(s["slot_id"]), case.gold["slot_values"][s["slot_id"]])
                for s in case.slots
                if prediction.steps.get(s["slot_id"]) is None
                or not value_matches(prediction.steps[s["slot_id"]], case.gold["slot_values"][s["slot_id"]],
                                     s["result_spec"])
            }
            if not bad_final and not bad_slots:
                continue
            msg = f"QUESTION:\n{case.body}\n"
            if bad_final:
                msg += f"final: got {prediction.final}, expected {case.gold['final_value']}\n"
            for slot_id, (got, expected) in bad_slots.items():
                msg += f"step {slot_id}: got {got}, expected {expected}\n"
            if result.used_float:
                msg += "NOTE: a float was returned; use Fraction only.\n"
            lines.append(msg)
        if len(lines) >= limit:
            break
    return "\n".join(lines)


@dataclass
class GenerationResult:
    template_id: str
    verified: bool
    rounds: int
    best: Verification | None


def generate_solver(
    client: LLMClient,
    template_id: str,
    cases: list[Case],
    *,
    rounds: int = 4,
    samples_per_round: int = 2,
) -> tuple[GenerationResult, str | None]:
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": build_prompt(cases)}]
    best: tuple[Verification, str, list] | None = None
    for round_index in range(rounds):
        requests = [
            Request(messages, temperature=0.0 if (round_index == 0 and k == 0) else 0.6,
                    max_tokens=2048, sample=round_index * 10 + k, thinking=False)
            for k in range(samples_per_round)
        ]
        for reply in client.chat_many(requests):
            code = extract_code(reply or "")
            if not code:
                continue
            verification, details = verify(code, cases)
            if verification.perfect:
                return GenerationResult(template_id, True, round_index + 1, verification), code
            score = (verification.final_ok, verification.slots_ok)
            if best is None or score > (best[0].final_ok, best[0].slots_ok):
                best = (verification, code, details)
        if best is None:
            continue
        # Feed back the best attempt's failures and ask for a corrected solver.
        messages = messages[:2] + [
            {"role": "assistant", "content": f"```python\n{best[1]}\n```"},
            {"role": "user", "content": "This solver is wrong on these instances:\n\n"
                                        + _feedback(best[2])
                                        + "\nFix it. Reply with the full corrected solver in one ```python block."},
        ]
    return GenerationResult(template_id, False, rounds, best[0] if best else None), None


def generate_all(
    client: LLMClient,
    groups: dict[str, list[Case]],
    registry: SolverRegistry,
    *,
    parallel_templates: int = 2,
    force: bool = False,
) -> list[GenerationResult]:
    todo = {t: cs for t, cs in groups.items() if force or not registry.has(t)}

    def work(item):
        template_id, cases = item
        result, code = generate_solver(client, template_id, cases)
        if code is not None:
            registry.save(template_id, code, result.best, {"rounds": result.rounds, "model": client.model})
        status = "OK " if result.verified else "FAIL"
        best = result.best.as_dict() if result.best else None
        print(f"{status} {template_id} rounds={result.rounds} best={best}", flush=True)
        return result

    with ThreadPoolExecutor(parallel_templates) as pool:
        return list(pool.map(work, sorted(todo.items())))
