# Weak Signal Fusion

A local **public-source intelligence desk**. When several weak public indicators become unusual together, it cues collection, assembles cited evidence, helps you write a working assessment, and produces a separate finished brief.

It is a proof of concept, not an operational watch and not an invasion detector.

## The question

> When several individually weak public indicators become unusual together, do they provide useful incremental information for strategic-intent triage?

The phenomenon under test is **strategic coupling**: during costly state preparation, systems that are usually only weakly related — physical activity, bureaucratic tempo, public attention, markets, digital infrastructure — can become more statistically dependent. The interesting coincidence is not three sensors of the same physical activity. It is unusual movement across *different mechanisms*.

Strategic intent is not directly observable. Measurement therefore scores unusual mobilisation or costly activation. Meaning, alternatives, and what to tell a decision-maker stay in the analyst products.

## What you get

```text
watch → notice → investigate → working assessment → intelligence brief
```

| Product | Audience | What it is |
|---|---|---|
| **Notice** | You | A cue to look: what moved, what was quiet, what was missing. |
| **Working assessment** | Intelligence colleagues | Key judgements, alternatives, confidence, and the evidence annex. |
| **Intelligence brief** | Up the chain | A short, versioned, signed-off editorial product. Export is not distribution. |

The model never creates an observation, changes a score, or opens a notice. Collection uses lawfully obtainable public sources only.

The v1 coincidence detector is a **closed experiment**: public series did move together before 24 February 2022, and hard negatives stayed quiet, but that is not a tripwire and not a proof of intent. Details: [FINDINGS.md](FINDINGS.md).

The desk path (notice through brief) is implemented for retrospective cases. A continuous live watch is later work. Plan: [ROADMAP.md](ROADMAP.md).

## Quick start

Requires Docker, and [Ollama](https://ollama.com) on the host if you will draft or prepare a brief.

```bash
cp .env.example .env    # fill only the sources you will use
docker compose up --build
```

Then open [http://127.0.0.1:5173](http://127.0.0.1:5173) (desk) and [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) (API).

| Service | Port | Role |
|---|---|---|
| `web` | 5173 | Vite UI; proxies `/api` |
| `api` | 8000 | FastAPI |
| `db` | 5432 | Postgres (`wsd` / `wsd` / `wsd`) |
| `agent` | — | Heartbeats and CLI jobs (`docker compose exec agent …`) |

`.env.example` is the credential catalogue. `wsd doctor` reports whether keys are present; it never prints values. Default tests never call live sources or the model.

Git tracks **code and `scenario.json` contracts**. Notices, packets, briefs, harvests and indexes stay on the local `scenarios/` and `data/` mounts.

After Python changes: `docker compose restart api`. The UI bind-mount reloads on its own.

Without Docker: `uv sync --extra dev`, then `uv run python dashboard/server.py --api-only` and `cd dashboard/web && npm install && npm run dev`. Operator detail, harvests and CLI: [HOWTO.md](HOWTO.md).

## Using the desk

Day-to-day work is the UI (Desk, Scenarios, Operations).

1. Open a notice.
2. **Secondary collection** — run selected source jobs and read what came back.
3. **Research and draft assessment** — bounded document retrieval and a model proposal. Review, add your judgement, **Save assessment**. Download the assessment for colleagues if you need it.
4. **Prepare new brief version** — editorial synthesis from the saved assessment, no new searches. Edit if needed, **Sign off**, download. Preparing always creates a new unsigned draft; it does not overwrite a signed version.

Replay a recorded harvest (validate → collect → review → measure → emit) with `wsd run workflow --scenario ukraine2022`. That is a backtest of a closed window, not the live desk.

## Tests

```bash
python3 run_unit_tests.py
```

Offline by default. `--live` may call source APIs; `--with-model` may call local Ollama. Neither is implied by the other.

## Constraints

- Retrospective qualification now; a bounded live pilot only after the [roadmap readiness gate](ROADMAP.md). Targeting is out of scope.
- Replay evidence must have been knowable at the cutoff. A search hit today is a lead, not proof it was available then.
- Missing is unknown, not silence. A cloudy VIIRS night is not a reason to stop watching other sources.
- No post-hoc threshold tuning, extra votes from split AOIs, or synthetic fixtures reported as results.
- Do not retune frozen `coincidence_v1` on Ukraine.

## Development

- Small, reviewable changes; record them in [CHANGELOG.md](CHANGELOG.md).
- Keep default tests offline and cheap. Give experiments an immutable run ID. Keep duds.
- After a scientific freeze, do not edit the frozen inputs; version a new protocol instead.

## Docs

| Doc | What it is |
|---|---|
| [HOWTO.md](HOWTO.md) | Operator path: setup, harvest, review, packet, assessment, brief, tests |
| [ROADMAP.md](ROADMAP.md) | Product sequence, backlog, live-pilot gate |
| [FINDINGS.md](FINDINGS.md) | Closed detector experiment |
| [CHANGELOG.md](CHANGELOG.md) | What changed |
| [weak-signal-fusion-spec.md](weak-signal-fusion-spec.md) | Original measurement/interpretation design record |
| [dashboard/web/README.md](dashboard/web/README.md) | UI workflow notes |
| `.env.example` | Credentials and source locators |
