#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Egor Khindikaynen (Nota). See LICENSE for license terms.
"""
Checks Nota language files against the English references and writes index.json.

The rules are the language-file contract of Nota spec 077 (FORMAT.md here), implemented the
same way as Nota's TranslationTable: tools/fixtures/verdicts.json holds the expected result
for a set of sample files, and both this script and Nota's smoke test must agree with it.
Standard library only.

  validate.py                       check languages/*.json against reference/*.json
  validate.py languages/fr.json     check some files
  validate.py --fixtures DIR        check DIR/*.json against DIR/verdicts.json
  validate.py --write-index COMMIT  check, then write index.json with files pinned at COMMIT

Exit 1 when a language file cannot be read, or has an entry that is in no reference, or that
cannot stand for its English text (wrong shape, placeholders, or a pattern that does not
format). Keys only older references have are warnings: a translation may keep them while
older Nota versions are still in use.
"""

import argparse
import glob
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORMAT_VERSION = 2
INDEX_FORMAT = 1
KEY_RE = re.compile(r'^[a-z0-9_]+(\.[a-z0-9_]+)+$')
MAX_KEY = 80
CODE_RE = re.compile(r'^[a-z]{2,3}(-[a-z0-9]+)*$')
PLACEHOLDER_RE = re.compile(r'\{(\d+)(?:[,:][^{}]*)?\}')
RULES = {"one_is_1", "one_is_0_1"}
MAX_PLACEHOLDER = 9
INT_MAX = 2 ** 31 - 1


class Table:
    def __init__(self, code, name, rule, notes, strings, problems):
        self.code, self.name, self.rule, self.notes = code, name, rule, notes
        self.strings = strings      # key -> (one or None, other, is_plural)
        self.problems = problems    # [(key, problem)]


def parse(text):
    """(Table, None) or (None, reason) — as TranslationTable.Parse."""
    class Duplicate(Exception):
        pass

    def hook(pairs):
        seen = set()
        for k, _ in pairs:
            if k in seen:
                raise Duplicate(k)
            seen.add(k)
        return dict(pairs)

    try:
        root = json.loads(text, object_pairs_hook=hook)
    except Duplicate as d:
        return None, f'duplicate key "{d.args[0]}"'
    except ValueError as e:
        return None, f"not valid JSON: {e}"
    if not isinstance(root, dict):
        return None, "the file must hold one JSON object"
    fv = root.get("formatVersion")
    if not isinstance(fv, int) or isinstance(fv, bool):
        return None, "formatVersion is missing"
    if fv != FORMAT_VERSION:
        return None, f"language file format {fv} is not supported (this check reads format {FORMAT_VERSION})"
    s = lambda k: root.get(k) if isinstance(root.get(k), str) else ""
    code = s("code")
    if not CODE_RE.match(code):
        return None, f"invalid code '{code}'"
    name = s("name")
    if not 1 <= len(name) <= 40:
        return None, "name must be 1–40 characters"
    rule = s("plural")
    if not rule and code == "en":
        rule = "one_is_1"
    if rule not in RULES:
        return None, "plural rule is missing" if not rule else f"unknown plural rule '{rule}'"
    strings, problems = {}, []
    table = root.get("strings")
    if table is not None:
        if not isinstance(table, dict):
            return None, "strings must be an object"
        for key, v in table.items():
            if not is_key(key):
                problems.append((key, "not a valid key (lower-case dot-separated segments, up to 80 characters)"))
                continue
            entry = entry_of(v)
            if entry is None:
                problems.append((key, 'must be a text, or an object with an "other" text'))
                continue
            if entry[1] == "":
                problems.append((key, "empty text (English is shown)"))
                continue
            strings[key] = entry
    return Table(code, name, rule, s("notes"), strings, problems), None


def is_key(key):
    return len(key) <= MAX_KEY and bool(KEY_RE.match(key))


def entry_of(v):
    if isinstance(v, str):
        return (None, v, False)
    if not isinstance(v, dict) or not isinstance(v.get("other"), str):
        return None
    one = v.get("one") if isinstance(v.get("one"), str) else None
    if one == "":
        one = None
    return (one, v["other"], True)


def placeholders(text):
    out = set()
    for m in PLACEHOLDER_RE.finditer(text.replace("{{", "").replace("}}", "")):
        i = int(m.group(1))
        out.add(i if i <= INT_MAX else -1)
    return out


