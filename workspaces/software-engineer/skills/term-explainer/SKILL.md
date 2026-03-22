---
name: term-explainer
description: When someone says a term in the meeting the user might not know, detect it and explain in real time.
triggers:
  - unfamiliar technical term spoken by another participant
  - acronym or jargon the user hasn't used before
  - domain-specific concept that needs context
tools:
  - read_skill
---

# Term Explainer

## How to Find the Right Term

1. Listen for technical terms, acronyms, and jargon spoken by OTHER participants (not the user).
2. Filter: has the user used this term themselves in this meeting or past meetings? If yes, skip — they know it.
3. Filter: is this common knowledge for the user's level? "API", "database", "frontend" → skip for a senior engineer.
4. Filter: have you already explained this term earlier in this meeting? Don't repeat.
5. What passes the filters is worth explaining.

**Detection signals (explain it):**
- Niche patterns: "saga pattern", "CQRS", "bloom filter", "Raft consensus"
- Domain crossover: a data scientist mentions "p-value" in a backend meeting
- Acronyms that aren't universal: "CRDT", "LSM tree", "WAL", "SLI vs SLO"
- Named laws/principles: "Hyrum's Law", "Conway's Law", "Goodhart's Law"

**Skip signals (don't explain):**
- User said the term themselves → they know it
- Common engineering vocabulary for their level
- Already explained in this meeting
- Generic business terms: "KPI", "OKR", "stakeholder"

## Output Format

Return a JSON suggestion with these fields:

```json
{
  "category": "term_explain",
  "title": "Saga Pattern",
  "body": "A design pattern for managing distributed transactions. Instead of one big atomic operation, it breaks work into a sequence of local transactions — each with a compensating action if a later step fails.\n\n*Context: Speaker mentioned this for the payment flow — sagas are the standard approach when multiple microservices need to coordinate without a central transaction manager.*"
}
```

### Rules for each field:

- **title**: The term exactly as spoken, capitalized properly. No extra words.
- **body**: 2-3 sentences max. Structure:
  1. First sentence: what it IS (plain definition)
  2. Second sentence: how it WORKS or an analogy
  3. Third sentence (italic): why it matters in THIS conversation — connect it to what was just discussed
- **category**: Always `term_explain`

## What Makes a Good Explanation

**Good:**
> **CRDTs**
> Conflict-free Replicated Data Types — data structures that multiple nodes can edit independently and always merge deterministically, without coordination.
>
> *Context: relevant to the offline-first sync problem discussed — CRDTs would let both clients edit without conflict resolution logic.*

**Bad:**
> **CRDTs**
> CRDTs stand for Conflict-free Replicated Data Types. They were introduced by Marc Shapiro et al. in 2011. There are two types: state-based (CvRDTs) and operation-based (CmRDTs). State-based CRDTs...

The bad example is a textbook dump. The user needs to understand the concept in 5 seconds while someone is still talking.

**Bad:**
> **API**
> An Application Programming Interface allows two systems to communicate.

Don't explain things the user obviously knows.

## Difficulty Calibration

Gauge the user's expertise from their persona and conversation history:

| User Level | Explain | Skip |
|---|---|---|
| Junior / student | Most technical terms, patterns, acronyms | Truly basic: "variable", "function", "loop" |
| Mid-level engineer | Niche patterns, cross-domain terms, named laws | Common patterns: "MVC", "REST", "pub/sub" |
| Senior engineer | Rare/specialized terms, cutting-edge concepts | Anything they'd encounter regularly |

**When in doubt, skip.** An unnecessary explanation is more annoying than a missed one. The user feels patronized if you explain things below their level.

## Pacing

- Max 2 explanations per minute — don't flood the screen
- If multiple unknown terms appear at once, pick the most relevant to the current discussion
- Wait for a natural pause (sentence boundary) before firing — don't explain mid-sentence
- Space explanations at least 15 seconds apart

## Gotchas

- Never explain a term the user said themselves — that's insulting
- Never explain the same term twice in one meeting
- Don't guess: if you're not confident what a term means in context, don't explain it wrong
- Keep it conversational, not academic — the user is in a live meeting, not reading a textbook
- The context line (italic) is critical — without it, the explanation feels generic and unhelpful
- If the term has multiple meanings, use the one that fits the conversation context
