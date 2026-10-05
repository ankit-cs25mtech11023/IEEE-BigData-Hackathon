"""Router: seen template solver -> hidden-path solver -> abstain."""

from __future__ import annotations

from collections import defaultdict
from typing import Callable

from .io import Case, Prediction, abstain, load_split
from .solvers.registry import SolverRegistry
from .templates import TemplateIndex

# A hidden-path solver takes the cases it must answer and returns predictions by case id.
HiddenSolver = Callable[[list[Case]], dict[str, Prediction]]


def predict(
    cases: list[Case],
    *,
    index: TemplateIndex | None = None,
    registry: SolverRegistry | None = None,
    hidden_solver: HiddenSolver | None = None,
    use_seen: bool = True,
) -> dict[str, Prediction]:
    index = index or TemplateIndex(load_split("train") + load_split("dev"))
    registry = registry or SolverRegistry()
    predictions: dict[str, Prediction] = {}

    by_template: dict[str, list[Case]] = defaultdict(list)
    leftovers: list[Case] = []
    for case in cases:
        template = index.route(case) if use_seen else None
        if template and registry.has(template):
            by_template[template].append(case)
        else:
            leftovers.append(case)

    for template, group in by_template.items():
        for case, prediction in zip(group, registry.solve(template, group)):
            if prediction.final is None:
                leftovers.append(case)  # solver crashed on this instance: let the hidden path try
            else:
                predictions[case.case_id] = prediction

    if hidden_solver and leftovers:
        predictions.update(hidden_solver(leftovers))

    for case in cases:
        predictions.setdefault(case.case_id, abstain(case))
    return predictions
