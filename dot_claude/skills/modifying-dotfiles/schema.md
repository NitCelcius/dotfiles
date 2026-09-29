# 設定変更ログ database schema

Data source ID (use this as the `notion-create-pages` parent):
`b44e1456-29cc-472b-97f9-7d58c105484b`

Last confirmed against the live schema: 2026-09-29. If a create call rejects a property or
option below as unrecognized, the schema has drifted: re-fetch the data source and update
this file.

## Properties to set

| Property | Type | Notes |
|---|---|---|
| `変更` | title | Required. One line, the what. |
| `日付` | date | Commit date (author date, `YYYY-MM-DD`). |
| `対象` | select | Exactly one. Options below. |
| `理由` | text | The why. `不明` when unknown. |
| `確度` | select | Exactly one. Options below. |
| `リンク` | url | Commit SHA URL. Dedupe key: one row per URL. |

## 対象 (pick one)

claude, codex, zed, git, shell, chezmoi, other

`chezmoi` is for the repo itself (CI, docs, layout, chezmoi config). Use `other` when
nothing fits; never type a new value.

## 確度 (pick one)

- 確定: the user stated the reason, or the session made it explicit.
- 推定: the reason was inferred from a commit body or diff.
- 不明: the reason is unknown; `理由` is also `不明`.

## Example call shape

```
notion-create-pages({
  parent: { type: "data_source_id", data_source_id: "b44e1456-29cc-472b-97f9-7d58c105484b" },
  pages: [{
    properties: {
      "変更": "...",
      "date:日付:start": "2026-09-29",
      "対象": "claude",
      "理由": "...",
      "確度": "確定",
      "リンク": "https://github.com/<owner>/<repo>/commit/<sha>"
    }
  }]
})
```

Dedupe check before creating: query the data source in rows mode with a `リンク` filter
(`string_is` on the commit SHA URL) and skip the write when a row comes back.
