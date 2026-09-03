"""Whether docs/art/verdict-ladder.svg is true of src/crucible/verdict.py.

tests/test_repo_art.py settles a different question: that the card fits its
columns and matches its spec byte for byte. A card can pass every check over
there and still describe a function that does something else, because nothing
in that file ever calls the function.

So every row drawn on the card is driven here. A row's key names a condition,
its value names the verdict the card claims comes back, and each test below
builds the condition and holds the real return against the drawn one. The card
also claims an ORDER, which is the part a row-by-row check would miss: a
measurement that trips two rungs at once has to stop at the higher one.

Claims and measurements are built by hand rather than loaded from a fixture,
because a fixture is one more thing that can drift from the drawing.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from crucible.claim import make_claim  # noqa: E402
from crucible.verdict import Measurement, verdict_for  # noqa: E402

CARD = next(
    card for card in json.loads(
        (ROOT / "docs" / "art" / "crucible.art.json").read_text("utf-8")
    )["cards"] if card["file"] == "verdict-ladder.svg")
ROWS = {field["key"]: field for field in CARD["fields"]}
DRAWN_ORDER = [field["key"] for field in CARD["fields"]]

# A claim that sealed a tolerance, one that did not, and one nothing could
# refute. Between them they reach every rung.
SEALED = make_claim("p95 stays under 200ms", "p95 over 200ms", tolerance=0.05)
UNSEALED = make_claim("p95 stays under 200ms", "p95 over 200ms")
UNTESTABLE = make_claim("the design is elegant", "")


def measured(claim, deviation, tolerance=0.05, binds_to=None):
    """One measurement row, shaped the way a runner writes it."""
    return Measurement(claim.id, binds_to or claim.sha256, deviation,
                       tolerance, "replay", 0.0)


# Keyed by the row it belongs to. Each entry builds the condition that row
# names, and nothing else.
CONDITIONS = {
    "no falsification": lambda: (UNTESTABLE, measured(UNTESTABLE, 0.01)),
    "no measurement": lambda: (SEALED, None),
    "binds to another claim": lambda: (
        SEALED, measured(SEALED, 0.01, binds_to="0" * 64)),
    "deviation not a number": lambda: (SEALED, measured(SEALED, None)),
    "tolerance widened": lambda: (
        SEALED, measured(SEALED, 0.01, tolerance=0.10)),
    "within tolerance": lambda: (SEALED, measured(SEALED, 0.01)),
    "over tolerance": lambda: (SEALED, measured(SEALED, 0.09)),
}


def test_every_row_the_card_draws_is_reached_by_something_here():
    """A row added to the spec and to nothing else would otherwise ship
    undriven, which is the failure this file exists to stop."""
    assert sorted(ROWS) == sorted(CONDITIONS), \
        "a drawn row has no case, or a case draws no row"


@pytest.mark.parametrize("key", sorted(CONDITIONS))
def test_each_row_returns_the_verdict_it_draws(key):
    claim, measurement = CONDITIONS[key]()
    assert verdict_for(claim, measurement).status == ROWS[key]["value"], key


@pytest.mark.parametrize("deviation,tolerance", [
    (None, 0.05), (-1.0, 0.05), (float("inf"), 0.05), (float("nan"), 0.05),
    (0.01, 0.0), (0.01, None), (0.01, -0.05),
])
def test_the_not_a_number_row_covers_every_shape_its_note_lists(deviation,
                                                                tolerance):
    """The note under that row lists None, infinite, negative, and a tolerance
    at zero. Each is a separate branch, and drawing one row for the set is
    only honest if they all land on the same rung."""
    verdict = verdict_for(SEALED, measured(SEALED, deviation, tolerance))
    assert verdict.status == "UNVERIFIABLE"
    assert verdict.margin is None


def test_the_marked_row_is_the_only_one_a_claim_stands_on():
    """The mark claims MATCH is where a claim holds. No other row may be
    marked, and no other condition may come back MATCH."""
    marked = [key for key, field in ROWS.items()
              if field.get("tone", "none") != "none"]
    assert marked == ["within tolerance"]
    for key, build in CONDITIONS.items():
        stands = verdict_for(*build()).status == "MATCH"
        assert stands == (key == "within tolerance"), key


def test_a_margin_comes_back_only_where_the_card_says_a_number_was_compared():
    """A margin on an UNVERIFIABLE row would read as a measurement that was
    taken, which is the thing UNVERIFIABLE exists to deny."""
    for key, build in CONDITIONS.items():
        margin = verdict_for(*build()).margin
        assert (margin is None) == (ROWS[key]["value"] == "UNVERIFIABLE"), key
    assert verdict_for(SEALED, measured(SEALED, 0.01)).margin == \
        pytest.approx(0.8)
    assert verdict_for(SEALED, measured(SEALED, 0.09)).margin == \
        pytest.approx(-0.8)


# A condition that trips the named row and something below it. The row named
# has to win, or the drawn order is wrong. "no measurement" is absent on
# purpose: every rung below it needs a measurement to reach, so no condition
# can trip it and a lower one together.
TWO_AT_ONCE = {
    "no falsification": (UNTESTABLE, None),
    "binds to another claim": (SEALED, measured(SEALED, None,
                                                binds_to="0" * 64)),
    "deviation not a number": (SEALED, measured(SEALED, None,
                                                tolerance=0.10)),
    "tolerance widened": (SEALED, measured(SEALED, 0.09, tolerance=0.10)),
}


@pytest.mark.parametrize("key", sorted(TWO_AT_ONCE))
def test_a_condition_that_trips_two_rungs_stops_at_the_higher_one(key):
    """This is the claim the card's title makes. Without it the drawing is a
    set of independent facts that happen to be listed in some sequence."""
    grounds = verdict_for(*TWO_AT_ONCE[key]).grounds
    assert grounds == verdict_for(*CONDITIONS[key]()).grounds, (
        f"a measurement tripping {key} and a lower rung stopped lower: "
        f"{grounds!r}")


def test_a_row_drawn_in_the_wrong_place_would_be_caught():
    """A control. Swap two rows on a copy of the spec and count the rows that
    stop agreeing with the function. A green suite otherwise proves only that
    these checks ran."""
    swapped = {key: dict(field) for key, field in ROWS.items()}
    swapped["within tolerance"]["value"] = ROWS["over tolerance"]["value"]
    swapped["over tolerance"]["value"] = ROWS["within tolerance"]["value"]
    wrong = [key for key, build in CONDITIONS.items()
             if verdict_for(*build()).status != swapped[key]["value"]]
    assert sorted(wrong) == ["over tolerance", "within tolerance"]


def test_an_unsealed_claim_is_the_reason_the_widened_row_is_about_the_seal():
    """The row says widened, not mismatched. A claim that sealed no tolerance
    accepts the tolerance the measurement carries, so the rung is about the
    seal rather than about tolerances disagreeing."""
    assert verdict_for(UNSEALED, measured(UNSEALED, 0.01,
                                          tolerance=0.10)).status == "MATCH"
    assert verdict_for(SEALED, measured(SEALED, 0.01,
                                        tolerance=0.10)).status == \
        "UNVERIFIABLE"


def test_the_footnote_claim_that_the_function_holds_no_model():
    """Drawn as fact in the footnote, so it is checked here: the same record
    gives the same verdict every time, with nothing else consulted."""
    claim, measurement = CONDITIONS["within tolerance"]()
    first = verdict_for(claim, measurement)
    assert first == verdict_for(claim, measurement)
    assert first.grounds == verdict_for(
        make_claim(claim.text, claim.falsification, tolerance=claim.tolerance),
        measurement).grounds


def test_the_command_the_card_cites_can_be_run():
    """The source line under the title is an instruction to the reader, and a
    reader who runs it and gets an error learns the card is decoration."""
    command = CARD["source"]
    assert command.startswith('python -c "')
    result = subprocess.run(
        [sys.executable, "-c", command.split('"')[1]],
        capture_output=True, text=True, cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")})
    assert result.returncode == 0, result.stderr
    assert "falsification" in result.stdout.lower()
