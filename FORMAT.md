# Language file format

What `tools/validate.py` checks here and what Nota accepts when it loads a language (Nota spec 077).

## Shape

```json
{
  "formatVersion": 2,
  "code": "fr",
  "name": "Français",
  "plural": "one_is_0_1",
  "notes": "Glossary, register, conventions for translators.",
  "strings": {
    "common.save": "Enregistrer",
    "menu.file.open": "Ouvrir",
    "clip.open": "Ouvrir le clip",
    "arrangement.selection.tracks": {
      "one": "{0} piste sélectionnée",
      "other": "{0} pistes sélectionnées"
    }
  }
}
```

## Rules

| Rule | Detail |
|---|---|
| `formatVersion` | `2`. `1` (text-keyed) and anything higher are rejected with a logged error; the language is not offered. |
| `code` | Lower-case BCP-47 primary tag (`fr`, `de`, `pt-br` allowed); equals the file name. `en` only for the reference. |
| `name` | The language's own name, shown in the picker. |
| `plural` | A rule id the app knows: `one_is_1`, `one_is_0_1`. Unknown → file rejected. Required except in `en.json` (`one_is_1` implied). |
| Keys | Match `^[a-z0-9_]+(\.[a-z0-9_]+)+$`, ≤ 80 chars, unique. |
| Values | A non-empty string, or a plural object with `other` required; `one` optional (missing → `other`). Unknown categories ignored. An empty string counts as missing (English shown). |
| Shape | A key that is a plural object in the reference must be one here, and the other way round; mismatch → entry invalid (English shown), reported. |
| Placeholders | `{0}` … `{9}` with optional format (`{0:0.0}`). `other` uses exactly the reference's placeholders, any order; `one` may drop but not add. `{{` `}}` literal. Every form must format (no stray brace, no `{0,abc}`, no index past 9); one that does not is an invalid entry, not counted in coverage. |
| Missing key | Run time: English. Coverage: counted missing. |
| Unknown key (not in the reference checked against) | Run time: ignored. Repository check: error if the key is in **no** reference, warning if only in older ones. |
| Malformed file | Language skipped, error logged, English kept; Nota always starts. |
| `en.json` extra rule | Every value present; `code` = `en`; this file *is* the reference. |

## Coverage

`translated valid entries of reference keys ÷ reference keys`, per reference, rounded down
to a whole percent.

## Key-set hash

SHA-256 (lower-case hex, first 16 chars) of the UTF-8 lines, sorted ordinally and joined with
`\n`: `key \t (text|plural) \t sorted placeholder indices joined by ","`. Computed
identically by the app, the smoke test and `tools/validate.py`.

# index.json

```json
{
  "formatVersion": 1,
  "generated": "2026-11-20T10:00:00Z",
  "references": {
    "0.43.0": "3f9a1c0d7e2b4a51",
    "0.44.0": "3f9a1c0d7e2b4a51",
    "develop": "b81e09f2c4d3a677"
  },
  "languages": [
    {
      "code": "fr",
      "name": "Français",
      "version": 12,
      "commit": "a1b2c3d…(40 hex)",
      "path": "languages/fr.json",
      "size": 214533,
      "sha256": "…64 hex…",
      "coverage": { "3f9a1c0d7e2b4a51": 100, "b81e09f2c4d3a677": 97 }
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `formatVersion` | Index shape. The app ignores an index with a higher major and says "update Nota to see more languages". |
| `references` | Nota version → key-set hash of its `en.json`. Versions with the same keys share a hash. |
| `languages[].version` | Integer, +1 each time the file's content changes on `main`. Shown as "update available" when greater than the installed one. |
| `commit` | The commit whose `path` has exactly `size` / `sha256`; the app downloads `<base>/<commit>/<path>`. |
| `coverage` | Per key-set hash, percent (see language-file contract). Only languages that pass validation are listed. |

## App behaviour

- Own hash in `coverage` → show that coverage.
- Own hash absent → use the newest `references` entry with a version ≤ the app's and show its
  coverage; none → show the language without coverage.
- Fetch failure, malformed index → installed languages only, "More languages are available
  online" (or the error) in the row; no dialog.
