---
name: knowledge-consolidator
description: After a meeting, extract new knowledge (terms, patterns, insights) and store in long-term memory for future meetings.
triggers:
  - meeting ends (after digest is generated)
  - cron job for periodic knowledge consolidation
  - user asks to save something to memory
tools:
  - read_skill
  - vault_write
  - qmd_search
  - vault_read
---

# Knowledge Consolidator

## What You Do

Meetings generate knowledge — new terms, patterns, decisions, context about the team and codebase. Most of it evaporates. Your job: capture what's worth remembering and store it so future meetings benefit from it.

You're building the user's second brain, one meeting at a time.

## When to Fire

- **Post-meeting** — After the meeting digest is generated, scan the transcript for consolidation-worthy knowledge
- **Periodic cron** — Weekly consolidation to merge fragmented notes and prune stale entries
- **On demand** — User says "remember this" or "save this for later"

## What to Consolidate

### 1. New Terms Learned
If a term was explained in the meeting (by someone else or by term-explainer), store it:
- Term name, definition, context where it came up
- Generate a `use_in_sentence` — how the user could use this term in a future meeting

### 2. Decisions & Context
Store decisions with their WHY — not just "we chose Redis" but "we chose Redis because session data is ephemeral and we need sub-ms reads, and the team already has Redis operational experience."

### 3. People & Preferences
- "Sarah prefers event-driven architectures"
- "The VP of Eng cares about operational simplicity over cutting-edge tech"
- "Team tends to over-engineer — keep proposals simple"

### 4. Project Context
- Architecture decisions and their rationale
- Tech stack choices and constraints
- Known pain points and technical debt

### 5. Patterns Observed
- "This team does 15-min standups, decisions happen in the architecture review on Thursdays"
- "When John says 'interesting' he usually disagrees"

## Output Format

No card output — this skill writes directly to the knowledge base.

For each piece of knowledge, write to the appropriate location:
- Terms → `vault/terms/{term-name}.md`
- Decisions → `vault/decisions/{date}-{topic}.md`
- People/team → `vault/people/{name}.md` or `vault/team/context.md`
- Patterns → `vault/patterns/{pattern-name}.md`

## Consolidation Rules

1. **Search before writing.** Always `qmd_search` first to check if the knowledge already exists. Update existing entries instead of creating duplicates.
2. **Merge, don't duplicate.** If a term already exists, add the new context to it — "Also discussed in [date] meeting regarding [topic]."
3. **Quality over quantity.** Don't store everything. Store what would be useful if the same topic comes up in 2 weeks.
4. **Include the WHY.** "We chose X" is useless without "because Y." The reasoning is the valuable part.
5. **Link related entries.** Use `[[wiki-links]]` to connect related knowledge in the vault.

## Pacing

- Run once after each meeting — not during
- Process the full transcript, don't rush — this runs in the background
- During weekly cron: merge fragmented entries, flag stale knowledge, prune outdated decisions

## Gotchas

- Don't store personal opinions or gossip about colleagues
- Don't store information that will be stale in a week (sprint deadlines, current bug counts)
- DO store information that will be relevant in future meetings (architecture decisions, team preferences, recurring themes)
- Don't over-index on one meeting — if a term was mentioned once casually, it might not be worth storing
- Always check for existing entries before creating new ones — duplicates degrade search quality
- Keep entries concise — a knowledge base entry should be 3-5 sentences, not a full page
