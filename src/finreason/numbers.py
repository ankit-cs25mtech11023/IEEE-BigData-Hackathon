"""Extract numeric literals from question text as exact Fractions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction

# A number is a standalone token: optional sign, digits with optional thousands commas
# or a decimal part, optionally followed by "/denominator" (question text uses rationals like 1975/28).
_NUMBER = re.compile(
    r"""
    (?<![A-Za-z0-9_.])                 # not glued to an identifier or another number (CO2e, d1, w1)
    (?<![A-Za-z0-9]-)                  # not a hyphenated label ("Year-1", "Tier-2")
    (?P<sign>-)?
    (?P<int>\d{1,3}(?:,\d{3})+|\d+)
    (?P<frac>\.\d+)?
    (?:/(?P<den>\d+(?:\.\d+)?)(?![\d.]*[A-Za-z]))?
    (?![A-Za-z0-9_])                   # not followed by letters (2nd, 10x is rare; keep strict)
    """,
    re.VERBOSE,
)


@dataclass(frozen=True)
class NumberToken:
    value: Fraction
    text: str
    start: int
    end: int


def parse_number(text: str) -> Fraction:
    """Parse '1,200', '-3.5', '1975/28' exactly."""
    text = text.replace(",", "").strip()
    if "/" in text:
        numerator, denominator = text.split("/", 1)
        return Fraction(Decimal(numerator)) / Fraction(Decimal(denominator))
    return Fraction(Decimal(text))


def number_tokens(text: str) -> list[NumberToken]:
    tokens = []
    for match in _NUMBER.finditer(text):
        raw = match.group(0)
        if match.group("sign") and match.start() > 0 and text[match.start() - 1].isalnum():
            continue
        tokens.append(NumberToken(parse_number(raw), raw, match.start(), match.end()))
    return tokens


def numbers(text: str) -> list[Fraction]:
    """All standalone numbers in the text, in order of appearance."""
    return [token.value for token in number_tokens(text)]