def formats(pattern, nargs):
    """Whether .NET string.Format accepts the pattern with nargs arguments (composite format
    grammar: {index[,alignment][:format]}, {{ and }} escapes)."""
    i, n = 0, len(pattern)
    while i < n:
        c = pattern[i]
        if c == '}':
            if i + 1 < n and pattern[i + 1] == '}':
                i += 2
                continue
            return False
        if c != '{':
            i += 1
            continue
        if i + 1 < n and pattern[i + 1] == '{':
            i += 2
            continue
        i += 1
        j = i
        while j < n and pattern[j].isdigit() and pattern[j].isascii():
            j += 1
        if j == i:
            return False
        if int(pattern[i:j]) >= nargs:
            return False
        i = j
        while i < n and pattern[i] == ' ':
            i += 1
        if i < n and pattern[i] == ',':
            i += 1
            while i < n and pattern[i] == ' ':
                i += 1
            if i < n and pattern[i] == '-':
                i += 1
            j = i
            while j < n and pattern[j].isdigit() and pattern[j].isascii():
                j += 1
            if j == i:
                return False
            i = j
            while i < n and pattern[i] == ' ':
                i += 1
        if i < n and pattern[i] == ':':
            i += 1
            while i < n and pattern[i] != '}':
                if pattern[i] == '{':
                    return False
                i += 1
        if i >= n or pattern[i] != '}':
            return False
        i += 1
    return True


def pattern_problem(pattern):
    used = placeholders(pattern)
    if any(i < 0 or i > MAX_PLACEHOLDER for i in used):
        return f"a placeholder index outside 0–{MAX_PLACEHOLDER}"
    if not formats(pattern, max(used) + 1 if used else 0):
        return "the text cannot be formatted (check its braces and placeholders)"
    return None


def entry_problem(t, ref):
    one, other, plural = t
    r_one, r_other, r_plural = ref
    if plural != r_plural:
        return 'the English text is counted: give "one" and "other"' if r_plural else "the English text is not counted: give a plain text"
    p = pattern_problem(other)
    if p:
        return p
    if one is not None:
        p = pattern_problem(one)
        if p:
            return "singular form: " + p
    want = placeholders(r_other)
    got = placeholders(other)
    if got != want:
        return f"placeholders {{{','.join(map(str, sorted(got)))}}} differ from the English {{{','.join(map(str, sorted(want)))}}}"
    if one is not None and not placeholders(one) <= want:
        return "the singular form has a placeholder the English lacks"
    return None


def validate_against(table, ref):
    """(problems, coverage %) — as TranslationTable.ValidateAgainst."""
    problems, valid = list(table.problems), 0
    for key in sorted(table.strings):
        if key not in ref.strings:
            problems.append((key, "not in the English reference"))
            continue
        p = entry_problem(table.strings[key], ref.strings[key])
        if p:
            problems.append((key, p))
            continue
        valid += 1
    coverage = 100 if not ref.strings else (100 * valid) // len(ref.strings)
    return problems, coverage


def key_set_hash(ref):
    lines = sorted(f"{k}\t{'plural' if v[2] else 'text'}\t{','.join(map(str, sorted(placeholders(v[1]))))}"
                   for k, v in ref.strings.items())
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()[:16]


# ---- references and languages -------------------------------------------------------------

def version_key(name):
    """Sort order of reference versions: releases by number, develop last."""
    if name == "develop":
        return (1, ())
    return (0, tuple(int(p) if p.isdigit() else 0 for p in re.split(r"[.\-]", name)))


def load_references():
    refs = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "reference", "*.json"))):
        version = os.path.basename(path)[:-5]
        table, err = parse(open(path, encoding="utf-8").read())
        if table is None or table.code != "en":
            print(f"reference/{version}.json: unusable ({err or 'not English'}) — skipped", file=sys.stderr)
            continue
        refs[version] = table
    return dict(sorted(refs.items(), key=lambda kv: version_key(kv[0])))


