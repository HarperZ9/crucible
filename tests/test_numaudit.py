"""Number audit: each rule must flag a planted wrong figure and pass the correct one."""
import json

import pytest

from crucible.cli import main
from crucible.numaudit import audit, normalise


def rules(text):
    return [(f.rule, f.severity) for f in audit(text)]


@pytest.mark.parametrize("wrong, right", [
    ("runs at 140 degrees C or about 220 degrees F in service",
     "runs at 140 degrees C or about 284 degrees F in service"),
    ("a range of 96 kilometers or 90 miles", "a range of 96 kilometers or 60 miles"),
    ("it weighs 100 kg or about 100 pounds", "it weighs 100 kg or about 220 pounds"),
    ("rated at 200 kW or 500 horsepower", "rated at 200 kW or 268 horsepower"),
])
def test_unit_pair(wrong, right):
    assert rules(wrong) == [("unit_pair", "flag")]
    assert rules(right) == []


def test_unit_pair_range_and_caption_readings():
    # a range pairs its ends; a dropped minus sign on both sides is marked ambiguous, not passed
    assert rules("from -40 degrees C to 120 degrees C or about -40 degrees F to 248 degrees F") == []
    assert rules("from 34 degrees C to 121 degrees C or about 30 degrees F to 250 degrees F") == [("unit_pair", "ambiguous")]
    assert rules("lasted just 9 60 km or about 600 miles") == [("unit_pair", "ambiguous")]


def test_normalise_thousands():
    assert normalise("over 37,000 rpm at 4 500 F") == "over 37000 rpm at 4500 F"


def test_speed_multiple():
    assert rules("about 3 trillion meters per second or about 10 million times faster than light") == [("speed_multiple", "flag")]
    assert rules("about 3 trillion meters per second or about 10000 times faster than light") == []


def test_screw_resolution_with_and_without_worm():
    assert rules("a screw with a pitch of 1 mm and a thimble divided into 20 parts reads down to 500ths of a millimeter") \
        == [("screw_resolution", "flag")]
    assert rules("a screw with a pitch of 1 mm and a thimble divided into 20 parts reads down to 1/20 of a millimeter") == []
    assert rules("a screw of 20 threads to the inch turned by a worm wheel of 200 teeth driven by a hand wheel "
                 "carrying 250 divisions, each division moving 1 millionth of an inch") == []


def test_thermal_expansion():
    wrong = "an aluminum bar cut at a length of 100 millimetres will expand up to 51 microns when heated to 100 degrees"
    right = "an aluminum bar cut at a length of 100 millimetres will expand up to 184 microns when heated to 100 degrees"
    found = audit(wrong)
    assert [f.rule for f in found] == ["thermal_expansion"]
    assert found[0].extra["implied_rise_K"] == pytest.approx(22.17, abs=0.05)
    assert rules(right) == []


def test_rim_speed_solves_radius_from_energy():
    text = ("to store 26 kilowatt hours in a 100 kilogram flywheel it would be one meter and spin over 37000 rpm, "
            "so the rim would move at over {n} times the speed of sound")
    assert rules(text.format(n=11)) == [("rim_speed", "flag")]
    assert rules(text.format(n=5.6)) == []


def test_reference_distance():
    assert rules("the rover landed on Mars after a 350 mile journey") == [("reference_distance", "flag")]
    assert rules("the rover landed on Mars after a 300 million mile journey") == []


def test_data_rate_and_ground_sample():
    base = ("a 1.8 gigapixel sensor with a field of view of around 16 kilometers, each pixel can resolve down to "
            "{g}, capturing at 15 frames a second it makes {r} of imagery every second")
    found = rules(base.format(g="2 millimeters", r="21 terabytes"))
    assert ("ground_sample", "flag") in found and ("data_rate", "flag") in found
    assert rules(base.format(g="40 centimeters", r="81 gigabytes")) == []


def test_fuel_endurance():
    assert rules("it carried 10 lb of fuel, burning up to a gallon per minute, with flights of up to 10 minutes") \
        == [("fuel_endurance", "flag")]
    assert rules("it carried 10 lb of fuel, burning up to a gallon per minute, with flights of up to 1 minutes") == []


def test_trend_direction():
    assert rules("today it takes 96 billion hash guesses per block; a decade earlier it took only about "
                 "180 trillion hash guesses, a dramatic rise") == [("trend_direction", "flag")]
    assert rules("today it takes 180 trillion hash guesses per block; a decade earlier it took only about "
                 "96 billion hash guesses, a dramatic rise") == []


def test_plain_prose_has_no_findings():
    assert audit("The engine was built in 1876 and had 4 strokes and 2 valves per cylinder.") == []


def test_cli_json(tmp_path, capsys):
    p = tmp_path / "t.txt"
    p.write_text("it runs at 140 degrees C or about 220 degrees F", encoding="utf-8")
    assert main(["numaudit", str(p), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["schema"] == "crucible.numaudit/1" and out["flags"] == 1
    assert main(["numaudit", str(p), "--fail-on-flag"]) == 1
