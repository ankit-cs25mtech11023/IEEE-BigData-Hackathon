"""TF-IDF retrieval of similar labelled cases to use as worked examples."""

from __future__ import annotations

import math
import re
from collections import Counter

from ..io import Case

_TOKEN = re.compile(r"[a-z][a-z_]+")


def family(template_id: str | None) -> str:
    """Template family without difficulty/version: fp.<domain>.<topic>.<family>."""
    return ".".join((template_id or "").split(".")[:4])


def _tokens(case: Case) -> list[str]:
    text = case.body + " " + " ".join(slot["description"] for slot in case.slots)
    return _TOKEN.findall(text.lower())


class Retriever:
    def __init__(self, pool: list[Case]):
        # One representative per template keeps examples diverse.
        by_template: dict[str, Case] = {}
        for case in pool:
            by_template.setdefault(case.template_id or case.case_id, case)
        self.pool = list(by_template.values())
        documents = [Counter(_tokens(case)) for case in self.pool]
        frequency = Counter(token for doc in documents for token in doc)
        n = len(documents)
        self.idf = {token: math.log((n + 1) / (count + 1)) + 1 for token, count in frequency.items()}
        self.vectors = [self._vector(doc) for doc in documents]

    def _vector(self, counts: Counter) -> dict[str, float]:
        vector = {t: (1 + math.log(c)) * self.idf.get(t, 1.0) for t, c in counts.items()}
        norm = math.sqrt(sum(v * v for v in vector.values())) or 1.0
        return {t: v / norm for t, v in vector.items()}

    def search(self, case: Case, k: int = 3, exclude_families: set[str] | None = None) -> list[Case]:
        query = self._vector(Counter(_tokens(case)))
        exclude_families = exclude_families or set()
        scored = []
        for candidate, vector in zip(self.pool, self.vectors):
            if family(candidate.template_id) in exclude_families:
                continue
            score = sum(weight * vector.get(token, 0.0) for token, weight in query.items())
            # Prefer examples with the same answer type (enum vs decimal).
            if candidate.answer_spec["type"] == case.answer_spec["type"]:
                score += 0.05
            scored.append((score, candidate))
        scored.sort(key=lambda item: -item[0])
        return [candidate for _, candidate in scored[:k]]
