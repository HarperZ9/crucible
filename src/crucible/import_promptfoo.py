"""Turn a promptfoo suite into a re-checkable thesis.

promptfoo is a common eval config format, and the cost of moving a suite off it is rewriting the
assertions. This module makes that one command: every assertion in a promptfooconfig becomes a
Crucible Claim (the assertion as a testable prediction) with its falsification condition (the
observation that refutes it), and the suite becomes a Thesis whose seal a third party re-derives.
Nothing is judged here. Importing produces the registrable thesis; ``crucible assess`` produces
verdicts.

Input: a promptfooconfig as JSON (stdlib) OR a YAML SUBSET. The YAML parser is
deliberately narrow and FAIL-LOUD: it handles block mappings, block sequences,
and plain/quoted scalars (the shape real promptfoo configs use) and RAISES on
anything it does not fully support (flow style, anchors, multi-line/`|`/`>`
scalars, tabs) rather than silently mis-parsing an assertion into the wrong
claim. A mis-imported assertion is worse than a refused one, so the parser
refuses.

Supported assertion types map to a claim + falsification:
  contains / icontains / equals / not-contains / regex / starts-with /
  is-json / cost / latency / llm-rubric / javascript / python / <others>
Every type is imported (an unknown type becomes a generic 'assertion holds'
claim, never dropped); the type and value are preserved in the claim text so the
prediction stays specific and the falsification stays checkable.
"""
from __future__ import annotations

import json
from collections.abc import Callable

from .claim import Claim, make_claim
from .thesis import Thesis, make_thesis

PUBLISHABLE = "publishable"


class PromptfooParseError(ValueError):
    """Raised when the input is not a promptfoo config we can import faithfully."""


# ---------------------------------------------------------------------------
# minimal, fail-loud YAML subset (block maps + block seqs + scalars only)
# ---------------------------------------------------------------------------

_UNSUPPORTED = {
    "&": "anchors", "*": "aliases", "<<": "merge keys",
    "|": "block scalars", ">": "folded scalars",
}


def _scalar(tok: str):
    tok = tok.strip()
    if tok == "" or tok == "~" or tok == "null":
        return None
    if tok in ("true", "True"):
        return True
    if tok in ("false", "False"):
        return False
    if len(tok) >= 2 and tok[0] in "\"'" and tok[-1] == tok[0]:
        inner = tok[1:-1]
        if tok[0] == '"' and "\\" in inner:
            raise PromptfooParseError("escape sequences in double-quoted scalars are not "
                                      "supported; convert the config to JSON")
        if tok[0] == "'":
            if "'" in inner.replace("''", ""):
                raise PromptfooParseError(f"unbalanced quote in scalar {tok!r}")
            return inner.replace("''", "'")
        if '"' in inner:
            raise PromptfooParseError(f"unbalanced quote in scalar {tok!r}")
        return inner
    if tok[:1] in "\"'":
        raise PromptfooParseError(f"unterminated quoted scalar {tok!r}")
    if tok.startswith("[") or tok.startswith("{"):
        raise PromptfooParseError("flow-style collections are not supported; "
                                  "convert the config to JSON")
    try:
        return int(tok)
    except ValueError:
        pass
    try:
        return float(tok)
    except ValueError:
        return tok


def _indent(line: str) -> int:
    if "\t" in line[:len(line) - len(line.lstrip())]:
        raise PromptfooParseError("tabs in indentation are not valid YAML; use spaces")
    return len(line) - len(line.lstrip(" "))


def _strip_comment(line: str) -> str:
    """Drop a trailing ``# comment``. A ``#`` inside quotes, or one with no space before it, is
    part of the value, so a quoted assertion value keeps every character."""
    quote = ""
    for i, ch in enumerate(line):
        if quote:
            quote = "" if ch == quote else quote
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " 	"):
            return line[:i]
    return line


def parse_yaml_subset(text: str):
    """Parse the block-map/block-seq/scalar subset. Fail loud on the rest."""
    raw = []
    for ln in text.splitlines():
        s = _strip_comment(ln).rstrip()
        if not s.strip() or s.strip() == "---":
            continue
        raw.append(s)
    for line in raw:
        stripped = line.strip()
        for tok, name in _UNSUPPORTED.items():
            if stripped.startswith(tok) or f": {tok}" in stripped or stripped.endswith(f" {tok}"):
                raise PromptfooParseError(f"{name} are not supported; convert to JSON")
    pos = [0]

    def parse_block(min_indent: int):
        items_is_seq = None
        mapping: dict = {}
        seq: list = []
        while pos[0] < len(raw):
            line = raw[pos[0]]
            ind = _indent(line)
            if ind < min_indent:
                break
            body = line.strip()
            if body.startswith("- "):
                if items_is_seq is False:
                    raise PromptfooParseError("mixed sequence and mapping at one level")
                items_is_seq = True
                pos[0] += 1
                rest = body[2:].strip()
                if ":" in rest and rest[0] not in "\"'":
                    # inline mapping start on the dash line
                    raw[pos[0] - 1] = " " * (ind + 2) + rest
                    pos[0] -= 1
                    seq.append(parse_block(ind + 2))
                elif rest == "":
                    seq.append(parse_block(ind + 2))
                else:
                    seq.append(_scalar(rest))
            elif ":" in body:
                if items_is_seq is True:
                    break
                items_is_seq = False
                key, _, val = body.partition(":")
                key = key.strip()
                if key and key[0] in "\"'" and key[-1] == key[0]:
                    key = key[1:-1]
                pos[0] += 1
                if val.strip() == "":
                    nxt = _next_indent(pos[0])
                    mapping[key] = parse_block(ind + 1) if nxt > ind else None
                else:
                    mapping[key] = _scalar(val)
            else:
                raise PromptfooParseError(f"cannot parse line: {line!r}")
        return seq if items_is_seq else mapping

    def _next_indent(i: int) -> int:
        return _indent(raw[i]) if i < len(raw) else -1

    result = parse_block(0)
    return result


