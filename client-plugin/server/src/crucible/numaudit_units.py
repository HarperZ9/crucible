"""Paired unit restatements: "<number> <unit> or about <number> <other unit>".

The second figure must be the first converted. Units with two common definitions (US and
imperial gallons; short, long and metric tons; mechanical and metric horsepower) pass if any
definition fits. Tolerance: 12% for ordinary units, and for temperature the larger of 6% of the
Fahrenheit value or 5 degrees, which allows the rounding speech uses ("about 250 F" for 248 F).
"""
from __future__ import annotations

import re

from crucible.numaudit import Finding, excerpt, num_re, value

# (pattern, dimension, factors to SI). Longer phrases come first so they win the alternation.
UNITS = [
    (r"square kilomet(?:er|re)s?|sq\.? ?km|km2", "area", (1e6,)),
    (r"square nautical miles?", "area", (3.4299e6,)),
    (r"square miles?|sq\.? ?mi", "area", (2.58999e6,)),
    (r"square met(?:er|re)s?", "area", (1.0,)),
    (r"square (?:feet|foot)", "area", (0.092903,)),
    (r"hectares?", "area", (1e4,)),
    (r"acres?", "area", (4046.86,)),
    (r"kilomet(?:er|re)s? (?:per|an|a) hour|km/h|kph", "speed", (0.277778,)),
    (r"miles (?:per|an|a) hour|mph", "speed", (0.44704,)),
    (r"met(?:er|re)s? (?:per|a) second|m/s", "speed", (1.0,)),
    (r"knots", "speed", (0.514444,)),
    (r"newton[- ]met(?:er|re)s?", "torque", (1.0,)),
    (r"pound[- ]f(?:ee|oo)t|lb[- ]?ft|foot[- ]pounds?", "torque", (1.35582,)),
    (r"cubic met(?:er|re)s?", "volume", (1.0,)),
    (r"lit(?:er|re)s?", "volume", (1e-3,)),
    (r"gallons?", "volume", (3.78541e-3, 4.54609e-3)),
    (r"nautical miles?", "length", (1852.0,)),
    (r"kilomet(?:er|re)s?|km", "length", (1e3,)),
    (r"centimet(?:er|re)s?|cm", "length", (1e-2,)),
    (r"millimet(?:er|re)s?|mm", "length", (1e-3,)),
    (r"microns?|micromet(?:er|re)s?", "length", (1e-6,)),
    (r"met(?:er|re)s?", "length", (1.0,)),
    (r"miles?", "length", (1609.344,)),
    (r"yards?", "length", (0.9144,)),
    (r"feet|foot|ft", "length", (0.3048,)),
    (r"inch(?:es)?", "length", (0.0254,)),
    (r"kilograms?|kg", "mass", (1.0,)),
    (r"tonnes?", "mass", (1e3,)),
    (r"tons?", "mass", (907.185, 1016.05, 1e3)),
    (r"pounds?|lbs?", "mass", (0.453592,)),
    (r"ounces?|oz", "mass", (0.0283495,)),
    (r"grams?", "mass", (1e-3,)),
    (r"megawatts?|MW", "power", (1e6,)),
    (r"kilowatts?|kW", "power", (1e3,)),
    (r"horsepower|hp", "power", (745.7, 735.5)),
    (r"watts?", "power", (1.0,)),
    (r"psi", "pressure", (6894.76,)),
    (r"kilopascals?|kPa", "pressure", (1e3,)),
    (r"megapascals?|MPa", "pressure", (1e6,)),
    (r"bar", "pressure", (1e5,)),
    (r"atmospheres?", "pressure", (101325.0,)),
]
TEMP_C = r"degrees? (?:celsius|centigrade|c)\b|celsius|centigrade"
TEMP_F = r"degrees? (?:fahrenheit|f)\b|fahrenheit"
UNIT_ALT = "|".join(f"(?:{p})" for p, _, _ in UNITS)
CONNECT = (r"\s*,?\s*(?:or|\()\s*(?:about|around|roughly|nearly|almost|approximately|some|just over|"
           r"just under|over|under|close to|more than|less than)?\s*")
PAIR = re.compile(num_re("a") + r"\s*(?P<ua>" + TEMP_C + "|" + TEMP_F + "|" + UNIT_ALT + r")\b" + CONNECT
                  + num_re("b") + r"\s*(?P<ub>" + TEMP_C + "|" + TEMP_F + "|" + UNIT_ALT + r")\b", re.I)


