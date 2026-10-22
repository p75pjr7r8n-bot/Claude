#!/usr/bin/env bash
# SessionStart hook: loads the using-superpowers skill into context,
# like the Superpowers plugin does. Here the skills live in .claude/skills
# instead of a plugin, so "superpowers:<name>" means the project skill <name>.
set -euo pipefail

root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
skill_md="$root/.claude/skills/using-superpowers/SKILL.md"
if [ -r "$skill_md" ]; then
  content="$(<"$skill_md")"
else
  content="Error reading using-superpowers skill"
fi

escape_for_json() {
  local s="$1"
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  s="${s//$'\n'/\\n}"
  s="${s//$'\r'/\\r}"
  s="${s//$'\t'/\\t}"
  printf '%s' "$s"
}

note="Superpowers is installed as project skills in .claude/skills, not as a plugin. Wherever a skill says superpowers:<name>, invoke the project skill <name> (for example superpowers:brainstorming means the brainstorming skill)."
context="<EXTREMELY_IMPORTANT>
You have superpowers.

${note}

**Below is the full content of your 'using-superpowers' skill - your introduction to using skills. For all other skills, use the 'Skill' tool:**

${content}
</EXTREMELY_IMPORTANT>"

printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}\n' "$(escape_for_json "$context")"
