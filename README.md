# Nota translations

The interface languages of [Nota](https://github.com/nota-daw/nota), the free DAW. Nota itself
ships in English; every other language lives here, one file each, and Nota downloads the one
you pick in **Preferences → Appearance → Language** (from the next Nota release; until then
French is also built into the app). Fixing or adding a translation is a pull
request to this repository: no build of Nota, no waiting for a release.

| Language | File |
|---|---|
| Français | [`languages/fr.json`](languages/fr.json) |

## How it fits together

- **Keys.** Nota asks for every text by a stable key such as `preferences.language.restart`.
  The English text of each key is Nota's *English reference*,
  [`en.json`](https://github.com/nota-daw/nota/blob/develop/src/managed/Nota.Application/Localization/en.json)
  in the Nota repository.
- **References.** The [`published`](../../tree/published) branch holds a copy of the English
  reference for every Nota release (`reference/0.59.0.json` …) and for the code in progress
  (`reference/develop.json`). They are pulled from Nota automatically.
- **Languages.** [`languages/<code>.json`](languages/) translates the keys of the references.
  A file may be partial: anything missing shows in English.
- **Index.** `index.json` on the `published` branch is what Nota reads: each language with its
  version, checksum and how complete it is for each Nota version. It is generated after every
  merge; nobody edits `published` by hand.

## Fix or complete a translation

1. Open `languages/<code>.json` and find the key. Its English is the same key in
   [`reference/develop.json`](../../blob/published/reference/develop.json) (texts Nota has today) or in the
   reference of the release you use.
2. Change the text. Keep every placeholder — `{0}`, `{1}`, possibly with a format such as
   `{0:0.0}` — in any order; write a literal brace as `{{` or `}}`.
3. A counted text has two forms: `{ "one": "{0} piste", "other": "{0} pistes" }`. Which count
   takes `one` is the file's `plural` rule (see below). `one` may leave the number out
   ("Une piste"); `other` keeps every placeholder.
4. Open a pull request. The **check** job tells you, without building Nota, whether every entry
   is valid and how complete the language is. An entry it rejects names its key and the problem.

Follow the language's conventions in its `notes` field (French: the glossary linked there —
infinitive for actions, sentence case, a narrow no-break space before `:` `;` `?` `!`). Device
and parameter names (Nota Volt, Cutoff, LFO …) stay in English.

## Add a language

1. Copy `languages/fr.json` to `languages/<code>.json` — `<code>` is the lower-case language
   tag (`de`, `es`, `pt-br`).
2. Set `code` to the same tag, `name` to the language's own name (`Deutsch`), and `plural`:
   - `one_is_1` — only 1 is singular (English, German, Spanish, Italian …);
   - `one_is_0_1` — 0 and 1 are singular (French, Brazilian Portuguese …).

   A language that needs more forms (`few`, `many`: Russian, Polish, Arabic …) needs a new rule
   in Nota first — open an issue there.
3. Write your own `notes` (glossary, register), translate what you can and **delete the rest**:
   an entry left in French is shown in French.
4. Open a pull request.

## Preview before publishing

In Nota (from the release that downloads languages), **Preferences → Appearance → Language →
Load file…** runs Nota in a language file from
your disk after a restart, with its problems listed under the row. Or start Nota once with
`NOTA_UI_LANGUAGE=/path/to/de.json`.

## The rules

The file format, checked by [`tools/validate.py`](tools/validate.py) here and by Nota itself, is
in [FORMAT.md](FORMAT.md). Run the check locally with Python 3:

```sh
python3 tools/sync_references.py   # pull Nota's English references
python3 tools/validate.py          # check every language
```

## License

Translations are part of Nota and licensed like it: [AGPL-3.0-only](LICENSE). By opening a pull
request you agree to license your contribution under it.
