"""Number audit: recompute stated figures from the inputs stated beside them.

A transcript, paper or page often states a figure together with the numbers it should follow
from: "140 C or about 220 F", "a 1 mm pitch divided into 20 parts reads 1/500 mm", "1.8 gigapixels
over 16 km resolve 2 mm". The audit finds those local groups, recomputes the figure with a fixed
rule, and reports each group whose stated value falls outside the rule's tolerance.

It checks internal arithmetic only. A figure that is wrong but consistent with its neighbours
passes; a figure with no stated inputs is never checked. Every finding carries the rule, the
excerpt, the stated value, the recomputed value and the tolerance, so a reader can redo it.

Text is normalised first: line breaks joined, thousands separators removed ("37,000" and the
caption form "4 500"), and a small set of number words read ("a hundred", "one", "two").
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

SCALE = {"thousand": 1e3, "million": 1e6, "billion": 1e9, "trillion": 1e12}
WORDS = {"a": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
         "nine": 9, "ten": 10, "twelve": 12, "fifteen": 15, "twenty": 20, "fifty": 50, "a hundred": 100,
         "one hundred": 100, "a thousand": 1000}
_WORD_ALT = "|".join(sorted((re.escape(w) for w in WORDS if w != "a"), key=len, reverse=True))
NUM = (r"(?P<{n}>\d+(?:\.\d+)?|" + _WORD_ALT + r")(?:\s*(?P<{n}s>thousand|million|billion|trillion))?")


def num_re(name: str) -> str:
    """A named number group, digits or a number word, with an optional scale word."""
    return NUM.format(n=name)


def value(m: re.Match, name: str) -> float:
    raw = m.group(name).lower()
    v = float(WORDS[raw]) if raw in WORDS else float(raw)
    scale = m.groupdict().get(name + "s")
    return v * SCALE[scale.lower()] if scale else v


def normalise(text: str) -> str:
    t = re.sub(r"\s+", " ", text)
    t = re.sub(r"(?<=\d),(?=\d{3}\b)", "", t)
    t = re.sub(r"(?<![\d.])(\d{1,3}) (\d{3})(?![\d.])", r"\1\2", t)  # caption thousands: "4 500"
    t = re.sub(r"(\d)\s*°\s*([CF])\b", r"\1 degrees \2", t)
    return t


@dataclass
class Finding:
    rule: str
    offset: int
    excerpt: str
    stated: float
    recomputed: float
    tolerance: str
    note: str = ""
    severity: str = "flag"  # "flag", or "ambiguous" when a second reading of the text would pass
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def excerpt(text: str, start: int, end: int, pad: int = 40) -> str:
    return text[max(0, start - pad): min(len(text), end + pad)].strip()


def outside(stated: float, recomputed: float, factor: float) -> bool:
    """True when stated and recomputed differ by more than a multiplicative factor."""
    if stated <= 0 or recomputed <= 0:
        return stated != recomputed
    r = stated / recomputed
    return r > factor or r < 1 / factor


def audit(text: str) -> list[Finding]:
    from crucible.numaudit_rules import RULES
    from crucible.numaudit_units import unit_pairs
    t = normalise(text)
    found = unit_pairs(t)
    for rule in RULES:
        found.extend(rule(t))
    found.sort(key=lambda f: f.offset)
    return found


def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))
