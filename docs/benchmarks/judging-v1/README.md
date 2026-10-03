# Judging benchmark v1

One run on 2026-10-03 of a small local judge against three questions. The bars were written down before the run, and the run happened once. Every number here can be re-derived from the files in this folder.

## What it asks

1. Does asking for a preference in both orders beat scoring each answer alone?
2. Does splitting a thesis into sub-questions make the named weakest claim more stable across reruns?
3. Does a summary keep the one reviewer who disagrees?

## Inputs

`make_inputs.py` (seed 20261003) writes `inputs-v1.json`, sha256 `5fde527891f85ac6e1fab292be007b753a1d09e2ba723d250e459677665061bd`. Running it again gives the same hash.

- 100 pairs of worked answers to arithmetic word problems (change and distance). One answer in each pair is right. The other has a slip in its first step that carries through. The right answer sits in slot A in 52 pairs and in slot B in 48.
- 30 theses of three arithmetic claims each, with exactly one claim false.
- 30 sets of five reviewer views. Four support a plan and one disagrees, naming a concern word unique to that set.

The labels are exact by construction. A labeller that saw only this file and none of the code rechecked every label before scoring. It agreed on all 100 pairs and all 30 theses. It flagged set 14, where the concern word "support" also appears in the four majority views, so a word check cannot tell the two sides apart there. Set 14 stays in the frozen file, and the summary results are reported with and without it.

## Judge

Qwen3.5-2B (revision `15852e8c`), bf16 on one RTX 4090, with thinking turned off. `run_judge.py` reads next-token probabilities for the answer tokens and writes every probability and generated summary to `raw-v1.json`. `analyze.py` scores that file with Crucible's own functions and writes `scores-v1.json`. `c3_sensitivity.py` writes `c3-sensitivity-v1.json`.

## Bars and results

| Question | Bar set before the run | Result | Outcome |
|:--|:--|:--|:--|
| Order-swap consistency | at least 0.85 | 0.07 [0.03, 0.14] | fail |
| Pairwise minus pointwise accuracy | interval above zero | 0.07 vs 0.87; difference -0.80 [-0.88, -0.72] | fail |
| Decomposed minus holistic agreement on the weakest claim, 3 reruns | interval above zero | 0.70 vs 0.20; difference +0.50 [+0.27, +0.70] | pass |
| `summarize_views` keeps the planted minority | at least 0.9 | 30 of 30 | pass |
| Model summary keeps the concern word, 29 sets | no bar | plain prompt 26 of 29, 0.90 [0.74, 0.96]; told to keep minorities 26 of 29, same | reported |

Proportion intervals are Wilson 95%. Difference intervals come from a paired bootstrap over items, 10,000 resamples, seed 20261003.

### Pairwise

This judge picked the first slot in 96% of its answers [93%, 98%]. In 93 of 100 pairs the two orders named different winners. Read in one order only, its accuracy was 0.56, which looks like a weak preference and is mostly slot position. Scoring each answer alone with a yes or no question gave 0.87.

The both-order check did its job: it refused to report a preference in 93 pairs where the judge had none it could defend. With this judge it does not make the judging more accurate. Pointwise scoring is the better choice for a 2B judge on this task. The bar asked for 100 human preference labels, and no such set was available, so the human-preference version of the claim is untested.

### Decomposed claims

Each thesis was judged three times at temperature 0.7. Asked as one question ("which of these three is least supported"), the judge named the same claim in all three runs for 6 of 30 theses. Asked claim by claim, it did so for 21 of 30. The decomposed runs named the false claim 57% of the time, against 39% for the holistic runs.

### Minority views

`summarize_views` groups views by position and never drops a group, so it keeps every planted minority. That holds by construction; the run confirms the code path rather than testing a hard case.

The model summaries kept the concern word in 26 of 29 sets with either prompt. A reader of the three misses in each arm found the concern there in another form: "licensing" or "license" for "licence", "locking in" or "lock-in" for "lockin", "permission" for "permissions", "unsubscribes" for "unsubscribe". The word check undercounts, and on these easy sets the 2B model kept the dissent with or without being told to. Thirteen of the 60 summaries said "out of four" when there were five reviewers, which the bar did not measure.

## What this cannot show

- Arithmetic slips are one kind of error. Nothing here transfers to open-ended answers or to human preference.
- A 2B judge is small. A larger judge may have far less slot bias, and then the both-order check matters in a different way.
- The minority sets are easy: one dissenter, stated plainly, with a distinctive word. A harder set would split the dissent across sources or bury it.

## Changes from the files as run

Three edits keep machine paths out of this folder: `run_judge.py` reads the model from `CRUCIBLE_JUDGE_MODEL` (default `Qwen/Qwen3.5-2B`), the `model` field in `raw-v1.json` names the revision, and the two scoring scripts import Crucible from this repository's `src`. Scores re-derived from these copies match the scores from the run exactly.
