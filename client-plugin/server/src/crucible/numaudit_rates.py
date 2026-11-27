"""Number audit rules for rates and sensors: data rate from pixels and frame rate, ground sample
distance from pixels and field width, fuel endurance from load and burn rate, and the direction of
a stated trend between two dated values."""
from __future__ import annotations

import math
import re

from crucible.numaudit import Finding, excerpt, num_re, outside, value

BYTES = {"tera": 1e12, "giga": 1e9, "mega": 1e6, "tb": 1e12, "gb": 1e9, "mb": 1e6}
PIXELS = {"giga": 1e9, "mega": 1e6}
FUEL_DENSITY = (0.70, 1.45)  # kg per litre, gasoline to concentrated hydrogen peroxide
MASS_KG = {"lb": 0.453592, "pound": 0.453592, "kilogram": 1.0, "kg": 1.0}
VOL_L = {"gallon": 3.78541, "lit": 1.0}


def _pixels(back: str):
    px = [value(x, "p") * PIXELS[x.group("pu").lower()]
          for x in re.finditer(num_re("p") + r"\s*(?P<pu>giga|mega)[- ]?pixels?", back, re.I)]
    return max(px) if px else None  # the whole sensor, not one of its tiles


def data_rate(t: str) -> list[Finding]:
    """Bytes per second over pixels per second gives bytes per pixel; outside 0.05 to 16 is flagged."""
    out = []
    pat = re.compile(num_re("x") + r"\s*(?P<bu>tera|giga|mega)bytes?\s+(?:of [\w ]{0,30}?)?(?:every|per|a|each) second", re.I)
    for m in pat.finditer(t):
        back = t[max(0, m.start() - 900): m.start()]
        px = _pixels(back)
        fps = list(re.finditer(num_re("f") + r"\s*(?:frames (?:a|per) second|fps)", t[max(0, m.start() - 300): m.end() + 100], re.I))
        if not px or not fps:
            continue
        rate = value(m, "x") * BYTES[m.group("bu").lower()]
        bpp = rate / (px * value(fps[-1], "f"))
        if bpp < 0.05 or bpp > 16:
            out.append(Finding("data_rate", m.start(), excerpt(t, m.start() - 100, m.end()), rate,
                               round(px * value(fps[-1], "f") * 3, 1), "0.05 to 16 bytes per pixel",
                               note=f"{bpp:.3g} bytes per pixel; 3 bytes per pixel would give {px * value(fps[-1], 'f') * 3:.3g} B/s"))
    return out


def ground_sample(t: str) -> list[Finding]:
    """Field width over the side of a square frame gives the ground covered by one pixel."""
    out = []
    pat = re.compile(r"pixel[\w ]{0,40}?(?:down to|resolve|resolution of|of)\s+(?:just\s+|about\s+|around\s+)?"
                     + num_re("g") + r"\s*(?P<gu>millimet\w*|mm|centimet\w*|cm|met(?:er|re)s?|inch\w*|feet)", re.I)
    for m in pat.finditer(t):
        back = t[max(0, m.start() - 600): m.start()]
        px = _pixels(back)
        width = list(re.finditer(r"(?:field of view|swath|width|wide)[\w ]{0,30}?" + num_re("w")
                                 + r"\s*(?P<wu>kilomet\w*|km|miles?)", back, re.I))
        if not px or not width:
            continue
        w_m = value(width[-1], "w") * (1609.344 if width[-1].group("wu").lower().startswith("mile") else 1000.0)
        gu = m.group("gu").lower()
        unit = 1e-3 if gu.startswith(("mm", "milli")) else 1e-2 if gu.startswith(("cm", "centi")) else \
            0.0254 if gu.startswith("inch") else 0.3048 if gu == "feet" else 1.0
        stated = value(m, "g") * unit
        expect = w_m / math.sqrt(px)
        if outside(stated, expect, 3.0):
            out.append(Finding("ground_sample", m.start(), excerpt(t, m.start() - 60, m.end()), stated, round(expect, 4),
                               "factor 3", note=f"{w_m:g} m across sqrt({px:.3g}) pixels is {expect:.3g} m per pixel"))
    return out


def fuel_endurance(t: str) -> list[Finding]:
    """Fuel load over burn rate bounds the flight time; mass and volume meet through fuel density."""
    out = []
    pat = re.compile(num_re("a") + r"\s*(?P<au>lb|pounds?|kilograms?|kg|gallons?|lit(?:er|re)s?)\s+of\s+(?:[\w-]+\s+){0,3}?"
                     r"(?:fuel|propellant|peroxide|kerosene|gasoline|petrol)", re.I)
    for m in pat.finditer(t):
        fwd = t[m.end(): m.end() + 250]
        rate = re.search(r"(?:(?P<one>an?|one)|" + num_re("r") + r")\s*(?P<ru>gallons?|lit(?:er|re)s?|lb|pounds?|kg|kilograms?)\s*(?:a|per|each) minute", fwd, re.I)
        dur = re.search(num_re("d") + r"\s*minutes?", fwd[rate.end():] if rate else "", re.I)
        if not rate or not dur:
            continue
        r_val = 1.0 if rate.group("one") else value(rate, "r")
        lo, hi = _endurance_min(value(m, "a"), m.group("au"), r_val, rate.group("ru"))
        stated = value(dur, "d")
        if stated > 2 * hi or stated < 0.5 * lo:
            out.append(Finding("fuel_endurance", m.start(), excerpt(t, m.start(), m.end() + rate.end() + dur.end()),
                               stated, round(hi, 3), "within 0.5x to 2x of load / rate",
                               note=f"load over rate gives {lo:.3g} to {hi:.3g} minutes"))
    return out


def _endurance_min(amount, au, rate, ru):
    def kind(u):
        u = u.lower()
        return ("mass", next(v for k, v in MASS_KG.items() if u.startswith(k))) if any(u.startswith(k) for k in MASS_KG) \
            else ("vol", next(v for k, v in VOL_L.items() if u.startswith(k)))
    (ka, fa), (kr, fr) = kind(au), kind(ru)
    a, r = amount * fa, rate * fr
    if ka == kr:
        return a / r, a / r
    vals = [(a / d) / r if ka == "mass" else (a * d) / r for d in FUEL_DENSITY]
    return min(vals), max(vals)


def trend_direction(t: str) -> list[Finding]:
    """'It takes X now; a decade earlier it took only Y': with a stated rise, Y must be below X."""
    out = []
    for m in re.finditer(r"(?:a decade|\d+ years|years|decades) (?:earlier|ago|before)|previously", t, re.I):
        before = list(re.finditer(num_re("x") + r"\s+(?P<nx>[a-z]+)", t[max(0, m.start() - 150): m.start()], re.I))
        after = re.search(r"(?P<only>only\s+)?(?:about\s+|around\s+|roughly\s+)?" + num_re("y") + r"\s+(?P<ny>[a-z]+)",
                          t[m.end(): m.end() + 120], re.I)
        if not before or not after or before[-1].group("nx").lower() != after.group("ny").lower():
            continue
        win = t[max(0, m.start() - 250): m.end() + 250].lower()
        rise = re.search(r"\b(rise|increase|grew|growth|harder|rising|more)\b", win)
        x, y = value(before[-1], "x"), value(after, "y")
        if y > x and (after.group("only") or rise):
            why = "'only' on the larger figure" if after.group("only") else "a stated rise"
            out.append(Finding("trend_direction", m.start(), excerpt(t, m.start() - 120, m.end() + 120), y, x,
                               "earlier value below current", note=f"earlier {y:g} exceeds current {x:g} despite {why}"))
    return out
