---
name: AI Educator Local TODO
---

# AI Educator TODO

This TODO is scoped to the `ai-educator` sub-agent workspace only.

## Routing

- [x] Add direct UI routing to `ai-educator`
- [x] Add Chief routing hints for curriculum and teaching requests
- [ ] Verify transcript-side routing chooses `ai-educator` when meeting persona is `chief`
- [ ] Add tests for curriculum prompt -> `ai-educator` route
- [ ] Add tests for misspellings like `curriculam` -> `curriculum-architect`

## Output Templates

- [x] Create `templates/course-outline.md`
- [x] Create `templates/module-plan.md`
- [x] Create `templates/project-brief.md`
- [x] Create `templates/resume-artifact.md`
- [ ] Create `templates/assessment-rubric.md`
- [ ] Create `templates/agent-readiness-roadmap.md`

## Knowledge Base

- [x] Define target vault structure in `KNOWLEDGE-BASE.md`
- [ ] Add conventions for naming curriculum files
- [ ] Add conventions for versioning program outlines
- [ ] Define link strategy between `programs/`, `modules/`, and `projects/`
- [ ] Add example notes for one bootcamp and one workshop

## Agent Behavior

- [ ] Update `AGENT.md` to explicitly reference local templates
- [ ] Add output mode for "draft now, refine later"
- [ ] Add output mode for "save-ready vault asset"
- [ ] Add rubric-oriented response pattern
- [ ] Add stronger guidance for college-student vs adult-professional tradeoffs

## Productization

- [ ] Add save-to-vault flow for `ai-educator` replies
- [ ] Add UI button to convert a chat answer into a curriculum note
- [ ] Add UI button to convert a chat answer into a project brief
- [ ] Add educator digest view for recent curriculum assets

## Evaluation

- [ ] Define examples of good curriculum outputs
- [ ] Define examples of weak curriculum outputs
- [ ] Add regression prompts for:
  - bootcamp design
  - adult-learning adaptation
  - capstone scoping
  - resume/portfolio conversion
  - agent-readiness sequencing
