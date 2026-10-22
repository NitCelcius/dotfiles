---
name: friction
description: Records a friction, a missed skill, or an idea to the Notion 摩擦ログ. Use for /friction, when the user asks to note something that went wrong, or when a skill should have run but did not.
---

# Friction

Frictions noticed in one session are forgotten by the next, and they happen on several
machines. This skill records each one as a row in the Notion database 摩擦ログ, so the
monthly review can count how often each recurs. A friction becomes a dotfiles change
only when it recurs: a `CLAUDE.md` rule on the second occurrence, a skill on the third.

## What to record

| 種別 | When |
|---|---|
| 摩擦 | Something went wrong or cost a retry: a tool failed, Claude misread the request, a step had to be redone. |
| スキル発火ミス | The user describes a skill instead of naming it, runs one by name after it should have triggered, or says afterwards that one should have run. Opening a fresh task with `/<skill>` is not a miss. |
| アイデア | The user wants to keep an idea for later. |

If it is unclear which 種別 fits, pick the closest and say so in one line; do not ask.

## Steps

1. **Serve the request first.** For a skill described by what it does, name the matching
   skill and run it. If two fit, ask which one. If none fits, say so and log nothing.
2. **Collect the context** with one shell call:
   `hostname; echo "$CLAUDE_CODE_SESSION_ID"; basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"`
   These fill 端末, セッション and プロジェクト. Never leave them empty; write `不明` if a
   value is missing.
3. **Draft the row.**
   - 内容: one line a reader can act on without the transcript: what happened, in which
     step. No paths, secrets or personal detail.
   - 種別: from the table above.
   - 依頼内容: one line on what the user was doing at the time.
   - 関連スキル: the skill name, for スキル発火ミス; otherwise leave it empty.
   - 発覚: for スキル発火ミス only: 内容で指示, 名前で指示 or 事後に指摘.
   - 日付: today. 回数: 1. 状態: 未対応.
4. **Merge a repeat.** Query rows with the same 種別 and 状態 = 未対応. If one describes
   the same friction, raise its 回数 by one, set 日付 to today, and append a line
   `日付 端末 プロジェクト セッション: 内容` to its page body instead of creating a row.
5. **Write without asking**, then tell the user in one line, with the row link. Logging
   is cheap and the user may delete a row.

Japanese text follows the Content rules in `save-to-knowledge/SKILL.md`.

## Resolving rows

When the user asks to work through the log: query rows with 状態 = 未対応, sorted by
回数. Fix through `modifying-dotfiles`, then set 状態 to 対応済み and 対応リンク to the
commit or PR. Set 対応不要 when the row needs no change.

## Database

Data source: `collection://6943285c-cdf8-4ff4-8a6e-d53934296ee9`

```
notion-create-pages({
  parent: { type: "data_source_id", data_source_id: "6943285c-cdf8-4ff4-8a6e-d53934296ee9" },
  pages: [{
    properties: {
      "内容": "...",
      "種別": "摩擦",
      "依頼内容": "...",
      "関連スキル": "",
      "date:日付:start": "2026-10-22",
      "回数": 1,
      "状態": "未対応",
      "端末": "...",
      "プロジェクト": "...",
      "セッション": "..."
    }
  }]
})
```

Options: 種別 is one of 摩擦, スキル発火ミス, アイデア. 発覚 is one of 名前で指示,
内容で指示, 事後に指摘. 状態 is one of 未対応, 対応済み, 対応不要. If a create call
rejects a property, re-fetch the data source and update this section.
