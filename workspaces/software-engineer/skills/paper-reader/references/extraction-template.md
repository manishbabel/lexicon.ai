# Extraction Template

Follow this structure when extracting knowledge from a paper.

## Paper Note (→ vault/papers/YYYY-MM-DD-paper-title.md)

```markdown
---
title: Paper Title Here
authors: [Author One, Author Two]
date: 2026-03-18
url: https://arxiv.org/abs/XXXX.XXXXX
category: agents
tags: [multi-agent, orchestration, tool-use]
relevance: high
---

# Paper Title Here

## Summary
3-4 sentences max. What did they do? What did they find? Why does it matter?

## Key Findings
- Finding 1 (with concrete numbers if available)
- Finding 2
- Finding 3

## New Terms
- [[term-name]] — brief definition
- [[another-term]] — brief definition

## Practical Takeaway
One sentence the user could say in a meeting to reference this paper's insight.
Example: "There was a recent paper showing that multi-agent systems with role specialization outperform single-agent by 40% on complex tasks."

## Patterns & Approaches
- Pattern name: brief description of how it works and when to use it
```

## Term Note (→ vault/terms/term-name.md)

```markdown
---
term: the term
category: agents
difficulty: intermediate
related: [related-term-1, related-term-2]
context_tags: [meeting, architecture]
source: paper:arxiv/XXXX.XXXXX
created: 2026-03-18
---

# The Term

**Definition:** Plain-language explanation. Write it so someone in a meeting
can understand it without an ML background.

## Use in Sentence
"A natural sentence the user can say in a meeting that uses this term correctly
and makes them sound knowledgeable."

## Key Points
- Point 1
- Point 2

## Gotchas
- Common misconception or misuse of this term

## Related
- [[related-term-1]] — how it connects
- [[related-term-2]] — how it connects
```

## Quality Checklist

Before saving, verify:
- [ ] Definition is plain language (no jargon-explaining-jargon)
- [ ] use_in_sentence sounds natural, not textbook-like
- [ ] Category is one of the 8 categories
- [ ] Difficulty is set accurately (beginner/intermediate/advanced)
- [ ] Related terms use [[wiki-links]]
- [ ] No duplicate terms (searched existing terms first)
