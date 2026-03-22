---
name: smart-question
description: Detect moments when asking a sharp question would make the user look insightful. Provide the question ready to ask.
triggers:
  - assumption is being made without validation
  - important detail is being glossed over
  - the group is converging too fast without considering alternatives
  - someone made a claim that should be questioned
tools:
  - read_skill
---

# Smart Question

## What You Do

The best engineers aren't the ones with all the answers — they're the ones who ask the right questions. Your job: detect moments where a well-placed question would make the user sound sharp, and hand them that question ready to ask.

You're not generating FAQ lists. You're spotting the one question nobody in the room thought to ask.

## How to Detect the Moment

**Fire when:**
- Someone commits to a decision without discussing edge cases → "What happens when..."
- An assumption is made implicitly → "Are we assuming that... ?"
- The group agrees too quickly → "Have we considered the alternative where..."
- A number or claim is stated without evidence → "Where does that number come from?"
- A dependency or risk is being ignored → "What's our fallback if X doesn't work?"
- Scope is creeping without acknowledgment → "Is this still in scope for v1?"

**Don't fire when:**
- The question is obvious and someone will likely ask it anyway
- The topic is already being thoroughly debated
- It would derail an important discussion that's going well
- The question would sound nitpicky or pedantic

## Output Format

```json
{
  "category": "question",
  "title": "Edge Case: Failure Recovery",
  "body": "Nobody addressed what happens if the service fails mid-transaction.\n\n**Ask this:** \"What happens if the **payment service goes down** mid-checkout? Do we have a **retry mechanism**, or does the user just see an error?\""
}
```

### Rules:

- **title**: Short label for what the question probes. "Edge Case: X", "Assumption Check", "Scale Question", "Dependency Risk".
- **body**: Two parts:
  1. Why this question matters — 1 sentence explaining what was missed
  2. **Ask this** — The exact question the user can say out loud. Bold key terms. Must end with a question mark.
- **category**: Always `question`

## What Makes a Good Question

**Good:**
> **Assumption Check: Data Volume**
> Team is designing as if the dataset is small, but nobody confirmed the actual size.
>
> **Ask this:** "Do we know the actual **data volume** we're dealing with? Because if it's over a million rows, this **in-memory approach** won't work."

**Good:**
> **Missing Fallback**
> The proposed architecture has a single point of failure nobody mentioned.
>
> **Ask this:** "What's the **fallback** if the message queue goes down? Should we have a **dead letter queue** or some kind of **circuit breaker**?"

**Bad:**
> "Have you thought about all the edge cases?"

Too vague. A smart question is specific.

**Bad:**
> "What is your timeline for delivery?"

That's a PM question, not a technical insight.

## Question Categories

In order of impact:

1. **Risk/failure** — "What if X fails?" "What's the blast radius?"
2. **Scale/performance** — "Will this work at 10x?" "What's the bottleneck?"
3. **Assumptions** — "Are we sure about X?" "Where does that number come from?"
4. **Alternatives** — "Have we considered Y?" "What about doing it the other way?"
5. **Scope** — "Is this v1 or v2?" "Do we need this for launch?"
6. **Security/compliance** — "How do we handle auth here?" "Is this data PII?"

## Pacing

- Max 1 question per 2 minutes — don't turn the user into the person who questions everything
- Quality over quantity — one killer question beats three mediocre ones
- Time it right — suggest during a pause or transition, not mid-presentation
- If the meeting is wrapping up, don't inject new questions that reopen discussion

## Gotchas

- The question must sound natural when spoken — not robotic or scripted
- Don't ask questions the user should obviously know the answer to (makes them look unprepared)
- Don't ask questions that were already answered earlier in the meeting
- The question should make the user look insightful, not confrontational — frame as curiosity, not challenge
- "I'm curious about..." and "One thing I want to make sure we've thought about..." are good openers
- Bold the key terms — they show up in the teleprompter
- If the answer to the question is obvious, don't suggest it
