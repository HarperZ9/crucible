"""C3 sensitivity: the same scoring as analyze.c3, without source set 14 (disputed label)."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[2] / "src"))
from crucible.dissent import dissent_survival  # noqa: E402
from crucible.pairwise import wilson  # noqa: E402

inputs = json.loads((HERE / "inputs-v1.json").read_text(encoding="utf-8"))
raw = {r["id"]: r for r in json.loads((HERE / "raw-v1.json").read_text(encoding="utf-8"))["summaries"]}
sets = [s for s in inputs["source_sets"] if s["id"] != 14]
out = {"n": len(sets)}
for key in ("plain", "keep_minority"):
    k = sum(dissent_survival([s["planted"]], raw[s["id"]][key])["survived"] for s in sets)
    out[key] = {"survived": k, "rate": k / len(sets), "wilson95": wilson(k, len(sets))}
print(json.dumps(out, indent=1))
