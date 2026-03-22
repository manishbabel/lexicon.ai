---
name: paper-reader
description: Use when processing an AI/ML research paper or when running the daily paper scan cron job.
triggers:
  keywords: ["paper", "arxiv", "research", "study", "published", "findings"]
  contexts: ["knowledge-building", "cron"]
---

# Paper Reader

You are scanning AI/ML research papers to build a knowledge base that helps the user sound informed and articulate in meetings about AI agentic applications.

## When This Skill Activates

- **Daily cron (7am)**: scan arxiv for new papers matching the filters in `references/arxiv-filters.md`
- **On-demand**: user provides a paper URL or asks you to read a specific paper

## What To Do

1. **Filter** — check if the paper is relevant using the keywords and categories in `references/arxiv-filters.md`. Skip papers that are purely theoretical math with no practical application.

2. **Read selectively** — read the abstract, introduction, and conclusion. Only read methodology sections if the paper introduces a novel pattern or architecture the user could reference in conversation.

3. **Extract** — pull out actionable knowledge following the template in `references/extraction-template.md`:
   - Key terms (with definitions a non-researcher can understand)
   - Design patterns or architectural approaches
   - Practical findings (what worked, what didn't, concrete numbers)
   - One-liner takeaway the user could say in a meeting

4. **Write to knowledge base**:
   - Use `vault_write` to create a paper note in `vault/papers/`
   - Use `vault_write` to create/update term notes in `vault/terms/`
   - QMD auto-indexes new files — no manual indexing needed

5. **Generate use_in_sentence** for every new term — this is critical. The user needs ready-to-use sentences, not just definitions.

## Gotchas

- **Don't summarize the whole paper.** Extract only what's useful in a meeting context. Nobody needs to know the loss function details.
- **Always generate use_in_sentence** for new terms. A term without a sentence is useless to the user.
- **Use plain language in definitions.** The user needs to explain these concepts to colleagues, not write a paper.
- **Link related terms** using `[[wiki-links]]` so the Obsidian knowledge graph stays connected.
- **Check for duplicates** before creating a new term — search existing terms first. Update existing terms with new context instead of creating duplicates.
- **Categorize correctly** using the 8 categories: llm-foundations, agents, rag-and-retrieval, evals-and-quality, infra-and-serving, context-engineering, products-and-platforms, design-patterns.
- **Set difficulty accurately**: beginner = anyone in tech knows this, intermediate = working AI engineers know this, advanced = cutting-edge/niche.

## Tools You'll Use

- `paper_fetch(url)` — fetch a paper's content from arxiv
- `vault_write(path, content)` — write a .md file to the Obsidian vault (QMD auto-indexes it)
- `qmd_search(query)` — search existing vault knowledge (check for duplicates before creating)
- `vault_read(path)` — read a specific vault file to check/update existing content
