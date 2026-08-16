---
name: feedback-on-compaction
description: Review whether Claude Code context compactions were well timed and paid back their estimated overhead.
disable-model-invocation: true
allowed-tools: Bash
---

# Feedback on compaction

When the user invokes this skill, do not run analysis immediately.

First ask exactly one concise question: **Which scope should I analyze: this repository or all projects?** Wait for the user's answer.

After the user answers:

- For "this repository", run `python "$HOME/.claude/feedback-on-compaction/feedback_on_compaction.py" report --scope repo` from the repository directory.
- For "all projects", run `python "$HOME/.claude/feedback-on-compaction/feedback_on_compaction.py" report --scope all`.
- Do not choose a scope on the user's behalf, even if arguments were supplied with the invocation.
- Present the report in the language the user is currently using.
- Lead with the recommendation, then the supporting measurements and important limitations.
- Do not read or quote transcript text or the collected `compact_summary` fields. The report command deliberately emits only token and structural metadata.
