# Handoff — FinReason Cup 2026 Task 1 (updated 2026-10-05, session 2)

Start a new session in `/home/ankit-kali/D/Projects/Capstone/Dev` and read, in order:
1. `claude.md` — context, protocols, key commands (follow its protocols: plan-first, checkbox discipline, git rules)
2. `plan.md` — full plan, data/scoring facts, Key Decisions (all measurements are logged there), open items
3. `checkbox.md` — what is done / pending
4. This file — session state and immediate next steps

## Goal
Compete in FinReason Cup 2026 Task 1 (Verifiable Financial Chain Reasoning), IEEE Big Data Cup.
Site: https://the-finai.github.io/IEEE-bigdata-cup/task1/
- **Test ZIP due 15 Oct 2026 23:59 AoE** (internal target: first upload 9 Oct, final 14 Oct).
- **Working Notes paper due 23 Oct 2026 23:59 AoE** (CyberChair SC03, ≤10 pages IEEE 2-col).

## State
- Git: `main`, remote `origin` = `git@github.com:ankit-cs25mtech11023/IEEE-hackathon-finreason.git`.
  Nothing pushed yet (push only when the user asks). Commit identity: `ankit-cs25mtech11023`. No AI attribution.
- `.env` exists (gitignored): `qwen-122b`, `LLM_CONCURRENCY=8`, `LLM_THINKING=0`. **Never print or echo the key.**
- **Endpoint works from the user's home network.** Provider said NOT to use the college network. Plain HTTP.
- Phases 0–1 done; Phase 2–4 code runs live. 9/9 tests pass (`.venv/bin/python -m pytest -q tests`).
- Seen solvers: **4 / 290 verified** (`solvers/generated/`, committed).
- Abstain baseline ZIPs still valid (`outputs/{leaderboard,test}/abstain/submission.zip`, gitignored).
- `toolkit/` = official repo pinned at `fa6d96db…` (gitignored; `scripts/setup_toolkit.sh`). Never modify it.

## This session (all recorded in plan.md Key Decisions)
1. Connectivity OK. Only hosted model: `qwen-122b`.
2. qwen-122b **thinks by default**: reasoning arrives inline in `content`, ending in `</think>`
   (no `reasoning_content`). Same trivial prompt: thinking on 32.5s / 307 tok vs off 1.4s / 27 tok.
3. Added thinking toggle to `src/finreason/llm/client.py`:
   - `.env` `LLM_THINKING=0|1` (client default) + `Request(thinking=True/False/None)` per request.
   - Sent as `extra_body={"chat_template_kwargs": {"enable_thinking": ...}}`.
   - When thinking is on, `max_tokens += LLM_THINK_BUDGET` (default 8192).
   - Part of the cache key. If reasoning is truncated (`finish_reason=length`, no `</think>`), the reply is "".
   - Seen-solver generation (`solvers/generate.py`) always uses `thinking=False`.
   - Per-run override: `LLM_THINKING=1 .venv/bin/python scripts/...` (shell env beats `.env`).
4. Throughput: 8 parallel requests with thinking off took 4.2s, ~170 tok/s total. The server is shared, so
   one request occasionally stalls (~127s seen). The 300s timeout + 4 retries cover it.
5. Fixed the solver prompt: with thinking off, the model re-implemented `numbers()` itself and wrote its reasoning
   as code comments (0/10 on a trivial template). The prompt now forbids both, and the template verified in round 1 (136 tok).
6. Live smoke: `gen_solvers.py --limit 4 --parallel 4` gave 4/4 after the fix (2m40s for the first 4).
   `eval_hidden.py --n 4` (thinking off) gave 4/4 final, unanimous, ~775 completion tok per call.
7. Thinking on/off shoot-out on the hidden proxy: **started, then stopped by the user; no result yet.** The server was
   heavily loaded (~12 calls in 8 min). Partial replies are cached, so a rerun resumes for free.

## Next steps
1. Rerun the shoot-out in the background (same cases, same seed; cache resumes):
   `mkdir -p outputs/logs && LLM_THINKING=0 .venv/bin/python scripts/eval_hidden.py --n 30 --name shoot_nothink > outputs/logs/shoot_nothink.log 2>&1`
   then the same with `LLM_THINKING=1 … --name shoot_think`. Results go to `outputs/hidden_eval/<name>/`.
   Compare final/slot accuracy and tokens. Check server load first (`scripts/llm_check.py`). If it is slow,
   start the full seen-solver run (step 2) first: it is cheaper and needs no thinking.
   Then set the hidden-path default from the shoot-out. If thinking wins, either set `LLM_THINKING=1` in `.env`
   (solver generation stays off regardless) or pass `thinking=True` in `hidden/solver.py`.
   Record the decision in plan.md first, then tick the checkbox item.
2. Full seen-solver run: `.venv/bin/python scripts/gen_solvers.py --parallel 8` (~290 templates; estimate
   1.5–3 h depending on server load; resumable thanks to the cache and the registry skipping verified templates). Then:
   - `.venv/bin/python scripts/predict.py dev --name seen_v1` and the official `score-dev` (command in claude.md). Target ≥ 0.99 FAC.
   - Re-run failures with `--include-dev`, then fix stubborn ones by hand.
   - Leaderboard: `predict.py leaderboard --name seen_v1` → `package.py leaderboard …` → user uploads at
     https://zhuohan-finreason-task1-development.hf.space/
3. Hidden proxy, full: `scripts/eval_hidden.py --n 0 --name full_v1` (174 eligible dev cases). Use
   `by_agreement` in the report for error analysis and iterate on the prompts in `hidden/solver.py`.
4. **First Test upload by 9 Oct**: `predict.py test --hidden --name v1` → `package.py test …` → user uploads at
   https://zhuohan-finreason-task1-test-submission.hf.space/ (Team Name must stay the same across uploads).
5. Paper (Phase 6). Required citations: Cup overview, Task 1 overview, FinChain (ACL 2026); BibTeX on the site `#paper-references`.

## Still needed from the user
1. **Team Name** (permanent) for Test uploads. Contact email is already known (plan.md).
2. Affiliation for the paper.

## Risks to watch
- Shared server: latency varies a lot. Long runs should go in the background with logs in `outputs/logs/`.
- With thinking off, the model tends to write its reasoning into code comments. Watch completion tokens per call.
- Solvers that rely on number positions may break on rare phrasings; those cases fall through to the hidden path.
- `seed` rejection is handled automatically; `<think>` is stripped.

## User preferences
- Explain details before implementing and wait for an explicit go-ahead. Claude leads implementation.
- Commits under the user's identity with **no Claude/AI attribution** (global CLAUDE.md). Stage files explicitly
  (`HANDOFF.md` is deliberately untracked unless the user asks).
- Caveman (terse) response mode active.

## Suggested skills
- `project-blueprint`: keep plan.md / checkbox.md / claude.md in sync, and commit after steps.
- `code-review` or `simplify`: before the final submission run.
- `dataviz` / `artifact-design`: results figures for the paper.
