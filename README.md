# Prompt Iteration Workbench

A local, Python-first UI for adversarial prompt iteration: **expand** on purpose, then **edit** on purpose, repeating until you land on something clean, compliant, and high quality.

This tool is designed for the way you actually iterate when you care about the result: first you **add** coverage and capability, then you **reduce** to balance, clarity, and constraint compliance.

---

## What this is

Prompt Iteration Workbench is a local app that helps you iteratively produce better outputs from LLMs by alternating two phases:

- **Additive phase**: intentionally adds detail and capability  
  Examples: more ingredients, more steps, more coverage, more options, more structure.

- **Reductive phase**: intentionally edits toward simplicity and balance  
  Examples: remove or merge steps, reduce ingredients, tighten language, simplify workflow, improve compliance.

### Iteration semantics

**One iteration = one additive phase followed by one reductive phase.**

So if you select **Iterations = 3**, the engine runs:

1. Additive (iteration 1)
2. Reductive (iteration 1)
3. Additive (iteration 2)
4. Reductive (iteration 2)
5. Additive (iteration 3)
6. Reductive (iteration 3)

---

## Why this exists

Most prompt tools push you toward a single pass “best prompt.” That fails when the task is genuinely complex.

This workbench supports a more reliable approach:

1. **Force expansion** so the model explores enough of the solution space.
2. **Force reduction** so the output becomes usable, balanced, and efficient.
3. Repeat until convergence.

This is especially useful for:

- engineered recipes and food science workflows
- formulations (skin care, cosmetics, cleaning)
- procedures and SOPs
- structured data outputs (JSON schemas, checklists)
- code or code-adjacent specs
- any “creative + constraints” task where quality comes from iteration

---

## Core capabilities (current and planned)

### Current (early milestones)

- Local UI with fields for outcome, constraints, resources, prompts, and output
- Project save/load for reproducible iteration sessions

### Planned

- **Prompt Architect**: auto-generate additive and reductive prompt templates for the task
- Alternating **additive/reductive** iteration engine
- History timeline with per-step snapshots
- Optional diff and change summaries
- Soft format enforcement, plus structural validation when needed (example: JSON parse)

---

## UI overview

The UI is built around a single working state:

- **Outcome**: what you are trying to produce (example: `Skin Cream Formulation`)
- **Requirements and constraints**: must-haves and must-nots
- **Special equipment/ingredients/skills**: anything non-standard you have available
- **Iterations**: how many additive+reductive pairs to run
- **Additive phase allowed changes**: what the additive pass is permitted to change
- **Reductive phase allowed changes**: what the reductive pass is permitted to change
- **Format**: JSON, Markdown, Python, or Text
- **Additive prompt template**: supports substitution tokens
- **Reductive prompt template**: supports substitution tokens
- **Current output**: editable working draft
- **History**: every step captured with metadata (phase, model, timestamp)

Manual edits to **Current output** become the starting point for the next phase.

---

## Tech stack

- Python local app
- NiceGUI for the UI
- OpenAI API for generation
- `.env` configuration for keys and model selection

---

## Getting started

### Prerequisites

- Python 3.10+ recommended

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

### Configure environment

Copy `.env.example` to `.env` and fill values:

```bash
cp .env.example .env
```

`.env` contents:

```env
OPENAI_API_KEY=your_key_here
PREMIUM_LLM_MODEL=your_premium_model_name
BUDGET_LLM_MODEL=your_budget_model_name
```

### Run

```bash
python3 main.py
```

NiceGUI will print a local URL. Open it in your browser.

---

## Project files and persistence

Saved projects are stored as JSON (location defined in the roadmap; initially a local folder in the repo or user home directory). A saved project includes:

* all UI inputs
* prompt templates
* current output
* full iteration history

This makes sessions reproducible and shareable.

---

## Prompt templates and tokens

Additive and reductive prompts support substitution tokens such as:

* `{{OUTCOME}}`
* `{{REQUIREMENTS}}`
* `{{SPECIAL_RESOURCES}}`
* `{{FORMAT}}`
* `{{PHASE_RULES}}`
* `{{CURRENT_OUTPUT}}`
* `{{ITERATION_INDEX}}`
* `{{PHASE_NAME}}`

Planned UI will include a “preview rendered prompt” so you can see exactly what will be sent to the model.

---

## Model selection

Two model slots are used:

* `PREMIUM_LLM_MODEL`: used for high-leverage steps (Prompt Architect, optional final polish)
* `BUDGET_LLM_MODEL`: used for most iteration steps

The goal is to spend premium compute only where it changes outcomes.

---

## Roadmap

See `.vibe/PLAN.md` for staged milestones and checkpoint acceptance criteria.

---

## Contributing

This repo is designed for incremental implementation. Each checkpoint is intended to be completed in one focused pass with:

* a clear objective
* concrete deliverables
* verifiable acceptance criteria
* minimal demo commands
* evidence captured in `.vibe/STATE.md`

If you are contributing changes:

* keep edits scoped to the current checkpoint
* prefer small, testable increments
* avoid UI polish beyond what the checkpoint requires

---

## License

MIT
