# Project Progress

## Phase 0: Setup
- [x] Download Task 1 data (13 dev + 3 test files) and verify against official toolkit copy
- [x] Clone official toolkit and pin commit; add `scripts/setup_toolkit.sh`
- [x] `git init`, `.gitignore` (venv, outputs, toolkit, .env), `.env.example`
- [x] Create `.venv`, `requirements.txt`, install deps
- [x] Confirm official `score-dev` reproduces 1.0 on `dev_targets.jsonl`

## Phase 1: Core infrastructure (no LLM)
- [x] `io.py`: load/join questions, gold, manifest, targets; write predictions
- [x] `numbers.py`: robust number extraction (ints, decimals, negatives, rationals, comma thousands)
- [x] `formatting.py`: final value rendering (half_up to N dp, enum), exact slot rendering as rational/decimal
- [x] `sandbox.py`: subprocess executor with timeout and restricted imports for generated code
- [x] `scoring.py`: wrap official scorer; per-template / per-difficulty breakdown report
- [x] `templates.py`: skeletons, signatures, template routing; measure routing accuracy on dev (target 100%)
- [x] Packaging script: predictions → validate → `submission.zip` → validate-zip via official CLI
- [x] Abstain baseline end-to-end: produce valid dev/leaderboard/test ZIPs
- [x] Unit tests for numbers, formatting, routing, sandbox

## Phase 2: LLM client
- [x] OpenAI-compatible client reading `.env`; disk cache keyed by (model, messages, params)
- [x] Concurrency + retries + rate limiting
- [x] Connectivity check script; list hosted models (`scripts/llm_check.py`)
- [x] Run connectivity check against the college endpoint
- [x] Thinking toggle: `LLM_THINKING` env + per-request override, part of cache key
- [ ] Thinking on/off shoot-out on hidden-path proxy (~30 cases each); pick hidden-path default

## Phase 3: Seen path — verified template solvers
- [x] Solver contract + prompt (template examples + gold → `solve(text)` code)
- [x] Generation loop with verify-against-all-instances and error-feedback retries
- [ ] Registry of verified solvers; coverage report (templates solved / 290)
- [ ] Manual fixes for remaining failing templates
- [ ] Local dev seen score ≥ 0.99 FAC
- [ ] First leaderboard upload

## Phase 4: Hidden path — PoT + self-consistency
- [x] Leave-template-out evaluation harness (hidden-path proxy)
- [x] PoT prompt with answer_spec + slot descriptions + retrieved examples
- [x] Retrieval of similar train examples (topic/description/lexical similarity)
- [x] Sampling N programs + majority vote on final, slot vote among agreeing programs
- [ ] Error analysis loop; prompt iteration on proxy set
- [ ] Optional: verifier/critic pass for low-agreement cases

## Phase 5: Submissions
- [ ] First valid Test upload (by 9 Oct)
- [ ] Full pipeline run on leaderboard 580 + test 928; record scores and receipts
- [ ] Final Test upload (by 14 Oct); save receipt

## Phase 6: Working Notes paper
- [ ] Collect results tables (dev, leaderboard, leave-template-out proxy, ablations)
- [ ] Draft paper in IEEE 2-column template (≤10 pages), required citations
- [ ] Submit via CyberChair SC03 by 23 Oct
