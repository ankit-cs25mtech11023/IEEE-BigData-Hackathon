# Claude Context — FinReason Cup 2026 Task 1

## What This Project Is
Entry for FinReason Cup 2026 Task 1 (IEEE Big Data Cup): solve templated financial word problems and output an
exact final answer plus exact values for published intermediate-step slots. Scoring is exact match (no tolerance);
official test score = mean of seen-template and hidden-template strata. System = router: verified per-template
Python solvers for seen templates, LLM program-of-thought + self-consistency for hidden templates, all arithmetic in
`Fraction`. LLM is a college-hosted OpenAI-compatible endpoint (config in `.env`). Full details in `plan.md`.

**Deadlines:** Test ZIP 15 Oct 2026 23:59 AoE (aim 14 Oct). Paper 23 Oct 2026 23:59 AoE.

## Current Phase
Phases 0–1 done. Phase 2–4 code written and running live against `qwen-122b` (endpoint works off-campus; provider
said not to use the college network). Seen solvers: 4/290 verified so far. Next: thinking on/off shoot-out result →
full solver generation → hidden-path eval → submissions. See HANDOFF.md for session state.

## Recent Decisions
- Hidden-template half is 50% of final score and dev leaderboard is seen-only → leave-template-out proxy eval is essential.
- Never let the LLM do arithmetic or rounding; it writes code, we execute with `Fraction` and format ourselves.
- Use official toolkit (`toolkit/`, pinned) for validate / package / score-dev; never modify it.
- qwen-122b thinks by default; `LLM_THINKING` (default 0) toggles it, solver generation always off. Only one model hosted,
  so the model shoot-out became a thinking on/off shoot-out on the hidden-path proxy.

## Key Commands
- Venv: `.venv/bin/python`; tests: `.venv/bin/python -m pytest -q tests`
- LLM check: `.venv/bin/python scripts/llm_check.py` (needs `.env`, see `.env.example`)
- Seen solvers: `.venv/bin/python scripts/gen_solvers.py [--limit N] [--include-dev]`
- Hidden proxy eval: `.venv/bin/python scripts/eval_hidden.py --n 60 --name run1` → `outputs/hidden_eval/<name>/`
  (prefix `LLM_THINKING=1` to enable thinking for one run; the shell env overrides `.env`)
- Predict: `.venv/bin/python scripts/predict.py {dev,leaderboard,test} [--hidden] --name NAME` → `outputs/<split>/<name>/`
- Package: `.venv/bin/python scripts/package.py {leaderboard,test} outputs/<split>/<name>/predictions.jsonl`
- Official dev scoring: `python3 toolkit/scripts/task1_cli.py score-dev --questions data/task1/development/dev_questions.jsonl --gold data/task1/development/dev_gold.jsonl --manifest data/task1/development/dev_manifest.jsonl --predictions <preds.jsonl>`
- Validate / package: see `toolkit/scripts/task1_cli.py {validate,package,validate-zip}`.

## Protocols (always follow these)

1. **Plan-first rule**: If a new decision contradicts or changes anything in plan.md, update plan.md FIRST, then update checkbox.md to reflect any new or removed tasks, THEN implement.

2. **Checkbox discipline**: Mark items in checkbox.md as done only after they are fully implemented and working.

3. **Git commits**: Before committing, verify git is configured under the user's name (see Git Protocol below). Commit after:
   - A major feature or step is completed
   - plan.md or checkbox.md are updated
   - The user explicitly asks for a commit

4. **No silent changes**: Never change the direction of the project without updating plan.md first. If something mid-implementation reveals a flaw in the plan, pause, update the plan, then continue.

5. **claude.md updates**: Only update this file when the plan changes significantly or the user asks for it. Do not regenerate it every session.

6. **No AI attribution**: Never add Co-Authored-By Claude or "Generated with Claude Code" to commits or PRs.

## Git Protocol
Before every commit run `git config user.name` and `git config user.email`. If either is empty, stop and ask the user to set them:
`git config --global user.name "Your Name"` / `git config --global user.email "your@email.com"`.
Commit with `git add . && git commit -m "<specific message>"`. Never use `--author` or override identity.
Push only when the user asks (remote `origin` = GitHub, see plan.md).
