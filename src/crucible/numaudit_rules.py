"""Number audit rules for mechanics and physics: speed multiples, screw and gear resolution,
thermal expansion, rim speed, and distances to named bodies. Each rule anchors on one phrase,
reads its inputs from a window around it, and recomputes the stated figure."""
from __future__ import annotations

import math
import re

from crucible.numaudit import Finding, excerpt, num_re, outside, value

C_LIGHT, C_SOUND = 299_792_458.0, 343.0
ALPHA = {"alumin": 23e-6, "steel": 12e-6, "iron": 11.8e-6, "brass": 19e-6, "copper": 17e-6,
         "titanium": 8.6e-6, "invar": 1.2e-6, "glass": 9e-6, "nickel": 13e-6, "lead": 29e-6}
LEN_M = {"mm": 1e-3, "millimet": 1e-3, "cm": 1e-2, "centimet": 1e-2, "met": 1.0, "m": 1.0,
         "micron": 1e-6, "micromet": 1e-6, "inch": 0.0254, "feet": 0.3048, "foot": 0.3048, "ft": 0.3048}
# Closest and farthest distance from Earth, km.
BODIES = {"moon": (356_500, 406_700), "lunar": (356_500, 406_700), "mars": (5.46e7, 4.01e8),
          "venus": (3.8e7, 2.61e8), "jupiter": (5.88e8, 9.68e8), "saturn": (1.2e9, 1.66e9), "sun": (1.47e8, 1.52e8)}


def _len_m(unit: str) -> float:
    u = unit.lower()
    for k in sorted(LEN_M, key=len, reverse=True):
        if u.startswith(k):
            return LEN_M[k]
    raise KeyError(unit)


def speed_multiple(t: str) -> list[Finding]:
    """'3 trillion meters per second or about 10 million times faster than light'."""
    speeds = {"met": 1.0, "m/s": 1.0, "kilomet": 1e3, "km/s": 1e3, "miles per second": 1609.344}
    pat = re.compile(num_re("v") + r"\s*(?P<u>met(?:er|re)s? per second|m/s|kilomet(?:er|re)s? per second|km/s|"
                     r"miles per second)[^.]{0,60}?" + num_re("n") +
                     r"\s*times (?:faster than |the speed of |as fast as )?(?P<ref>light|sound)", re.I)
    out = []
    for m in pat.finditer(t):
        u = m.group("u").lower()
        si = next(f for k, f in speeds.items() if u.startswith(k))
        ratio = value(m, "v") * si / (C_LIGHT if m.group("ref").lower() == "light" else C_SOUND)
        if outside(value(m, "n"), ratio, 2.0):
            out.append(Finding("speed_multiple", m.start(), excerpt(t, m.start(), m.end()), value(m, "n"),
                               round(ratio, 4), "factor 2", note=f"the stated speed is {ratio:.4g} times {m.group('ref')}"))
    return out


_RES = re.compile(r"(?:(?P<frac>1/(?P<den>\d+))|(?P<num>\d+)\s*ths?|(?P<one>(?:1|one|a) )?(?P<word>hundredth|"
                  r"thousandth|ten thousandth|hundred thousandth|millionth))\s+of an? (?P<u>inch|millimet\w*|mm)", re.I)
_WORDDEN = {"hundredth": 1e2, "thousandth": 1e3, "ten thousandth": 1e4, "hundred thousandth": 1e5, "millionth": 1e6}


def screw_resolution(t: str) -> list[Finding]:
    """Pitch divided by thimble divisions (times any worm reduction) must give the stated reading."""
    out = []
    for m in re.finditer(r"(?:divided into|carrying|with) (?P<n>\d+) (?:parts|divisions|graduations)", t, re.I):
        back = t[max(0, m.start() - 250): m.start()]
        pitch = None
        for pm in re.finditer(r"pitch of (?P<p>\d+(?:\.\d+)?) ?(?P<u>mm|millimet\w*|inch\w*)", back, re.I):
            pitch = (float(pm.group("p")), "mm" if pm.group("u").lower().startswith("m") else "inch")
        for pm in re.finditer(r"(?P<tpi>\d+) threads (?:per|to the|an) inch", back, re.I):
            pitch = (1.0 / float(pm.group("tpi")), "inch")
        res = _RES.search(t, m.end(), m.end() + 150)
        if not pitch or not res:
            continue
        worm = re.findall(r"worm(?: wheel)? (?:of|with) (\d+) teeth", back, re.I)
        divs = float(m.group("n")) * (float(worm[-1]) if worm else 1.0)
        den = (float(res.group("den")) if res.group("frac") else float(res.group("num")) if res.group("num")
               else _WORDDEN[res.group("word").lower()])
        stated_u = "mm" if res.group("u").lower().startswith("m") else "inch"
        stated = (1.0 / den) * (1.0 if stated_u == pitch[1] else (25.4 if stated_u == "inch" else 1 / 25.4))
        expect = pitch[0] / divs
        if outside(stated, expect, 1.05):
            out.append(Finding("screw_resolution", m.start(), excerpt(t, m.start() - 120, res.end()),
                               stated, round(expect, 8), "5%",
                               note=f"pitch {pitch[0]:g} {pitch[1]} / {divs:g} divisions = {expect:.4g} {pitch[1]}"))
    return out


