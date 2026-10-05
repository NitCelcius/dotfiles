---
name: chezmoi-sync
description: Applies chezmoi without dropping live-only fields from `modify_` templates. Use before `chezmoi apply`, or when `chezmoi status` shows `MM`.
---

# Chezmoi Sync

`chezmoi status`/`chezmoi diff` answer one question — what would `chezmoi apply`
change — not "what should I commit." The two directions never share a command:

- **Commit** (source → git): plain `git status`/`git log @{u}..` in the source repo.
  Nothing chezmoi-specific about it; use `commit-scope-audit` for the actual staging.
- **Apply** (source → live home directory): `chezmoi status`/`chezmoi diff`. This is
  what this skill covers.

Don't conflate them: a clean `chezmoi status` says nothing about uncommitted source
changes, and a clean `git status` says nothing about unapplied ones.

## Step 1: Run both, separately

```bash
git -C <source> status
git -C <source> fetch origin && git -C <source> log --oneline @{u}..
chezmoi status
```

If `chezmoi status`/`diff` prints `config file template has changed, run chezmoi init
to regenerate config file`, check `.chezmoi.toml.tmpl`'s own header comment for
whether it authorizes an unattended `chezmoi init` (this repo's does, for the main
checkout — never run `chezmoi init` from inside a `.worktree/` copy, since it bakes
in whatever `sourceDir` is in effect). Run it, then re-run `chezmoi status`.

## Step 2: Split by status code

`chezmoi status` prints a two-character code per path. A single letter (` M`, `A `)
is a plain, one-directional file — target (from source) differs from what's live, and
`chezmoi apply` is a straight overwrite in that direction. Bucket these as **safe**.

Two letters (`MM`) mean the path has a `modify_<name>` source script — a
chezmoi:modify-template that receives the live file's content on stdin and emits the
would-be-applied content. `chezmoi diff` for these compares the current live file
against *that script's output run against the current live file* — not against a
frozen source snapshot. That's a partial-management merge, not a git-style conflict,
but it can still lose data if the script's carry-over list is stale.

## Step 3: For every `MM` path, read the modify script before trusting the diff

1. Find the script: it sits next to the target's would-be source path, named
   `modify_<basename>` (e.g. live `~/.codex/config.toml` → source
   `dot_codex/modify_config.toml`). `chezmoi source-path` does not resolve these —
   search the source tree for `modify_<basename>` under the matching directory.
2. Read its header comment and the fields/tables it explicitly carries over from
   `.chezmoi.stdin` (a `pick`, a `dig`/`get` on specific keys, a whole-table copy).
   Everything not on that list is source-owned: the script's hardcoded body
   overwrites it on every apply, regardless of what's live.
3. Run `chezmoi diff -- <target>` for that one path and classify every non-cosmetic
   hunk:
   - **Reordering/whitespace only** (key order, quote style, line-ending changes with
     no value change) — cosmetic, from re-serialization. Ignore.
   - **A source-owned field's value changed** — intended forward sync. Safe.
   - **A field appears only on the removed (`-`) side and nowhere on the added (`+`)
     side, and it is not on the script's carry-over list** — a silent drop. The
     script's carry-over list is missing it. Do not apply until this is resolved.
   - **A field's value differs on both sides with no stated precedence** (the script
     doesn't pick a winner because it isn't on its own tracked list, e.g. a live
     value the source body also happens to hardcode) — a real conflict. Needs a
     decision.

## Step 4: Report two buckets, not one

- **Safe to apply**: every single-letter path, plus any `MM` path where step 3 found
  only cosmetic and intended-forward-sync hunks.
- **Needs a decision**: any `MM` path with a silent drop or an unresolved conflict.
  Name the exact field, both values, and which side would win on a blanket apply.
  Two ways to resolve: extend the modify script's carry-over list (if the live value
  should always survive an apply), or accept the source's value (if the live one was
  incidental drift) — state which you're recommending and why, then let the user pick.

Never run a blanket `chezmoi apply` while a "needs a decision" path is unresolved —
it silently resolves in favor of the template's hardcoded side. Apply the safe bucket
with explicit paths (`chezmoi apply -- <path> <path> ...`) or, once every `MM` path is
cleared, a plain `chezmoi apply`.

## Don't

- Don't treat `MM` as a merge conflict in the git sense — it's the modify_ template
  doing its job. Most `MM` diffs are cosmetic re-serialization or intended forward
  sync; only a silent drop or a genuine two-sided disagreement is worth a stop.
- Don't skip reading the modify script and infer intent from the diff alone — the
  diff shows a rendered result, not which side is source-owned vs live-owned.
- Don't run `chezmoi init` to clear the template-changed warning without checking the
  template's own comment first, and never from a worktree checkout.
- Don't fold the commit-side check into the apply-side one — they use different
  commands and answer different questions.