def load_config(text: str, *, is_json: bool | None = None) -> dict:
    """Load a promptfoo config from JSON or the YAML subset. `is_json` forces the
    reader; None auto-detects (a leading { or [ is JSON)."""
    t = text.lstrip()
    use_json = is_json if is_json is not None else t.startswith(("{", "["))
    if use_json:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise PromptfooParseError(f"invalid JSON config: {e}") from e
    else:
        data = parse_yaml_subset(text)
    if not isinstance(data, dict):
        raise PromptfooParseError("promptfoo config must be a mapping at the top level")
    return data


# ---------------------------------------------------------------------------
# assertion -> claim
# ---------------------------------------------------------------------------

def _assert_to_claim(assertion: dict, *, test_label: str, index: int) -> Claim:
    atype = str(assertion.get("type", "assertion")).strip() or "assertion"
    value = assertion.get("value", "")
    vtext = value if isinstance(value, str) else json.dumps(value, sort_keys=True)
    metric = assertion.get("metric")
    where = f"test {test_label}" if test_label else f"test #{index}"
    if atype in ("contains", "icontains"):
        text = f"The model output for {where} contains {vtext!r}."
        fals = f"The output does not contain {vtext!r}."
    elif atype in ("not-contains", "not-icontains"):
        text = f"The model output for {where} does NOT contain {vtext!r}."
        fals = f"The output contains {vtext!r}."
    elif atype in ("equals", "is-equals"):
        text = f"The model output for {where} equals {vtext!r}."
        fals = f"The output differs from {vtext!r}."
    elif atype == "regex":
        text = f"The model output for {where} matches regex {vtext!r}."
        fals = f"The output does not match {vtext!r}."
    elif atype in ("starts-with",):
        text = f"The model output for {where} starts with {vtext!r}."
        fals = f"The output does not start with {vtext!r}."
    elif atype == "is-json":
        text = f"The model output for {where} is valid JSON{(' matching a schema' if value else '')}."
        fals = "The output is not valid JSON (or violates the schema)."
    elif atype in ("cost",):
        text = f"The model call for {where} costs at most {vtext}."
        fals = f"The cost exceeds {vtext}."
    elif atype in ("latency",):
        text = f"The model call for {where} completes within {vtext} ms."
        fals = f"The latency exceeds {vtext} ms."
    elif atype in ("llm-rubric", "model-graded-closedqa", "model-graded-factuality"):
        text = f"The model output for {where} satisfies the rubric: {vtext}"
        fals = "A grader judges the output as failing the rubric."
    elif atype in ("javascript", "python"):
        text = f"The model output for {where} satisfies the {atype} assertion."
        fals = f"The {atype} assertion returns false/throws for the output."
    else:
        text = f"The model output for {where} satisfies the {atype} assertion" \
               f"{(' (' + vtext + ')') if vtext else ''}."
        fals = f"The {atype} assertion does not hold for the output."
    if metric:
        text = f"[{metric}] {text}"
    return make_claim(text, fals)


def _tests(config: dict) -> list:
    tests = config.get("tests", [])
    if isinstance(tests, str):
        raise PromptfooParseError(
            "tests is an external file reference; pass the resolved config "
            "(promptfoo can emit one) so every assertion is present to import")
    if not isinstance(tests, list):
        raise PromptfooParseError("promptfoo 'tests' must be a list")
    return tests


def import_promptfoo(text: str, *, is_json: bool | None = None,
                     clock: Callable[[], float]) -> Thesis:
    """Convert a promptfoo config into a Thesis of claims. Deterministic given
    `clock`. Raises PromptfooParseError if there are no assertions to import."""
    config = load_config(text, is_json=is_json)
    title = str(config.get("description") or "imported promptfoo suite").strip()
    claims: list[Claim] = []
    seen: set[str] = set()
    for i, test in enumerate(_tests(config)):
        if not isinstance(test, dict):
            continue
        label = str(test.get("description") or test.get("name") or "").strip()
        asserts = test.get("assert", [])
        if not isinstance(asserts, list):
            raise PromptfooParseError(f"test #{i} 'assert' must be a list")
        for j, a in enumerate(asserts):
            if not isinstance(a, dict):
                raise PromptfooParseError(f"test #{i} assertion #{j} must be a mapping")
            claim = _assert_to_claim(a, test_label=label, index=i)
            if claim.sha256 in seen:                # identical assertions collapse (same content hash)
                continue
            seen.add(claim.sha256)
            claims.append(claim)
    if not claims:
        raise PromptfooParseError(
            "no assertions found to import: a promptfoo suite needs tests with "
            "an 'assert' list for the migration to produce claims")
    return make_thesis(title, claims, clock=clock, disposition=PUBLISHABLE)
