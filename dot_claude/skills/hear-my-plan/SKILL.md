---
name: hear-my-plan
description: Use before any new project, feature, or architecture change when the user dumps a long, rough, or incomplete idea (roughly 120+ words). Hear the idea out, pull it back to purpose and goals, and produce a clear execution plan. Do NOT implement until the user approves. Skip small, clear, well-scoped tasks. Always available explicitly via /hear-my-plan.
---

# Hear My Plan

The user tends to throw long, unstructured, incomplete ideas. The default failure mode is to treat that dump as an implementation order and build something misaligned. Don't. First hear it out, reorganize it from the root, and agree on a plan. Only build after the user explicitly approves.

## When this fires
- Auto: a new project / feature / architecture change described in a long, rough message (roughly 120+ words).
- Explicit: `/hear-my-plan` (any length).
- Skip: small, clear, well-scoped tasks, or plain fact questions. If you're clearly in this zone, exit the skill and proceed normally. (The ~120-word threshold exists so small features don't trip this.)

<HARD-GATE>
Do NOT write code, scaffold, run implementation tools, or invoke any implementation skill until you have presented a plan AND the user has approved it AND told you to implement. Presenting the plan is not permission to build.
</HARD-GATE>

## Process
1. Explore context, only if it exists. If there's a relevant codebase, docs, or files, read them first. This skill is not limited to programming; for non-code plans with no repo, skip this.
2. Triage scope. Decompose ONLY if the idea mixes two or more new features, or two or more projects. Then reflect back: independent pieces, dependencies, suggested order; agree which piece to tackle now; grill only that piece. Don't decompose aggressively — organizing is the point. A single piece: skip decomposition.
3. Clarify one question at a time. Pull back to the root: necessity, purpose, intended effect, then goals, then the execution plan. Wait for each answer before the next. Carry your recommended answer and reasoning with each question. Multiple choice or open-ended both fine. Dig deeper on answers; a pivot may result, which is welcome.
4. Offer 2-3 approaches only when a real fork exists, with your recommendation. Don't force it every time.
5. Light self-check before presenting: re-read the plan for placeholders, contradictions, ambiguity, scope creep. Fix inline.
6. Present the plan, then STOP and ask whether to implement.

## Plan structure
Self-contained: a fresh session must be able to act on it without the chat history. Write it for a general university graduate (non-specialist) in plain terms; programming details may assume an engineer. No alternatives section — this is an execution plan.

1. Background & problem — why, restated in 1-2 sentences so it reads cold
2. Purpose & intended effect — what gets better
3. Goals / success criteria — define as concretely as you can; not every plan has a measurable metric, but try
4. Execution plan — ordered steps with dependencies made explicit
5. Out of scope — what you deliberately won't do (YAGNI)
6. Open questions — unresolved points, so a fresh session won't guess and re-misalign

## Output & stopping
- Default: present the plan in chat (the conversation is saved).
- Context-saving exit: when context is getting heavy, write the plan to a file and end, so implementation starts cold from the file.
- Language: dialogue and plan in Japanese, plain for laypeople; programming terms at engineer level. If the repo/context is English, output in English.
- After presenting: always pause and ask "implement this?" Never auto-chain into building.

## Don't
- Don't treat the initial idea dump as an implementation order.
- Don't import "every trivial task needs a design" — small, clear tasks exit the skill.
- Don't auto-invoke another skill after the plan. Wait for the user.
