"""Route a question to a known train template, or mark it as hidden (unseen template).

Two keys:
- spec signature: canonical JSON of answer_spec + trace_spec. Fixed within a template (the
  official scorer enforces this). On test, exactly 580 questions match a train signature, which
  equals the official seen-stratum size, so "signature known" == "seen template".
- text skeleton: question body with numbers masked. Used to pick among the few templates that
  share a signature.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from difflib import SequenceMatcher

from .io import Case

_NUMBER_MASK = re.compile(r"-?\d[\d,]*(?:\.\d+)?(?:/\d+)?")


def signature(case: Case) -> str:
    return json.dumps([case.answer_spec, case.question["trace_spec"]], sort_keys=True)


def skeleton(case: Case) -> str:
    return _NUMBER_MASK.sub("#", case.body)


class TemplateIndex:
    def __init__(self, labelled: list[Case]):
        self.by_signature: dict[str, set[str]] = defaultdict(set)
        self.skeletons: dict[str, set[str]] = defaultdict(set)
        self.cases: dict[str, list[Case]] = defaultdict(list)
        for case in labelled:
            template = case.template_id
            assert template, "labelled cases need a manifest"
            self.by_signature[signature(case)].add(template)
            self.skeletons[template].add(skeleton(case))
            self.cases[template].append(case)

    def route(self, case: Case) -> str | None:
        """Template id for a seen-template question, else None."""
        candidates = self.by_signature.get(signature(case))
        if not candidates:
            return None
        if len(candidates) == 1:
            return next(iter(candidates))
        text = skeleton(case)
        for template in candidates:
            if text in self.skeletons[template]:
                return template
        return max(candidates, key=lambda t: self._similarity(text, t))

    def _similarity(self, text: str, template: str) -> float:
        return max(SequenceMatcher(None, text, known).ratio() for known in self.skeletons[template])