def thermal_expansion(t: str) -> list[Finding]:
    """alpha * length * temperature rise must give the stated growth."""
    out = []
    pat = re.compile(r"(?:expand|grow|lengthen)\w*\s+(?:by\s+|up to\s+|about\s+|around\s+)*" + num_re("d")
                     + r"\s*(?P<du>microns?|micromet\w+|mm|millimet\w+)", re.I)
    for m in pat.finditer(t):
        back = t[max(0, m.start() - 200): m.start()].lower()
        mat = next((k for k in ALPHA if k in back), None)
        ln = list(re.finditer(r"length of " + num_re("l") + r"\s*(?P<lu>mm|millimet\w*|cm|centimet\w*|met\w*)", back))
        fwd = t[m.end(): m.end() + 120]
        hot = re.search(r"heated (?P<k>to|by) " + num_re("tt") + r"\s*degrees", fwd, re.I)
        if not (mat and ln and hot):
            continue
        L = value(ln[-1], "l") * _len_m(ln[-1].group("lu"))
        rise = value(hot, "tt") - (20.0 if hot.group("k").lower() == "to" else 0.0)
        expect = ALPHA[mat] * L * rise
        stated = value(m, "d") * _len_m(m.group("du"))
        if rise > 0 and outside(stated, expect, 1.5):
            implied = stated / (ALPHA[mat] * L)
            out.append(Finding("thermal_expansion", m.start(), excerpt(t, m.start() - 120, m.end() + hot.end()),
                               stated, expect, "factor 1.5",
                               note=f"{mat} alpha {ALPHA[mat]:g}/K over {L:g} m and {rise:g} K; stated growth fits {implied:.3g} K",
                               extra={"implied_rise_K": round(implied, 2)}))
    return out


def rim_speed(t: str) -> list[Finding]:
    """'N times the speed of sound' for a spinning rotor, from its size and rpm (or energy and mass)."""
    out = []
    for m in re.finditer(r"(?P<q>over |about |nearly |almost )?" + num_re("n") + r"\s*times the speed of sound", t, re.I):
        back = t[max(0, m.start() - 500): m.start()]
        rpm = list(re.finditer(num_re("r") + r"\s*rpm", back, re.I))
        size = list(re.finditer(num_re("s") + r"\s*(?P<su>met(?:er|re)s?|feet|foot|centimet\w*|cm|inch\w*)\b"
                                r"(?P<lab> in diameter| diameter| radius| across| wide)?", back, re.I))
        if not rpm or not size:
            continue
        w = value(rpm[-1], "r") * 2 * math.pi / 60
        energy = re.findall(r"(\d+(?:\.\d+)?)\s*(?:kilowatt[- ]hours?|kWh)", back, re.I)
        mass = re.findall(r"(\d+(?:\.\d+)?|hundred)\s*(?:kilograms?|kg)", back, re.I)
        stated, sev, note = value(m, "n"), "flag", ""
        if energy and mass:
            mm = 100.0 if mass[-1] == "hundred" else float(mass[-1])
            r = math.sqrt(4 * float(energy[-1]) * 3.6e6 / (mm * w * w))
            note = f"radius {r:.3g} m solved from {energy[-1]} kWh in a {mm:g} kg solid disc"
        else:
            s = value(size[-1], "s") * _len_m(size[-1].group("su"))
            r = s if (size[-1].group("lab") or "").strip() == "radius" else s / 2
            note = f"size {s:g} m read as {'radius' if r == s else 'diameter'}"
            if r != s and not outside(stated, w * s / C_SOUND, 1.3):
                sev = "ambiguous"
        mach = w * r / C_SOUND
        if outside(stated, mach, 1.3):
            out.append(Finding("rim_speed", m.start(), excerpt(t, rpm[-1].start() + max(0, m.start() - 500), m.end()),
                               stated, round(mach, 3), "factor 1.3", note=note + f"; rim speed {w * r:.0f} m/s", severity=sev))
    return out


def reference_distance(t: str) -> list[Finding]:
    """A journey to a named body must be at least of the order of its distance from Earth."""
    out = []
    pat = re.compile(num_re("d") + r"\s*(?P<u>miles?|kilomet(?:er|re)s?|km)\s+(?:journey|trip|voyage|flight|cruise|transit)", re.I)
    for m in pat.finditer(t):
        win = t[max(0, m.start() - 300): m.end() + 100].lower()
        hits = [(abs(i.start() - 300), b) for b in BODIES for i in re.finditer(r"\b" + b + r"\b", win)]
        if not hits:
            continue
        body = min(hits)[1]
        km = value(m, "d") * (1.609344 if m.group("u").lower().startswith("mile") else 1.0)
        lo, hi = BODIES[body]
        if km < lo / 2 or km > hi * 4:
            out.append(Finding("reference_distance", m.start(), excerpt(t, m.start(), m.end()), km, lo,
                               "from half the closest to 4x the farthest distance",
                               note=f"{body} is {lo:.3g} to {hi:.3g} km from Earth"))
    return out


def _rules():
    from crucible.numaudit_rates import (
        data_rate,
        fuel_endurance,
        ground_sample,
        trend_direction,
    )
    return [speed_multiple, screw_resolution, thermal_expansion, rim_speed, reference_distance,
            data_rate, ground_sample, fuel_endurance, trend_direction]


RULES = _rules()
