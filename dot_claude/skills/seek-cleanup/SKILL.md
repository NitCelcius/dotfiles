---
name: seek-cleanup
description: Finds dead code, unused imports, orphaned CSS, and other clutter across a codebase. Use when asked for cleanup; just-changed code → /simplify.
---

# seek-cleanup

Search for code, styles, and resources that may be removable, then report them
as a numbered list.

## Steps

1. Confirm the scope: current file, directory, or whole project.
2. Search for the following:
   - Unused imports / exports
   - CSS class definitions not referenced from templates or Markdown
   - Commented-out code blocks
   - Declared but unused variables or functions
   - Empty files and unreachable code
3. Output removal candidates as a numbered list with `file:line` and the reason.
4. **Delete only after confirmation.** Do not auto-delete.
