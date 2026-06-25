"""A self-contained tour of crucible, offline, no install and nothing downloaded.

Build a thesis of three claims about binary search, measure two of them against a known bound, and
witness a verdict per claim: one holds (MATCH), one breaks (DRIFT), and one states no falsification
condition so nothing can settle it (UNVERIFIABLE). Then tamper with the witnessed record to show the
seal catch it.

    python examples/demo.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import dataclasses  # noqa: E402

from crucible.assess import assess, verify_assessment  # noqa: E402
from crucible.claim import make_claim  # noqa: E402
from crucible.measure import MetricSpec, TableMeasure, measure_thesis  # noqa: E402
from crucible.steelman import NullSteelman, steelman_thesis  # noqa: E402
from crucible.thesis import make_thesis  # noqa: E402

CLOCK = lambda: 1_700_000_000.0  # noqa: E731 (a fixed clock so the demo output is stable)


def main() -> int:
    holds = make_claim(
        "binary search over a sorted array of 1024 elements does at most 11 comparisons",
        "a measured worst-case comparison count above 11 for n=1024",
    )
    breaks = make_claim(
        "binary search over a sorted array of 1024 elements does at most 3 comparisons",
        "a measured worst-case comparison count above 3 for n=1024",
    )
    untestable = make_claim("binary search is more elegant than linear search")  # no falsification

    thesis = make_thesis("Binary search comparison bounds", [holds, breaks, untestable], clock=CLOCK)
    print(f'thesis "{thesis.title}": {len(thesis.claims)} claims, seal {thesis.seal[:12]}...')

    # Steelman first: the adversary proposes the test that would settle each claim (it does not decide).
    print()
    for r in steelman_thesis(NullSteelman(), thesis):
        print(f"  steelman[{r.source}] {r.claim_id}: {r.measurable or '(unfalsifiable)'}")

    # The measurement decides. A sound oracle reads the substrate: the worst case for n=1024 is
    # floor(log2(1024)) + 1 = 11 probes. The oracle computes each claim's deviation from that.
    oracle = TableMeasure(
        specs={
            holds.id: MetricSpec(predicted=11.0, tolerance=0.5, observe="probes_1024"),
            breaks.id: MetricSpec(predicted=3.0, tolerance=0.5, observe="probes_1024"),
            # the untestable claim gets no spec, so the oracle returns UNVERIFIABLE
        },
        substrate={"probes_1024": 11.0},
        clock=CLOCK,
    )
    measurements = measure_thesis(oracle, thesis)
    assessment, verdicts = assess(thesis, measurements, clock=CLOCK)
    print()
    for v in verdicts:
        print(f"  {v.status:<12} {v.grounds}")
    print()
    print(f"counts: MATCH {assessment.match}  DRIFT {assessment.drift}  "
          f"UNVERIFIABLE {assessment.unverifiable}")
    print(f"assessment seal {assessment.seal[:12]}..., verified {verify_assessment(assessment)}")

    tampered = dataclasses.replace(assessment, drift=0, match=2)  # quietly turn a break into a pass
    print(f"after flipping a DRIFT to a MATCH, verified {verify_assessment(tampered)}  <- caught")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
