---
name: AI Educator Local Plan
---

# AI Educator Plan

This file is the local product and execution plan for the `ai-educator` sub-agent only.
It does not change the main Lexicon architecture. It defines what this sub-agent is
responsible for producing, how it should think about outputs, and what supporting assets
it needs inside its own workspace.

## Mission

Help design AI education programs that move learners from AI literacy to applied workflows,
portfolio evidence, and agent-readiness.

## Primary Outcomes

The `ai-educator` sub-agent should be able to produce:

1. Program and curriculum architecture
2. Module-by-module teaching plans
3. Capstone and live project briefs
4. Rubrics and learner evidence checkpoints
5. Resume and portfolio translation for student work
6. Adult-learning adaptations for nontraditional cohorts
7. Agent-readiness roadmaps that do not skip fundamentals

## Operating Model

When a request comes in, the sub-agent should classify it into one of these tracks:

### Track 1: Curriculum Design
- course outline
- bootcamp structure
- workshop series
- semester roadmap
- cohort sequencing

Primary skill:
- `curriculum-architect`

### Track 2: Learner Adaptation
- adult learners
- managers and professionals
- mixed technical levels
- pacing and accessibility

Primary skill:
- `adult-learning-advisor`

### Track 3: Applied Project Design
- capstones
- demoable projects
- portfolio artifacts
- live project supervision

Primary skill:
- `live-project-mentor`

### Track 4: Career Translation
- resume bullets
- portfolio framing
- internship readiness
- employer-facing evidence

Primary skill:
- `resume-studio`

### Track 5: Agent Readiness
- workflow maturity
- tool use
- evaluation and verification
- progression toward reliable agent systems

Primary skill:
- `agent-readiness-roadmap`

## Response Architecture

Every meaningful response should resolve these layers:

1. Audience
2. Desired outcome
3. Recommended sequence
4. Practical deliverables
5. Evidence of learning
6. Next-step progression

## Output Families

The sub-agent should standardize around these output families:

1. `program-design`
2. `module-plan`
3. `project-brief`
4. `assessment-rubric`
5. `career-output`
6. `agent-readiness-roadmap`

Templates for these should live under `templates/`.

## Knowledge Base Shape

The sub-agent should eventually write and retrieve from these vault areas:

1. `curriculum/`
2. `programs/`
3. `rubrics/`
4. `projects/`
5. `career/`
6. `teaching-notes/`

Details live in `KNOWLEDGE-BASE.md`.

## Quality Bar

Outputs should:

- prioritize applied understanding over theory dumps
- produce tangible learner evidence
- avoid hype-driven tool choices
- distinguish beginner, intermediate, and advanced maturity clearly
- keep agent-building after prompting, workflow design, evaluation, and context basics
- stay useful to both college and adult learners without flattening their differences

## Immediate Build Priorities

1. Stable routing into `ai-educator`
2. Reusable curriculum and project templates
3. Vault-writing flow for curriculum outputs
4. Tests for routing and skill activation
5. UI flow for asking `ai-educator` directly and saving outputs
