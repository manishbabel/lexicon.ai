---
name: meeting-prep
description: Before a meeting starts, load relevant context from memory — terms, past decisions, people notes — so the agent is primed.
triggers:
  - user clicks "Prepare" with meeting agenda/topics
  - meeting.prepare message received from frontend
tools:
  - read_skill
  - qmd_search
  - vault_read
---

# Meeting Prep

## What You Do

The user is about to go into a meeting. They've given you context — agenda, topics, attendees. Your job: search everything you know and load up the relevant terms, past decisions, people notes, and patterns so you're ready to assist in real time.

Think of it as a briefing before a mission. When the meeting starts, you should already know the terrain.

## When to Fire

- User fills out the prep form (agenda, topics, attendees, notes) and clicks "Prepare"
- The frontend sends `meeting.prepare` with the context

## What to Do

### 1. Parse the Input
Extract key signals from the prep data:
- **Topics** → search terms for the knowledge base
- **Attendees** → look up people notes (preferences, past interactions)
- **Agenda** → identify which skills will likely be needed
- **Notes** → additional context the user wants you to know

### 2. Search Knowledge Base
For each topic:
- `qmd_search` for relevant terms → pre-load into active context
- `qmd_search` for past decisions on this topic → know what was already decided
- `vault_read` for people notes on attendees → know who you're dealing with

### 3. Pre-activate Skills
Based on the agenda, predict which skills will fire:
- Architecture review → prime design-pattern-suggest
- Sprint planning → prime pro-con-analyzer, smart-question
- Knowledge sharing → prime term-suggest, term-explainer
- Retrospective → prime meeting-digest focus on action items

### 4. Build the Brief
Compile a prep summary for the user:

```json
{
  "terms_loaded": 12,
  "memories_loaded": 5,
  "summary": "Loaded 12 terms related to event sourcing and distributed systems. Found 3 past decisions about the payment architecture. Note: Sarah (attendee) prefers simple solutions — keep suggestions pragmatic."
}
```

## Output Format

This skill produces a `meeting.prepared` response (not a suggestion card):
- **terms_loaded** — count of relevant terms now in active context
- **memories_loaded** — count of relevant memories/decisions loaded
- **summary** — 1-2 sentence human-readable brief

## Prep Quality

**Good prep:**
- "Loaded terms: saga pattern, event sourcing, CQRS, compensating transaction. Past decision: team chose PostgreSQL over DynamoDB in Jan for the orders service. Sarah tends to push back on complexity — frame suggestions simply."

**Bad prep:**
- "Loaded 50 terms." (quantity without relevance)
- "Ready for the meeting." (no useful detail)

## Rules

- Be selective — load the 10-15 most relevant terms, not everything in the vault
- Prioritize recency — a decision from last week matters more than one from 6 months ago
- If no relevant knowledge is found, say so honestly: "No prior context found for these topics — starting fresh"
- Keep the summary actionable — tell the user something useful they didn't already know
- This runs BEFORE the meeting starts — speed matters. Don't spend 30 seconds on exhaustive search.

## Gotchas

- Don't load terms the user already knows well (check usage history)
- If an attendee has no people notes, don't mention them — silence is fine
- The prep summary is shown to the user — keep it concise and useful, not verbose
- Topics might be vague ("backend discussion") — do your best with broad searches
- If the user provided no topics/agenda, search based on recent meeting history for likely topics
- This is a one-shot operation — run once, return results, done. Don't keep running.
