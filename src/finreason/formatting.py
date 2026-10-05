"""Render computed values into strings the official validator and scorer accept.

Rules (from the official contracts):
- decimal / half_up N: any finite decimal is accepted; we quantize half-up to N places ourselves.
- decimal / exact: terminating values must be finite decimals; non-terminating must be an
  irreducible "p/q" string.
- enum: value must be one of answer_spec["allowed_values"] (case-sensitive).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, localcontext
from fractions import Fraction
from typing import Any, Mapping


class FormatError(ValueError):
    pass


def to_fraction(value: Any) -> Fraction:
    if isinstance(value, bool):
        raise FormatError("boolean given for a numeric result")
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise FormatError(f"non-finite value {value}")
        return Fraction(value)
    if isinstance(value, float):
        # Floats are lossy; go through repr so 0.1 stays 1/10 instead of its binary expansion.
        if value != value or value in (float("inf"), float("-inf")):
            raise FormatError(f"non-finite value {value}")
        return Fraction(Decimal(repr(value)))
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if "/" in text:
            numerator, denominator = text.split("/", 1)
            return Fraction(Decimal(numerator)) / Fraction(Decimal(denominator))
        return Fraction(Decimal(text))
    raise FormatError(f"cannot convert {type(value).__name__} to a number")


def _fraction_to_decimal_text(value: Fraction, places: int) -> str:
    with localcontext() as context:
        context.prec = 256
        decimal_value = Decimal(value.numerator) / Decimal(value.denominator)
        quantum = Decimal(1).scaleb(-places)
        rendered = format(decimal_value.quantize(quantum, rounding=ROUND_HALF_UP), "f")
    if rendered.startswith("-") and Decimal(rendered) == 0:
        rendered = rendered[1:]
    return rendered


def _is_terminating(denominator: int) -> bool:
    for prime in (2, 5):
        while denominator % prime == 0:
            denominator //= prime
    return denominator == 1


def render_exact(value: Fraction) -> str:
    if value == 0:
        return "0"
    if _is_terminating(value.denominator):
        with localcontext() as context:
            context.prec = 256
            text = format(Decimal(value.numerator) / Decimal(value.denominator), "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text
    return f"{value.numerator}/{value.denominator}"


def render_enum(value: Any, spec: Mapping[str, Any]) -> str:
    allowed = spec["allowed_values"]
    if isinstance(value, bool):
        candidate = "true" if value else "false"
    else:
        candidate = str(value).strip()
    if candidate in allowed:
        return candidate
    lowered = {item.lower(): item for item in allowed}
    if candidate.lower() in lowered:
        return lowered[candidate.lower()]
    raise FormatError(f"enum value {candidate!r} not in {allowed}")


def render(value: Any, spec: Mapping[str, Any]) -> str:
    """Render one final or slot value according to its result/answer spec."""
    if spec["type"] == "enum":
        return render_enum(value, spec)
    if spec["type"] != "decimal":
        raise FormatError(f"unsupported spec type {spec['type']!r}")
    number = to_fraction(value)
    rounding = spec["rounding"]
    if rounding["mode"] == "exact":
        return render_exact(number)
    if rounding["mode"] == "half_up":
        return _fraction_to_decimal_text(number, rounding["decimal_places"])
    raise FormatError(f"unsupported rounding mode {rounding['mode']!r}")
