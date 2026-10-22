---
name: my-skill
description: One or two sentences on what this skill does and when Claude should use it. Name the triggers, such as the words a user might type or the kind of task, because Claude reads this line to decide whether to load the skill.
---

# My Skill

Short summary of what this skill helps with.

## When to use

- The user asks for <task>.
- The project contains <file or tool> and the task involves it.

## When not to use

- <Cases that look similar but should be handled another way.>

## Steps

1. Gather what you need: <files to read, commands to run, questions to ask>.
2. Do the work: <the core procedure, in order>.
3. Check the result: <tests, lint, or a manual check>.
4. Report back: <what to tell the user and in what form>.

## Rules

- <Conventions to follow, e.g. naming, formatting, style.>
- <Things to never do.>

## Examples

**Input:** <a sample request>

**Output:** <what a good result looks like>

## Reference files

Put longer material next to this file and link it here, so it loads only when needed:

- `reference.md`: <detailed docs>
- `scripts/`: <helper scripts Claude can run>
