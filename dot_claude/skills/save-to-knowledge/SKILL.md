---
name: save-to-knowledge
description: Save a finding, decision, or workflow discovery from this session to the user's Notion "Knowledge(s)" database. Use when the user says "save this to knowledge", "note this in Notion Knowledge(s)", "add this to my knowledge base", or similar. Writes directly with a hard-coded schema and writing-style rules — no need to fetch the database structure or the style-guide pages from Notion first.
---

# Save to Notion Knowledge(s)

Writes one entry to the user's personal "🧮 Knowledge(s)" database in Notion. The database
schema, tag options, and writing-style rules are hard-coded below so this skill never needs to
query Notion for them — only the actual page-creation call touches the network.

Full property schema and tag option lists are in `schema.md` — read it before building the
`properties` object, since 中ジャンル alone has ~100 options and guessing one that isn't in the
list will fail or silently create an orphan tag.

## When NOT to use this

If the user's Notion "AI / General" persona (et) is who should be doing the writing — e.g. they
explicitly ask *that* assistant, in a Notion AI chat, to record something — this skill doesn't
apply; it's for when *you* (Claude Code) are asked to log a finding from *this* session.

## Workflow

1. **Identify the finding.** Pull it from what was just established in this session — a decision,
   a workaround, a discovered constraint, a preference the user stated. Do not go re-derive or
   re-research it.
2. **Draft the entry** (see Content rules below) and show it to the user before writing:
   - `Name` — a short, specific title, not a generic label
   - `Description` — one sentence, sub-title length
   - Body — a few bullet points, following the writing-style rules below
   - Proposed tags: `カテゴリ` (pick exactly one), `大ジャンル` (usually one), `中ジャンル`
     (usually one, occasionally two), `わたしtag` (zero or more)
3. **Create the page** via `notion-create-pages`, parent:
   `{"type": "data_source_id", "data_source_id": "ebb90a48-79c1-43bf-903c-5c1c192051ab"}`.
   Property names and exact option strings are in `schema.md` — copy them verbatim, including the
   full-width characters in property names like `カテゴリ`.
4. **Report back** the resulting page URL. Don't ask for confirmation before step 3 unless the
   draft has a genuinely ambiguous tag choice — showing the draft in step 2 already gives the user
   a chance to redirect before it's written.

## Content rules

Write the `Name`, `Description`, and body in whichever language fits the finding (this database
mixes Japanese and English entries; match whichever the finding itself was discussed in). For
Japanese content, follow these rules strictly — they're the same output rules the user's Notion AI
persona enforces on all page content, hard-coded here so this skill doesn't need to fetch them:

- No full-width colon `：`. Write it out as a sentence, or fold it into the lead-in clause.
- Prefer half-width parentheses `()` over full-width `（）`. Exception: quoted text, code, and
  proper nouns keep their original form.
- No dash characters (`—`, `–`, `―`). Don't use inverted/poetic phrasing. Don't insert an English
  word where a Japanese one works — exceptions are config keys, API/tool names, and terms that
  would become inaccurate if translated.
- Avoid force-only emphasis words that add no fact (`こそ`, `〜しきった`, `核心`, etc.). When degree
  or scope matters, state the concrete condition or number instead.
- Don't preface a bullet list or conclusion with "整理すると" / "重要なのは". Lead with the content.
- Bullets are for items referenced separately (comparisons, steps, options). Content connected by
  cause and effect goes in a full sentence, not a label-plus-explanation pair on one line.
- Aim for vocabulary a first-year university student would follow. Use a technical term or
  abbreviation only when it's genuinely necessary, and don't over-explain it once used.
- When building block content, use actual line breaks, not an escaped \n sequence.
- Verify the created page renders real paragraphs/line breaks, not a literal backslash-n, before reporting the URL back.

For English content, use plain, direct technical prose — no house style beyond that.

## Reusing tags over inventing them

The `カテゴリ`, `大ジャンル`, `中ジャンル`, and `わたしtag` properties are constrained option
lists. Always pick from the existing options in `schema.md`. If nothing genuinely fits, leave that
property empty rather than typing a new value — flag it to the user instead of silently expanding
the schema.
