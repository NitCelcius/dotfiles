---
name: check-my-code-format
description: Use when asked to verify naming conventions, design token usage, CSS class prefixes, or other code style standards against project conventions.
---

# check-my-code-format

Check naming conventions, design token usage, and code style against project
conventions, then report the findings.

## Steps

1. Read both project and global `CLAUDE.md` files to understand the conventions.
2. Verify the following:
   - **Naming conventions**: CSS class prefixes, component names, and prop names
   - **Design tokens**: Whether hard-coded color values such as `#xxx` and `rgb()` have been replaced with `--token-*` / `--color-*`
   - **File and directory structure**: Whether the code follows the component boundary rules in `CLAUDE.md`
   - **Type scale**: Whether `font-size` avoids raw `rem` / `px` values and preferably uses `--text-*` tokens
3. Output violations as a numbered list with `file:line` and the expected approach.
4. Do not auto-fix. Only make changes when explicitly asked to fix them.
