---
name: using-skills
description: Use when starting any conversation - establishes when to invoke skills. Skip if the edit target is explicit (file + change clearly stated). Invoke for open-ended design, feature work, or tasks where approach is unclear.
---

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

## Instruction Priority

User instructions always take precedence:

1. **User's explicit instructions** (CLAUDE.md, direct requests) — highest priority
2. **Skills** — override default behavior where they conflict
3. **Default system prompt** — lowest priority

## The Rule

**If the edit target is explicit, act directly. If the task is open-ended, check for skills first.**

An "explicit edit target" means: a specific file AND a specific change are both stated in the request.

- `"edit theme.css to rename .accent-yellow to .u-accent-yellow"` → explicit → act directly
- `"add a new stage section"` → open-ended → check for skills
- `"fix the bug in SlideGrid where columns don't align"` → approach unclear → check for skills

## Decision Flow

```dot
digraph skill_flow {
    "User message received" [shape=doublecircle];
    "Edit target explicit?\n(specific file + specific change)" [shape=diamond];
    "Any skill applies?" [shape=diamond];
    "Invoke Skill tool" [shape=box];
    "Announce: 'Using [skill] to [purpose]'" [shape=box];
    "Has checklist?" [shape=diamond];
    "Create TodoWrite todos" [shape=box];
    "Follow skill exactly" [shape=box];
    "Respond directly" [shape=doublecircle];

    "User message received" -> "Edit target explicit?\n(specific file + specific change)";
    "Edit target explicit?\n(specific file + specific change)" -> "Respond directly" [label="yes"];
    "Edit target explicit?\n(specific file + specific change)" -> "Any skill applies?" [label="no"];
    "Any skill applies?" -> "Invoke Skill tool" [label="yes"];
    "Any skill applies?" -> "Respond directly" [label="no"];
    "Invoke Skill tool" -> "Announce: 'Using [skill] to [purpose]'";
    "Announce: 'Using [skill] to [purpose]'" -> "Has checklist?";
    "Has checklist?" -> "Create TodoWrite todos" [label="yes"];
    "Has checklist?" -> "Follow skill exactly" [label="no"];
    "Create TodoWrite todos" -> "Follow skill exactly";
}
```

## How to Access Skills

**In Claude Code:** Use the `Skill` tool. When you invoke a skill, its content is loaded and presented to you — follow it directly. Never use the Read tool on skill files.

## Skill Priority

When multiple skills could apply:

1. **Process skills first** (brainstorming, writing-plans) — determine HOW to approach the task
2. **Implementation skills second** — guide execution

## Skill Types

**Rigid**: Follow exactly. Don't adapt away discipline.

**Flexible**: Adapt principles to context.

The skill itself tells you which type it is.