def _lookup(unit: str):
    for p, dim, factors in UNITS:
        if re.fullmatch(p, unit, re.I):
            return dim, factors
    if re.fullmatch(TEMP_C, unit, re.I):
        return "tempC", None
    if re.fullmatch(TEMP_F, unit, re.I):
        return "tempF", None
    return None, None


def _check_temp(a: float, da: str, b: float) -> tuple[bool, float]:
    expect = a * 9 / 5 + 32 if da == "tempC" else (a - 32) * 5 / 9
    tol = max(0.06 * abs(expect), 5.0) if da == "tempC" else max(0.06 * abs(expect), 3.0)
    return abs(b - expect) <= tol, expect


def _check_units(a: float, fa: tuple, b: float, fb: tuple) -> tuple[bool, float]:
    best = None
    for x in fa:
        for y in fb:
            expect = a * x / y
            ok = abs(b - expect) <= 0.12 * abs(expect)
            if ok:
                return True, expect
            if best is None or abs(b - expect) < abs(b - best):
                best = expect
    return False, best


_ONE = r"(?P<{u}>" + TEMP_C + "|" + TEMP_F + "|" + UNIT_ALT + r")\b"
RANGE = re.compile(num_re("a") + r"\s*" + _ONE.format(u="ua") + r"\s+to\s+" + num_re("b") + r"\s*" + _ONE.format(u="ub")
                   + CONNECT + num_re("c") + r"\s*" + _ONE.format(u="uc") + r"\s+to\s+" + num_re("d") + r"\s*"
                   + _ONE.format(u="ud"), re.I)


def _ranges(t: str):
    """'A u to B u or about C v to D v' yields the pairs (A, C) and (B, D)."""
    for m in RANGE.finditer(t):
        yield m, (value(m, "a"), m.group("ua"), value(m, "c"), m.group("uc"), m.group("a"))
        yield m, (value(m, "b"), m.group("ub"), value(m, "d"), m.group("ud"), m.group("b"))


def _second_reading(t, m, a, a_raw, b, da, fa, fb, temps, in_range):
    """Captions drop minus signs and split numbers ("9 60 km"). If such a reading passes, the
    finding is marked ambiguous rather than dropped: the text as written still fails."""
    if temps and in_range and _check_temp(-a, da, -b)[0]:
        return "ambiguous", "; fits if both minus signs were dropped"
    prev = re.search(r"(\d+) $", t[max(0, m.start() - 6): m.start()])
    if prev and a_raw.isdigit():
        joined = float(prev.group(1) + a_raw)
        ok = _check_temp(joined, da, b)[0] if temps else _check_units(joined, fa, b, fb)[0]
        if ok:
            return "ambiguous", f"; fits if the split number reads {joined:g}"
    return "flag", ""


def _check_pair(t, m, a, ua, b, ub, a_raw, in_range):
    da, fa = _lookup(ua)
    db, fb = _lookup(ub)
    if da is None or db is None:
        return None
    temps = {da, db} == {"tempC", "tempF"}
    if not temps and (da != db or fa == fb):
        return None  # different dimensions, or the same unit twice: not a restatement
    ok, expect = _check_temp(a, da, b) if temps else _check_units(a, fa, b, fb)
    if ok:
        return None
    sev, why = _second_reading(t, m, a, a_raw, b, da, fa, fb, temps, in_range)
    return Finding("unit_pair", m.start(), excerpt(t, m.start(), m.end()), b, round(expect, 4),
                   "max(6%, 5 F)" if temps else "12%",
                   note=f"{a:g} {ua} converts to about {expect:.4g} {ub}" + why, severity=sev)


def unit_pairs(t: str) -> list[Finding]:
    out, spans = [], []
    for m, (a, ua, b, ub, raw) in _ranges(t):
        spans.append((m.start(), m.end()))
        f = _check_pair(t, m, a, ua, b, ub, raw, True)
        if f:
            out.append(f)
    for m in PAIR.finditer(t):
        if any(s <= m.start() < e for s, e in spans):
            continue
        f = _check_pair(t, m, value(m, "a"), m.group("ua"), value(m, "b"), m.group("ub"), m.group("a"), False)
        if f:
            out.append(f)
    return out
