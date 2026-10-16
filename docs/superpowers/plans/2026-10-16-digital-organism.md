# DigitalMonster Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver a running, observable, internet-connected digital organism with durable memory, bounded autonomous activity and measured policy learning.

**Architecture:** Python standard-library control service owns SQLite identity, events, goals, resource permissions and jobs. A deterministic environment and trainable policy run independently of language models; network reading and GPU training are explicit capabilities. Browser UI exposes evidence and user controls.

**Tech Stack:** Python 3.11+, SQLite, unittest, HTTP, vanilla browser UI, optional PyTorch on a dedicated GPU worker.

**Spec:** ../specs/2026-10-16-digital-organism-design.md

## Global Constraints

- User has authorized implementation and deployment, with local RTX 4090 D and remote dual RTX 5090; no other machines or paid services.
- Core activity must work without an LLM. Network input cannot grant permissions or execute code.
- Local service binds loopback; remote service runs without root and remains controllable.
- First jobs are finite, with resource limits, audit trails and independent evaluation.
- No claims of consciousness; learned parameters, rules and retrieved text are distinguished.

## Review Focus

- Crash between action and persistence: atomic state and event updates, recovered identity.
- Network redirects, private addresses and excessive bodies: reject or limit without changing goals.
- Pause while external operation runs: no follow-on autonomous action; stop remains responsive.
- Invalid or corrupt policy: keep prior valid policy and report error.
- HTTP mutation from another origin: reject, require a local bearer token and strict request sizes.

## Tasks

### Task 1: Persistent organism and deterministic environment
Files: `digitalmon/store.py`, `digitalmon/world.py`, `tests/test_core.py`.
Interfaces: Store(path).snapshot(), tick(), control(action), remember(text); World step(state, action).
- [ ] Write and run failing tests for restart identity, atomic event/tick persistence, pause and deterministic replay.
- [ ] Implement state, events, messages, world evolution and bounded storage.
- [ ] Run `python -m unittest discover -s tests -v` and commit.

### Task 2: Real learning and independent evaluation
Files: `digitalmon/learning.py`, `digitalmon/gpu_train.py`, `tests/test_learning.py`.
Interfaces: train(seed, episodes), evaluate(policy, seeds), compare(candidate, current); JSON policy artifacts.
- [ ] Write failing tests for parameter changes, held-out performance, promotion gate and corrupt artifacts.
- [ ] Implement finite Q-learning, paired evaluations, atomic versioned policy promotion and GPU distillation worker.
- [ ] Verify CPU tests and run a real finite GPU training job; retain metrics and checkpoint hashes.

### Task 3: Public internet and resource capability jobs
Files: `digitalmon/network.py`, `digitalmon/runtime.py`, `config/resources.json`, `tests/test_network.py`, `tests/test_runtime.py`.
Interfaces: fetch_public(url), Runtime.step(), structured research/train goals; resource budgets.
- [ ] Write failing tests for private address rejection, redirect validation, oversized content and paused runtime.
- [ ] Implement pinned-address HTTPS fetch, finite retry and byte limits, autonomous queued goals, training budgets and audit records.
- [ ] Verify real public-page retrieval with provenance, failed-job recovery and policy adoption.

### Task 4: User controls and observation UI
Files: `digitalmon/server.py`, `digitalmon/static/index.html`, `digitalmon/__main__.py`, `tests/test_http.py`.
Interfaces: GET /api/state, POST /api/control, /api/message, /api/research, /api/train; token-protected mutations.
- [ ] Write failing tests for unauthorized mutations, unknown controls, pause/resume and persistent messages.
- [ ] Implement loopback server, dashboard, memory search and source display; clearly identify unavailable language generation.
- [ ] Verify API end-to-end and inspect browser UI.

### Task 5: Deployment and operational evidence
Files: `scripts/`, `README.md`, `docs/verification.md`.
- [ ] Deploy to an independent non-root remote runtime, expose through local SSH tunnel and register both GPU hosts.
- [ ] Run 30-minute activity observation, real internet job and GPU experiment; record pause/restart/rollback checks.
- [ ] Fresh independent code review, address actionable issues, run full suite and commit deliverable.
- [ ] Document exact start/stop/recovery commands and remaining gaps; no silent claims of unimplemented features.

## Execution ledger

- 2026-10-16: User requested tasks set up and implementation started. Inline execution selected to avoid further approval loops.
- Ruling: Empty repository stays in the supplied workspace on `codex/digital-organism`; no separate checkout needed because there are no unrelated files or existing implementation.
- Ruling: Initial learning is finite Q-learning plus optional GPU distillation, with fixed terrain and held-out episode seeds; this tests policy learning without implying broad generalization.
- Ruling: Resource registration does not imply all GPUs are occupied; allocate one GPU per finite job and leave the rest available.
