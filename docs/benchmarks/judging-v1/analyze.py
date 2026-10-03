"""Score raw-v1.json against the bars in DECISION.md. Uses crucible's own functions."""
import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[2] / "src"))
from crucible.dissent import dissent_survival, summarize_views  # noqa: E402
from crucible.pairwise import A, B, combine, pairwise_report, wilson  # noqa: E402


def boot(diffs, seed=20261003, n=10_000):
    rng = random.Random(seed)
    k = len(diffs)
    means = sorted(sum(diffs[rng.randrange(k)] for _ in range(k)) / k for _ in range(n))
    return {"mean": sum(diffs) / k, "low": means[int(0.025 * n)], "high": means[int(0.975 * n) - 1]}


def slot(p):
    return "first" if p["1"] > p["2"] else "second" if p["2"] > p["1"] else "tie"


def c1(inputs, raw):
    truth = {p["id"]: p["correct"] for p in inputs["pairs"]}
    results, pw, pt, single = [], [], [], []
    for r in raw["pairs"]:
        res = combine(slot(r["ab"]), slot(r["ba"]))
        results.append(res)
        pw.append(1.0 if res.verdict == truth[r["id"]] else 0.0)
        sa = r["point_a"]["Yes"] / (r["point_a"]["Yes"] + r["point_a"]["No"])
        sb = r["point_b"]["Yes"] / (r["point_b"]["Yes"] + r["point_b"]["No"])
        pick = A if sa > sb else B if sb > sa else None
        pt.append(1.0 if pick == truth[r["id"]] else 0.0)
        one = A if slot(r["ab"]) == "first" else B if slot(r["ab"]) == "second" else None
        single.append(1.0 if one == truth[r["id"]] else 0.0)
    n = len(pw)
    return {"report": pairwise_report(results),
            "pairwise_acc": sum(pw) / n, "pairwise_acc_wilson": wilson(int(sum(pw)), n),
            "pointwise_acc": sum(pt) / n, "pointwise_acc_wilson": wilson(int(sum(pt)), n),
            "single_order_acc": sum(single) / n,
            "pairwise_minus_pointwise": boot([a - b for a, b in zip(pw, pt)])}


def temper(probs, t=0.7):
    w = [math.exp(math.log(max(p, 1e-12)) / t) for p in probs]
    s = sum(w)
    return [x / s for x in w]


def sample(rng, probs):
    x, acc = rng.random(), 0.0
    for i, p in enumerate(probs):
        acc += p
        if x < acc:
            return i
    return len(probs) - 1


def c2(inputs, raw):
    wrong = {t["id"]: t["wrong"] for t in inputs["theses"]}
    hol_agree, dec_agree, hol_hit, dec_hit = [], [], 0, 0
    for r in raw["theses"]:
        hp = temper([r["holistic"][k] for k in ("1", "2", "3")])
        hol, dec = [], []
        for seed in (1, 2, 3):
            rng = random.Random(seed * 1000 + r["id"])
            hol.append(sample(rng, hp))
            pyes = [d["Yes"] / (d["Yes"] + d["No"]) for d in r["decomposed"]]
            said_no = [i for i, p in enumerate(pyes) if sample(rng, temper([p, 1 - p])) == 1]
            pool = said_no or list(range(3))
            dec.append(min(pool, key=lambda i: (pyes[i], i)))
        hol_agree.append(1.0 if len(set(hol)) == 1 else 0.0)
        dec_agree.append(1.0 if len(set(dec)) == 1 else 0.0)
        hol_hit += sum(h == wrong[r["id"]] for h in hol)
        dec_hit += sum(d == wrong[r["id"]] for d in dec)
    n = len(hol_agree)
    return {"holistic_agreement": sum(hol_agree) / n, "decomposed_agreement": sum(dec_agree) / n,
            "decomposed_minus_holistic": boot([d - h for d, h in zip(dec_agree, hol_agree)]),
            "holistic_names_false_claim": hol_hit / (3 * n),
            "decomposed_names_false_claim": dec_hit / (3 * n)}


def c3(inputs, raw):
    gen = {r["id"]: r for r in raw["summaries"]}
    path = plain = keep = 0
    for s in inputs["source_sets"]:
        word = s["planted"]
        summary = summarize_views(s["views"])
        kept = [g["position"] for g in summary["minorities"]]
        path += int(any(word in k for k in kept))
        plain += int(dissent_survival([word], gen[s["id"]]["plain"])["survived"])
        keep += int(dissent_survival([word], gen[s["id"]]["keep_minority"])["survived"])
    n = len(inputs["source_sets"])
    return {"crucible_path": path / n, "plain_summary": plain / n, "plain_wilson": wilson(plain, n),
            "keep_minority_summary": keep / n, "keep_wilson": wilson(keep, n)}


def main():
    inputs = json.loads((HERE / "inputs-v1.json").read_text(encoding="utf-8"))
    raw = json.loads((HERE / "raw-v1.json").read_text(encoding="utf-8"))
    out = {"c1": c1(inputs, raw), "c2": c2(inputs, raw), "c3": c3(inputs, raw)}
    (HERE / "scores-v1.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=1))


main()
