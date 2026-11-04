#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Egor Khindikaynen (Nota). See LICENSE for license terms.
"""
Pulls Nota's English references into reference/.

For each nota-daw/nota release tag vX.Y.Z that has no reference/X.Y.Z.json yet, fetches the
English reference (src/managed/Nota.Application/Localization/en.json) as it was at that tag;
always refreshes reference/develop.json from the develop branch, so translators can work on
texts before they ship. Tags from before keyed texts (no en.json there, or format < 2) are
skipped. Nothing is pushed from Nota: references are pulled, so no secret is shared between
the repositories (Nota spec 077, research R7).

Uses GITHUB_TOKEN when set (higher API rate limit). Standard library only.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.environ.get("NOTA_REPO", "nota-daw/nota")
EN_PATH = "src/managed/Nota.Application/Localization/en.json"
TAG_RE = re.compile(r"^v(\d+\.\d+\.\d+)$")


def get(url, accept="application/vnd.github+json"):
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "nota-translations-sync"})
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def tags():
    out, page = [], 1
    while True:
        batch = json.loads(get(f"https://api.github.com/repos/{REPO}/tags?per_page=100&page={page}"))
        out += [t["name"] for t in batch]
        if len(batch) < 100:
            return out
        page += 1


def reference_at(ref):
    """The English reference at a git ref, or None if it has none in format 2."""
    try:
        raw = get(f"https://raw.githubusercontent.com/{REPO}/{ref}/{EN_PATH}", accept="*/*")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    return raw if data.get("formatVersion") == 2 and data.get("code") == "en" else None


def write(name, raw):
    path = os.path.join(ROOT, "reference", f"{name}.json")
    old = open(path, "rb").read() if os.path.exists(path) else None
    if old == raw:
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(raw)
    return True


def main():
    changed = []
    for tag in tags():
        m = TAG_RE.match(tag)
        if not m or os.path.exists(os.path.join(ROOT, "reference", f"{m.group(1)}.json")):
            continue
        raw = reference_at(tag)
        if raw is not None and write(m.group(1), raw):
            changed.append(m.group(1))
    raw = reference_at("develop")
    if raw is not None and write("develop", raw):
        changed.append("develop")
    print("references updated: " + (", ".join(changed) if changed else "none"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