def check_language(path, refs):
    """(table or None, errors, warnings, coverage per hash)."""
    rel = os.path.relpath(path, ROOT)
    code = os.path.basename(path)[:-5]
    table, err = parse(open(path, encoding="utf-8").read())
    if table is None:
        return None, [f"{rel}: {err}"], [], {}
    errors, warnings, coverage = [], [], {}
    if table.code != code:
        errors.append(f"{rel}: the file declares code '{table.code}'")
    if code == "en":
        errors.append(f"{rel}: English is the reference and lives in Nota, not here")
    for key, problem in table.problems:
        errors.append(f"{rel}: {key} — {problem}")
    if not refs:
        warnings.append(f"{rel}: no English reference to check against")
        return table, errors, warnings, coverage
    newest = list(refs.values())[-1]
    for key in sorted(table.strings):
        holders = [v for v, r in refs.items() if key in r.strings]
        if not holders:
            errors.append(f"{rel}: {key} — in no English reference (a typo, or a key Nota never had)")
        elif newest is not None and key not in newest.strings:
            warnings.append(f"{rel}: {key} — only in older references ({holders[-1]}); remove it once those versions are gone")
        else:
            ref = refs[holders[-1]]
            p = entry_problem(table.strings[key], ref.strings[key])
            if p:
                errors.append(f"{rel}: {key} — {p}")
    for version, ref in refs.items():
        _, cov = validate_against(table, ref)
        coverage[key_set_hash(ref)] = cov
    return table, errors, warnings, coverage


# ---- commands -----------------------------------------------------------------------------

def cmd_fixtures(folder):
    verdicts = json.load(open(os.path.join(folder, "verdicts.json"), encoding="utf-8"))
    ref, err = parse(open(os.path.join(folder, verdicts["reference"]), encoding="utf-8").read())
    if ref is None:
        print(f"fixture reference: {err}", file=sys.stderr)
        return 1
    fails = 0
    for name, want in verdicts["files"].items():
        table, err = parse(open(os.path.join(folder, name), encoding="utf-8").read())
        if not want["loads"]:
            ok = table is None
            print(f"{'PASS' if ok else 'FAIL'} {name}: rejected ({err})")
        else:
            if table is None:
                print(f"FAIL {name}: should load: {err}")
                fails += 1
                continue
            problems, cov = validate_against(table, ref)
            got = sorted({k for k, _ in problems})
            ok = got == sorted(want["problems"]) and cov == want["coverage"]
            print(f"{'PASS' if ok else 'FAIL'} {name}: problems {got}, coverage {cov} % "
                  f"(want {sorted(want['problems'])}, {want['coverage']} %)")
        fails += 0 if ok else 1
    return 1 if fails else 0


def file_sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def write_index(commit, results, refs):
    path = os.path.join(ROOT, "index.json")
    old = {}
    if os.path.exists(path):
        try:
            old = {l["code"]: l for l in json.load(open(path, encoding="utf-8")).get("languages", [])}
        except ValueError:
            old = {}
    languages = []
    for file, (table, coverage) in sorted(results.items()):
        sha = file_sha256(file)
        prev = old.get(table.code)
        version = (prev["version"] + (0 if prev.get("sha256") == sha else 1)) if prev else 1
        languages.append({
            "code": table.code, "name": table.name, "version": version,
            "commit": commit if not prev or prev.get("sha256") != sha else prev["commit"],
            "path": os.path.relpath(file, ROOT).replace(os.sep, "/"),
            "size": os.path.getsize(file), "sha256": sha, "coverage": coverage,
        })
    index = {
        "formatVersion": INDEX_FORMAT,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "references": {v: key_set_hash(r) for v, r in refs.items()},
        "languages": languages,
    }
    # keep "generated" stable when nothing else changed, so the publisher commits only real changes
    if os.path.exists(path):
        try:
            prev = json.load(open(path, encoding="utf-8"))
            if {k: v for k, v in prev.items() if k != "generated"} == {k: v for k, v in index.items() if k != "generated"}:
                index["generated"] = prev.get("generated", index["generated"])
        except ValueError:
            pass
    with open(path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"index.json: {len(languages)} languages, {len(refs)} references")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*")
    ap.add_argument("--fixtures", metavar="DIR")
    ap.add_argument("--write-index", metavar="COMMIT")
    a = ap.parse_args()
    if a.fixtures:
        return cmd_fixtures(a.fixtures)
    refs = load_references()
    files = a.files or sorted(glob.glob(os.path.join(ROOT, "languages", "*.json")))
    errors, results = [], {}
    for path in files:
        table, errs, warns, coverage = check_language(os.path.abspath(path), refs)
        for w in warns:
            print("warning: " + w)
        errors += errs
        if table is not None and not errs:
            results[os.path.abspath(path)] = (table, coverage)
            covs = ", ".join(f"{v} {coverage.get(key_set_hash(r), 0)} %" for v, r in refs.items())
            print(f"ok: {os.path.relpath(path, ROOT)} — {table.name}" + (f" ({covs})" if covs else ""))
    for e in errors:
        print("error: " + e, file=sys.stderr)
    if a.write_index:
        if errors:
            print("index.json not written: fix the errors first", file=sys.stderr)
        else:
            write_index(a.write_index, results, refs)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
