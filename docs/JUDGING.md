# Judging: pairwise in both orders, decomposed claims, minorities kept

Three tools for when a model or a panel does the judging. Each one keeps the verdict re-checkable and reports what a simpler method would hide.

## Pairwise judging in both orders

A judge that compares two answers side by side often prefers whichever it reads first. Crucible asks the comparator twice, once with each answer in the first slot, and returns a winner only when both orders agree. A split comes back as `ORDER_DISAGREE`, never as a preference.

```python
from crucible.pairwise import judge_pair, pairwise_report

result = judge_pair(my_comparator, question, answer_a, answer_b, rubric)
result.verdict          # "A", "B", "TIE", "ORDER_DISAGREE" or "UNVERIFIABLE"
pairwise_report([result, ...])   # order-swap consistency and first-slot rate, with Wilson intervals
```

A comparator is any function `(question, first, second, rubric) -> {"prefer": "first" | "second" | "tie"}`. One that raises or answers anything else fails closed to `UNVERIFIABLE`. `PairwiseMeasure` puts the same check on the measure seam: "A beats B" is MATCH only when both orders prefer A, and the measurement seals the rubric, both answers and both slot answers for replay.

Judgments recorded by any tool can be scored from the command line:

```bash
crucible pairwise pairs.json          # {"pairs": [{"id": 1, "ab": "first", "ba": "second"}, ...]}
crucible pairwise pairs.json --json
```

`ab` is the slot picked with A first; `ba` is the slot picked with B first.

## Decomposed claims

A broad claim often mixes several judgments. Split it into typed sub-questions (yes or no, a number with a tolerance, a choice among options) and each one is measured on its own and decided by the same pure verdict function. The parent's verdict is the worst of its parts: any DRIFT gives DRIFT, otherwise any UNVERIFIABLE gives UNVERIFIABLE. The report names the one sub-question that held least well.

```bash
crucible decompose release.json --json
```

```json
{"claim": "the release is ready", "falsification": "any sub-question fails",
 "questions": [
   {"id": "tests", "text": "Does the test suite pass?", "kind": "yesno", "expected": true},
   {"id": "latency", "text": "p95 latency in ms", "kind": "number", "expected": 200, "tolerance": 50},
   {"id": "tier", "text": "Which tier ships?", "kind": "choice", "expected": "beta", "options": ["alpha", "beta"]}],
 "answers": {"tests": true, "latency": 400, "tier": "beta"}}
```

The decomposition carries its own seal beside the parent claim, so the parent claim's hash, and every registry that stores it, stays unchanged.

## Minority views kept

When several judges or sources weigh in, a summary that keeps only the consensus hides the view most likely to matter. `crucible views` groups views by position and lists the majority beside every minority position, with its sources and count. Nothing is dropped.

```bash
crucible views views.json             # {"views": [{"source", "position", "text"}], "planted"?: [...]}
crucible report REGISTRY --views views-by-claim.json   # adds a "Views, minorities kept" section
```

`dissent_survival(planted, summary)` scores any summary, structured or plain text, on how many planted minority positions it kept, so you can test a summarizer before trusting it.

## Measured results

One run with a 2B local judge (Qwen3.5-2B) on items with exact labels, bars set before the run. Full method, data and scripts: [`benchmarks/judging-v1`](benchmarks/judging-v1/README.md).

| Question | Result | Bar |
|:--|:--|:--|
| Order-swap consistency, 100 pairs | 0.07 [0.03, 0.14] | at least 0.85: fail |
| Pairwise vs pointwise accuracy | 0.07 vs 0.87 | pairwise ahead: fail |
| Same weakest claim in 3 reruns, 30 theses | decomposed 0.70, holistic 0.20, difference +0.50 [+0.27, +0.70] | pass |
| `summarize_views` keeps the minority, 30 sets | 30 of 30 | at least 0.9: pass |

The small judge picked the first slot 96% of the time. The both-order check caught that and returned `ORDER_DISAGREE` for 93 of 100 pairs instead of a false preference, but it does not make a judge this biased more accurate: for a 2B judge, score each answer alone. Agreement with human preference labels was not tested, because no labelled set was available. Splitting a thesis into sub-questions made the named weakest claim far more stable across reruns.
