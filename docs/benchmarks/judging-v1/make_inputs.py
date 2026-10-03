"""Frozen inputs for the Crucible judging sprint. Deterministic: seed 20261003."""
import json
import random
from pathlib import Path

HERE = Path(__file__).parent
rng = random.Random(20261003)
ITEMS = ["notebooks", "pens", "lamps", "chairs", "mugs", "cables", "plants", "tickets"]


def change_problem():
    k, p = rng.randint(3, 19), rng.randint(4, 29)
    total = k * p
    bill = (total // 50 + 1 + rng.randint(0, 2)) * 50
    slip = rng.choice([-10, 10, -20, 20, 1, -1])
    q = (f"A shop sells {ITEMS[rng.randrange(len(ITEMS))]} at {p} dollars each. A customer buys {k} "
         f"and pays with {bill} dollars. How much change does the customer get?")
    good = f"{k} x {p} = {total}. {bill} - {total} = {bill - total}. The change is {bill - total} dollars."
    bad_total = total + slip
    bad = (f"{k} x {p} = {bad_total}. {bill} - {bad_total} = {bill - bad_total}. "
           f"The change is {bill - bad_total} dollars.")
    return q, good, bad


def distance_problem():
    v, t = rng.randint(32, 88), rng.randint(2, 9)
    extra = rng.randint(5, 60)
    slip = rng.choice([-10, 10, 2, -2])
    q = (f"A train travels at {v} km per hour for {t} hours, then {extra} km more. "
         f"How far does it travel in total?")
    good = f"{v} x {t} = {v * t}. {v * t} + {extra} = {v * t + extra}. It travels {v * t + extra} km."
    bad = (f"{v} x {t} = {v * t + slip}. {v * t + slip} + {extra} = {v * t + slip + extra}. "
           f"It travels {v * t + slip + extra} km.")
    return q, good, bad


def pairs():
    out = []
    for i in range(100):
        q, good, bad = (change_problem if i % 2 == 0 else distance_problem)()
        correct_is_a = rng.random() < 0.5
        a, b = (good, bad) if correct_is_a else (bad, good)
        out.append({"id": i, "question": q, "a": a, "b": b, "correct": "A" if correct_is_a else "B"})
    return out


def fact(true):
    x, y = rng.randint(12, 49), rng.randint(11, 39)
    if rng.random() < 0.5:
        value, op = x * y, "x"
        wrong = value + rng.choice([-10, 10, -20, 20])
    else:
        value, op = x + y, "+"
        wrong = value + rng.choice([-10, 10, -1, 1])
    return f"{x} {op} {y} = {value if true else wrong}"


def theses():
    out = []
    for i in range(30):
        wrong = rng.randrange(3)
        out.append({"id": i, "claims": [fact(j != wrong) for j in range(3)], "wrong": wrong})
    return out


TOPICS = [
    ("ship the release on Friday", "rollback"), ("adopt the new logging library", "licence"),
    ("move the service to the new region", "latency"), ("launch the redesigned form", "accessibility"),
    ("enable session replay", "privacy"), ("upgrade the database cluster", "downtime"),
    ("switch to the cheaper storage tier", "durability"), ("merge the refactor today", "coverage"),
    ("turn on autoscaling", "cost"), ("publish the benchmark", "contamination"),
    ("retire the old API", "migration"), ("add the analytics script", "consent"),
    ("raise the rate limit", "abuse"), ("cache user profiles", "staleness"),
    ("open the beta to everyone", "support"), ("use the vendor SDK", "lockin"),
    ("compress the images harder", "artifacts"), ("drop the legacy browser", "enterprise"),
    ("batch the nightly jobs", "deadlines"), ("store logs for a year", "retention"),
    ("auto-merge dependency bumps", "supplychain"), ("translate with the model", "terminology"),
    ("let agents run shell commands", "sandboxing"), ("index the shared drive", "permissions"),
    ("ship the dark theme", "contrast"), ("cut the test suite in half", "regressions"),
    ("move docs to the wiki", "versioning"), ("offer an annual discount", "churn"),
    ("send weekly digest emails", "unsubscribe"), ("pin the model version", "deprecation"),
]


def source_sets():
    out = []
    for i, (topic, word) in enumerate(TOPICS):
        views = [{"source": f"reviewer{j}", "position": f"{topic}",
                  "text": f"I support the plan to {topic}; the benefits are clear."} for j in range(4)]
        minority = {"source": "reviewer4", "position": f"wait: {word} risk",
                    "text": f"I disagree: we should wait, because the {word} risk is not addressed."}
        views.insert(rng.randrange(5), minority)
        out.append({"id": i, "question": f"Should we {topic}?", "views": views, "planted": word})
    return out


def main():
    data = {"pairs": pairs(), "theses": theses(), "source_sets": source_sets()}
    (HERE / "inputs-v1.json").write_text(json.dumps(data, indent=1, sort_keys=True) + "\n",
                                         encoding="utf-8", newline="\n")


main()
