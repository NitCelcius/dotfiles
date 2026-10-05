---
name: log-skill-miss
description: Logs a skill that failed to trigger to Notion. Use when the user describes a skill instead of naming it, runs one late by name, or says one should have run.
---

# Log skill miss

A skill whose description is too thin stops triggering, and the miss is easy to forget
across devices. This skill records each miss in the Notion database "スキル発火ミス" so
the descriptions can be fixed later in one pass.

## When it is a miss

| The user… | 発覚 |
|---|---|
| describes a skill by what it does, without its name ("could we run a skill that…") | 内容で指示 |
| runs a skill by name after the moment it should have triggered on its own | 名前で指示 |
| says afterwards that a skill should have run | 事後に指摘 |

Not a miss: the user opens a fresh task with `/<skill>` before anything could have
triggered it.

## Steps

1. **Serve the request first.** For 内容で指示, match the user's wording against the
   available skill descriptions, say which skill it is by name, and run it. If two
   skills fit, ask which one. If none fits, say so and log nothing.
2. **Draft the row.**
   - スキル: the skill name.
   - 日付: today.
   - 依頼内容: one line on what the user asked or was doing at the time. No paths,
     secrets, or personal detail.
   - 発覚: from the table above.
   - 端末: output of `hostname`.
   - 状態: 未対応.
3. **Skip duplicates.** Query the data source for a row with the same スキル and 日付;
   if one exists for the same request, do not write another.
4. **Write it without asking**, then tell the user in one line, with the row link.
   Logging is cheap and the user may delete a row.

Japanese text follows the Content rules in `save-to-knowledge/SKILL.md`.

## Fixing the misses

When the user asks to fix logged misses: query rows with 状態 = 未対応, adjust each
skill's description (format per `writing-skills`) through `modifying-dotfiles`, then set
状態 to 対応済み and 対応リンク to the commit or PR. Set 対応不要 when the skill should
not have triggered after all.

## Database

Data source: `collection://6943285c-cdf8-4ff4-8a6e-d53934296ee9`

```
notion-create-pages({
  parent: { type: "data_source_id", data_source_id: "6943285c-cdf8-4ff4-8a6e-d53934296ee9" },
  pages: [{
    properties: {
      "スキル": "chezmoi-sync",
      "date:日付:start": "2026-10-05",
      "依頼内容": "...",
      "発覚": "内容で指示",
      "端末": "...",
      "状態": "未対応"
    }
  }]
})
```

Options: 発覚 is one of 名前で指示, 内容で指示, 事後に指摘. 状態 is one of 未対応,
対応済み, 対応不要. If a create call rejects a property, re-fetch the data source and
update this section.
