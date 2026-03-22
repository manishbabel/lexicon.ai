---
name: meeting-digest
description: After a meeting ends, generate a concise digest with decisions, action items, and key takeaways.
triggers:
  - meeting ends (meeting.control action=stop)
  - user requests a meeting summary
tools:
  - read_skill
---

# Meeting Digest

## What You Do

The meeting just ended. You have the full transcript. Your job: distill it into a digest the user can skim in 30 seconds — what was decided, what they need to do, and what mattered.

This is NOT a transcript summary. It's an executive brief for someone who was IN the meeting and needs a quick reference.

## When to Fire

- Automatically when a meeting ends (triggered by `meeting.control` stop action)
- On demand if user asks "summarize this meeting" or "what did we decide?"

## Output Format

```json
{
  "category": "general",
  "title": "Meeting Digest",
  "body": "## Decisions\n- Use Redis for session storage with AOF persistence enabled\n- Target launch date: March 28\n\n## Action Items\n- [ ] @User: Set up Redis Sentinel for failover (by Friday)\n- [ ] @Sarah: Update the API docs with new session endpoints\n- [ ] @Team: Review the load test results before next standup\n\n## Key Discussion\n- Debated Redis vs Memcached for sessions — Redis won due to TTL support and persistence\n- Scaling concern raised: need to test beyond 10k concurrent sessions\n\n## Terms Used\n- **AOF persistence**, **Redis Sentinel**, **session affinity**"
}
```

### Sections:

1. **Decisions** — What was agreed on. Bullet points. Only include actual decisions, not discussions.
2. **Action Items** — Who does what by when. Use `- [ ]` checkbox format. Include names if speakers were identified.
3. **Key Discussion** — 2-3 most important discussion points. Not everything — just what mattered.
4. **Terms Used** — Technical terms from the meeting the user might want to reference later. Bold them.

## What Makes a Good Digest

**Good:**
- Short — fits on one screen
- Actionable — clear who does what
- Specific — "use Redis with AOF" not "discussed caching options"
- Skimmable — headers, bullets, no paragraphs

**Bad:**
- Restating the entire conversation chronologically
- Vague summaries: "The team discussed various options for the database"
- Missing action items — the most useful part
- Including every minor comment or tangent

## Rules

- Keep the whole digest under 200 words
- Decisions are ONLY things that were explicitly agreed — don't infer agreement from silence
- Action items need a person (or "Team") and ideally a deadline
- If no decisions were made, say "No explicit decisions" — don't fabricate them
- If no action items came up, say "No action items identified"
- Skip the "Terms Used" section if fewer than 2 terms were notable

## Gotchas

- Don't include off-topic chitchat or jokes in the digest
- If speaker diarization was poor, use "A participant" instead of wrong names
- Don't editorialize — "The team made a questionable choice" is not your call
- Action items should be phrased as tasks, not discussion: "Set up Redis" not "Talked about setting up Redis"
- This fires once at meeting end — don't generate partial digests mid-meeting
