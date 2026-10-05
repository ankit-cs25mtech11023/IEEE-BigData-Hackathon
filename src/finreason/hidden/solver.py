"""Hidden path: program-of-thought with self-consistency for questions without a verified solver.

For each question the LLM writes `solve()` with the question's numbers as Fraction literals.
Programs run in the sandbox; we render their outputs with the official rounding rules and vote:
  - final answer: majority over rendered values (float-tainted programs get half a vote);
  - each slot: majority among programs that agree with the winning final answer.
Sampling is adaptive: a few samples first, more only when they disagree.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from ..formatting import FormatError, render
from ..io import Case, Prediction, load_split
from ..llm.client import LLMClient, Request, extract_code
from ..sandbox import run_program
from ..solvers.registry import SolverRegistry
from .retrieval import Retriever, family

SYSTEM = """You are an expert in finance and accounting who solves word problems by writing exact Python.

Write `def solve() -> dict` that returns {"final": value, "steps": {slot_id: value, ...}}.
Rules:
- Copy every number from the question into a fractions.Fraction literal, e.g. Fraction("0.46875"),
  Fraction("1975/28"). Do ALL arithmetic with Fraction. Never use float, round(), or math functions that
  return floats unless the problem truly needs them (e.g. sqrt, exp, log): then use them only where needed.
- Do not round anything. Return exact values; the caller applies the required rounding.
- Follow the question's own definitions, formulas, conventions and edge-case rules literally, even if they
  differ from textbook practice. The scenario is fictional and self-contained.
- Percent-unit values are percent points (5.76 means 5.76%), matching the unit in the answer spec.
- "steps" must contain every listed slot_id, each holding the intermediate value its description asks for.
- Enum answers: return exactly one of the allowed strings (e.g. "true"/"false").
- Allowed imports: fractions, math, decimal, itertools, functools, statistics, collections, re.
First think briefly in plain text about which quantities to compute (a few lines), then give the full
solution in one ```python code block."""


def _spec_text(case: Case) -> str:
    slots = [
        {"slot_id": s["slot_id"], "description": s["description"], "spec": s["result_spec"]}
        for s in case.slots
    ]
    return f"ANSWER SPEC: {json.dumps(case.answer_spec)}\nSLOTS: {json.dumps(slots)}"


def _example_block(case: Case, solver_code: str | None) -> str:
    block = (
        f"QUESTION:\n{case.body}\n{_spec_text(case)}\n"
        f"CORRECT final: {case.gold['final_value']}\n"
        f"CORRECT steps: {json.dumps(case.gold['slot_values'])}\n"
    )
    if solver_code and len(solver_code) < 2500:
        block += f"REFERENCE COMPUTATION (parses numbers from the text):\n```python\n{solver_code}\n```\n"
    return block


@dataclass
class Vote:
    final: str | None
    steps: dict[str, str]
    agreement: float
    samples: int


def vote(case: Case, results) -> Vote:
    rendered = []
    for result in results:
        if not result.ok or result.final is None:
            continue
        try:
            final = render(result.final, case.answer_spec)
        except (FormatError, ValueError, ArithmeticError):
            continue
        steps = {}
        for slot in case.slots:
            value = (result.steps or {}).get(slot["slot_id"])
            if value is None:
                continue
            try:
                steps[slot["slot_id"]] = render(value, slot["result_spec"])
            except (FormatError, ValueError, ArithmeticError):
                pass
        rendered.append((final, steps, 0.5 if result.used_float else 1.0))
    if not rendered:
        return Vote(None, {}, 0.0, len(results))
    weights: Counter = Counter()
    for final, _, weight in rendered:
        weights[final] += weight
    winner, winner_weight = weights.most_common(1)[0]
    slot_votes: dict[str, Counter] = defaultdict(Counter)
    for final, steps, weight in rendered:
        if final == winner:
            for slot_id, value in steps.items():
                slot_votes[slot_id][value] += weight
    steps = {slot_id: counter.most_common(1)[0][0] for slot_id, counter in slot_votes.items()}
    return Vote(winner, steps, winner_weight / sum(weights.values()), len(results))


class HiddenPathSolver:
    def __init__(
        self,
        client: LLMClient,
        pool: list[Case],
        registry: SolverRegistry | None = None,
        *,
        k_examples: int = 3,
        first_samples: int = 3,
        max_samples: int = 7,
        exclude_own_family: bool = False,
    ):
        self.client = client
        self.retriever = Retriever(pool)
        self.registry = registry or SolverRegistry()
        self.k_examples = k_examples
        self.first_samples = first_samples
        self.max_samples = max_samples
        # Leave-template-out evaluation: never show examples from the question's own family.
        self.exclude_own_family = exclude_own_family
        self.log: dict[str, dict] = {}

    @classmethod
    def from_env(cls, **kwargs) -> "HiddenPathSolver":
        return cls(LLMClient.from_env(), load_split("train") + load_split("dev"), **kwargs)

    def messages(self, case: Case) -> list[dict[str, str]]:
        exclude = {family(case.template_id)} if self.exclude_own_family and case.template_id else set()
        examples = self.retriever.search(case, self.k_examples, exclude)
        shots = "\n".join(
            _example_block(ex, self.registry.code(ex.template_id) if self.registry.has(ex.template_id) else None)
            for ex in examples
        )
        user = (
            f"Worked examples of related problems (different scenarios):\n\n{shots}\n"
            f"Now solve this problem.\n\nQUESTION:\n{case.body}\n{_spec_text(case)}"
        )
        return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]

    def _sample(self, case: Case, messages, start: int, count: int):
        requests = [
            Request(messages, temperature=0.0 if i == 0 else 0.7, max_tokens=3072, sample=i)
            for i in range(start, start + count)
        ]
        programs = [extract_code(reply or "") for reply in self.client.chat_many(requests)]
        results = []
        for code in programs:
            if code is None:
                continue
            results.extend(run_program(code, [()], timeout=10))
        return results

    def solve_case(self, case: Case) -> Prediction:
        messages = self.messages(case)
        results = self._sample(case, messages, 0, self.first_samples)
        decision = vote(case, results)
        if decision.agreement < 1.0 or decision.final is None:
            results += self._sample(case, messages, self.first_samples, self.max_samples - self.first_samples)
            decision = vote(case, results)
        self.log[case.case_id] = {"agreement": round(decision.agreement, 3), "samples": decision.samples,
                                  "final": decision.final}
        prediction = Prediction(case.case_id, case.question["dataset_version"], source="hidden")
        prediction.final = decision.final
        prediction.steps = decision.steps
        return prediction

    def __call__(self, cases: list[Case]) -> dict[str, Prediction]:
        # Questions run in parallel; each question's samples also run in parallel inside the client.
        workers = max(1, self.client.concurrency // self.first_samples)
        done = 0
        predictions = {}
        with ThreadPoolExecutor(workers) as pool:
            for prediction in pool.map(self.solve_case, cases):
                predictions[prediction.case_id] = prediction
                done += 1
                if done % 10 == 0 or done == len(cases):
                    print(f"  hidden path {done}/{len(cases)}  llm={self.client.stats}", flush=True)
        return predictions
