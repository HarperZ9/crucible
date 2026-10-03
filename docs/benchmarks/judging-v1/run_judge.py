"""GPU judge run for the Crucible sprint: Qwen3.5-2B, next-token probabilities.

Run with Python, torch and transformers on one CUDA GPU. Set CRUCIBLE_JUDGE_MODEL to a local
snapshot of the same revision to run offline.
Writes raw-v1.json (every probability and generation) beside this file.
"""
import json
import os
import sys
from pathlib import Path

import torch
from transformers import AutoModelForImageTextToText, AutoTokenizer

HERE = Path(__file__).parent
MODEL = os.environ.get("CRUCIBLE_JUDGE_MODEL", "Qwen/Qwen3.5-2B")  # revision 15852e8c
RUBRIC = "The correct answer has every arithmetic step right."


def load():
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForImageTextToText.from_pretrained(MODEL, dtype=torch.bfloat16, device_map="cuda")
    model.eval()
    return tok, model


def prompt(tok, text):
    msgs = [{"role": "user", "content": text}]
    return tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True,
                                   enable_thinking=False)


@torch.no_grad()
def next_probs(tok, model, text, options):
    ids = tok(prompt(tok, text), return_tensors="pt").to("cuda")
    logits = model(**ids).logits[0, -1].float()
    probs = torch.softmax(logits, -1)
    out = {}
    for opt in options:
        tid = tok.encode(opt, add_special_tokens=False)[0]
        out[opt] = probs[tid].item()
    return out


@torch.no_grad()
def generate(tok, model, text, max_new_tokens=120):
    ids = tok(prompt(tok, text), return_tensors="pt").to("cuda")
    out = model.generate(**ids, max_new_tokens=max_new_tokens, do_sample=False)
    return tok.decode(out[0, ids["input_ids"].shape[1]:], skip_special_tokens=True).strip()


def pair_prompt(q, first, second):
    return (f"{RUBRIC}\n\nQuestion: {q}\n\nAnswer 1: {first}\n\nAnswer 2: {second}\n\n"
            "Which answer is correct? Reply with only the number 1 or 2.")


def point_prompt(q, answer):
    return (f"{RUBRIC}\n\nQuestion: {q}\n\nAnswer: {answer}\n\n"
            "Is this answer correct? Reply with only Yes or No.")


def run_pairs(tok, model, pairs):
    rows = []
    for p in pairs:
        ab = next_probs(tok, model, pair_prompt(p["question"], p["a"], p["b"]), ["1", "2"])
        ba = next_probs(tok, model, pair_prompt(p["question"], p["b"], p["a"]), ["1", "2"])
        pa = next_probs(tok, model, point_prompt(p["question"], p["a"]), ["Yes", "No"])
        pb = next_probs(tok, model, point_prompt(p["question"], p["b"]), ["Yes", "No"])
        rows.append({"id": p["id"], "ab": ab, "ba": ba, "point_a": pa, "point_b": pb})
    return rows


def run_theses(tok, model, theses):
    rows = []
    for t in theses:
        listing = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(t["claims"]))
        hol = next_probs(tok, model, f"Here are three claims:\n{listing}\n\nWhich claim is least "
                         "supported, meaning most likely false? Reply with only 1, 2 or 3.",
                         ["1", "2", "3"])
        dec = [next_probs(tok, model, f"Claim: {c}\n\nIs this claim correct? Reply with only Yes or No.",
                          ["Yes", "No"]) for c in t["claims"]]
        rows.append({"id": t["id"], "holistic": hol, "decomposed": dec})
    return rows


def run_summaries(tok, model, sets):
    rows = []
    for s in sets:
        listing = "\n".join(f"- {v['source']}: {v['text']}" for v in s["views"])
        base = f"Question: {s['question']}\n\nReviewer views:\n{listing}\n\n"
        plain = generate(tok, model, base + "Summarize the reviewers' views in two sentences.")
        keep = generate(tok, model, base + "Summarize the reviewers' views in two sentences. "
                        "Keep every minority view, naming its concern; do not merge it into the consensus.")
        rows.append({"id": s["id"], "plain": plain, "keep_minority": keep})
    return rows


def main():
    data = json.loads((HERE / "inputs-v1.json").read_text(encoding="utf-8"))
    print("pid", os.getpid(), flush=True)
    tok, model = load()
    raw = {"model": MODEL, "pairs": run_pairs(tok, model, data["pairs"]),
           "theses": run_theses(tok, model, data["theses"]),
           "summaries": run_summaries(tok, model, data["source_sets"])}
    (HERE / "raw-v1.json").write_text(json.dumps(raw, indent=1) + "\n", encoding="utf-8")
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
