---
name: AI Educator Knowledge Base Structure
---

# AI Educator Knowledge Base

This document defines the target knowledge-base layout for curriculum and learner-output
assets produced by the `ai-educator` sub-agent.

## Recommended Vault Areas

```text
curriculum/
programs/
rubrics/
projects/
career/
teaching-notes/
```

## Folder Purposes

### `curriculum/`
Module-level teaching material.

Examples:
- weekly plans
- lesson outlines
- reading sequences
- assignment briefs

### `programs/`
Top-level program designs.

Examples:
- 6-week AI bootcamp
- semester roadmap
- workshop series
- executive training track

### `rubrics/`
Evaluation artifacts.

Examples:
- capstone rubric
- presentation rubric
- prompt quality rubric
- project review checklist

### `projects/`
Applied learner builds.

Examples:
- capstone briefs
- client-style project scopes
- demo requirements
- milestone checklists

### `career/`
Career translation assets.

Examples:
- resume bullet libraries
- portfolio framing notes
- internship readiness checklists
- employer-facing project summaries

### `teaching-notes/`
Reusable instructor guidance.

Examples:
- adult-learning patterns
- pacing adjustments
- cohort retrospectives
- common learner failure modes

## File Naming Conventions

Prefer:

- `YYYY-MM-topic-slug.md` for evolving program notes
- `program-name-v1.md` for formal versions
- `project-name-brief.md` for project assets
- `topic-rubric.md` for evaluation assets

## Linking Strategy

Each major program note should link to:

1. its module plans
2. its projects
3. its rubrics
4. its learner outcomes

Each project brief should link back to:

1. the parent program
2. the module that introduced it
3. the rubric used to assess it
4. the career artifact it supports

## Retrieval Priorities

When searching for context, the `ai-educator` sub-agent should prefer:

1. matching program designs
2. matching audience notes
3. matching project briefs
4. matching rubrics
5. matching career-output notes

## Minimum Metadata To Preserve

Every saved curriculum asset should capture:

- audience
- duration
- maturity level
- target outcome
- deliverables
- assessment method
- related projects
