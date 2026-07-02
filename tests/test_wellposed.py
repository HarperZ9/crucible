"""Pre-assessment validation: ill-posed measurement rows produce typed warnings BEFORE assessment
runs, and a well-posed file produces none. Every warning class carries its own negative fixture
here: a validator that cannot reject a known-bad row is not a validator."""
from __future__ import annotations

import pytest

from crucible.claim import make_claim
from crucible.thesis import make_thesis
from crucible.wellposed import (
    BOOLEAN_VALUE,
    DUPLICATE_CLAIM_BINDING,
    NON_POSITIVE_TOLERANCE,
    UNBOUND_CLAIM,
    UNTRUSTED_DEVIATION,
    WARNING_CODES,
    measurement_warnings,
    warning_row,
)

CLOCK = lambda: 1000.0  # noqa: E731


def _thesis():
    return make_thesis("Wellposed thesis",
                       [make_claim("c-one", "f1"), make_claim("c-two", "f2")], clock=CLOCK)


def _data(*rows):
    return {"measurements": list(rows)}


def test_well_posed_rows_produce_no_warnings():
    data = _data({"claim": "c-one", "deviation": 0.0, "tolerance": 0.1},
                 {"claim": "c-two", "deviation": 0.2, "tolerance": 0.1})
    assert measurement_warnings(_thesis(), data) == ()


def test_absent_deviation_is_honest_unmeasured_not_ill_posed():
    data = _data({"claim": "c-one", "tolerance": 0.1})
    assert measurement_warnings(_thesis(), data) == ()


@pytest.mark.parametrize("tolerance", [0.0, -1.0, "abc", float("inf")])
def test_non_positive_tolerance_warns(tolerance):
    data = _data({"claim": "c-one", "deviation": 0.0, "tolerance": tolerance})
    warnings = measurement_warnings(_thesis(), data)
    assert [w.code for w in warnings] == [NON_POSITIVE_TOLERANCE]
    assert warnings[0].row == 1
    assert warnings[0].claim == "c-one"


def test_missing_tolerance_warns_as_non_positive():
    warnings = measurement_warnings(_thesis(), _data({"claim": "c-one", "deviation": 0.0}))
    assert [w.code for w in warnings] == [NON_POSITIVE_TOLERANCE]


@pytest.mark.parametrize("deviation", [-0.5, float("nan"), float("inf"), "abc"])
def test_untrusted_deviation_warns(deviation):
    data = _data({"claim": "c-one", "deviation": deviation, "tolerance": 0.1})
    warnings = measurement_warnings(_thesis(), data)
    assert [w.code for w in warnings] == [UNTRUSTED_DEVIATION]


def test_boolean_deviation_and_tolerance_warn_once_each():
    data = _data({"claim": "c-one", "deviation": True, "tolerance": False})
    warnings = measurement_warnings(_thesis(), data)
    assert [w.code for w in warnings] == [BOOLEAN_VALUE, BOOLEAN_VALUE]
    assert "deviation" in warnings[0].detail
    assert "tolerance" in warnings[1].detail


def test_unbound_claim_warns():
    data = _data({"claim": "nope", "deviation": 0.0, "tolerance": 0.1})
    warnings = measurement_warnings(_thesis(), data)
    assert [w.code for w in warnings] == [UNBOUND_CLAIM]
    assert warnings[0].claim == "nope"


def test_ambiguous_claim_text_warns_as_unbound():
    thesis = make_thesis("Ambiguous", [
        make_claim("same text", "first failure", id="a"),
        make_claim("same text", "second failure", id="b"),
    ], clock=CLOCK)
    data = _data({"claim": "same text", "deviation": 0.0, "tolerance": 0.1})
    warnings = measurement_warnings(thesis, data)
    assert [w.code for w in warnings] == [UNBOUND_CLAIM]
    assert "ambiguous" in warnings[0].detail


def test_duplicate_claim_binding_warns_on_the_later_row():
    thesis = _thesis()
    claim_id = thesis.claims[0].id
    data = _data({"claim": "c-one", "deviation": 0.0, "tolerance": 0.1},
                 {"claim": claim_id, "deviation": 0.2, "tolerance": 0.1})
    warnings = measurement_warnings(thesis, data)
    assert [w.code for w in warnings] == [DUPLICATE_CLAIM_BINDING]
    assert warnings[0].row == 2


def test_one_row_can_carry_multiple_warnings_in_row_order():
    data = _data({"claim": "c-one", "deviation": -1.0, "tolerance": 0.0},
                 {"claim": "c-one", "deviation": True, "tolerance": 0.1})
    codes = [w.code for w in measurement_warnings(_thesis(), data)]
    assert codes == [UNTRUSTED_DEVIATION, NON_POSITIVE_TOLERANCE,
                     DUPLICATE_CLAIM_BINDING, BOOLEAN_VALUE]
    assert set(codes) <= set(WARNING_CODES)


def test_structurally_malformed_data_is_left_to_the_loader():
    assert measurement_warnings(_thesis(), {}) == ()
    assert measurement_warnings(_thesis(), {"measurements": "not-a-list"}) == ()
    assert measurement_warnings(_thesis(), _data("not-an-object")) == ()


def test_warning_row_is_the_typed_dict():
    data = _data({"claim": "nope", "deviation": 0.0, "tolerance": 0.1})
    row = warning_row(measurement_warnings(_thesis(), data)[0])
    assert set(row) == {"row", "claim", "code", "detail"}
    assert row["code"] == UNBOUND_CLAIM
