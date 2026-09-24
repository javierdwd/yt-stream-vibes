# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:

- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:

- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:

- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

## Project Overview

**Name:** yt-stream-vibes  
**Product:** Real-Time YouTube Live Sentiment & Intent Analyzer (JEV Engine)

**One-liner:** Dashboard that lists top YouTube Live streams by country, streams live chat, and classifies messages in real time (sentiment, intent, hype) via JEV.

**Core loop:** Pick a country → see Top 5 lives → select a stream → watch live chat metrics (hype gauge, sentiment breakdown, Q&A feed) update in real time.

**Audience:** Stream operators, community managers, and analysts who need live chat signal without reading every message.

### MVP must-haves

- Country selector (`regionCode`) → Top 5 live streams by view count
- Stream cards: thumbnail, title, channel, concurrent viewers
- Live chat ingest for the active `video_id`
- JEV classification per micro-batch
- Analytics panel: hype/temperature gauge (0–100), sentiment breakdown, filtered Q&A feed (questions only, spam ignored)

### Out of scope (MVP)

- **No database** — metrics live in memory for the active session only; nothing persisted
- Multi-user auth
- Auto-reply / moderation actions on YouTube
- Classifying beyond the JEV labels below
- Non-YouTube sources

### Future: vibe aggregator (post-MVP)

A persistence/aggregation layer that keeps a durable listing of results as **message → vibe** (and related JEV fields). Intended role:

- Aggregate classifications over time (per stream / session)
- Store and query the message→vibe mapping for replay, history, or analytics
- Feed the dashboard with more than the live window

Do **not** add a DB or aggregator schema in MVP. When it lands, prefer a thin store behind a clear interface so `jev_classifier` / SSE stay unaware of storage details.

---

## Stack

| Layer | Choice | Role |
|-------|--------|------|
| YouTube discovery | YouTube Data API v3 | Top lives + stream metrics |
| Chat ingest | Python + `pytchat` | Live chat via InnerTube (avoids official chat quota) |
| Classification | JEV | Ultra-low-latency ML on message batches |
| API | FastAPI + uvicorn via **uv** (`server/src`) | REST + SSE (internal; not browser-facing) |
| BFF | Next.js App Router `/api/*` | Proxies REST + SSE to FastAPI; hides backend URL |
| Frontend | Next.js latest stable + Tailwind + **pnpm** (`frontend/src`) | Real-time dashboard: controls, stream cards, analytics panel |
| Persistence | None (MVP) | Future: aggregator for message→vibe listings |

API keys and secrets stay server-side only.

---

## Architecture

```
[YouTube Data API v3] ── search.list / videos.list ──► youtube_service
                                                              │
[User picks stream] ──────────────────────────────────────────┤
                                                              ▼
                                                    chat_streamer (pytchat)
                                                              │
                                                    micro-batches (~3s or 15–20 msgs)
                                                              ▼
                                                    jev_classifier (JEV)
                                                              │
                                                    structured metrics JSON
                                                              ▼
                                                    server (FastAPI + SSE)
                                                              ▼
                                                    Next.js /api/* (BFF proxy)
                                                              ▼
                                                    browser (EventSource / fetch)
```

### Target module layout

```
frontend/
  src/                 # Next.js app source (latest stable)
    app/api/           # BFF route handlers → FastAPI (`API_URL` server-only)
    lib/backend.ts     # server-only FastAPI base URL helper
server/
  src/
    main.py              # FastAPI app: CORS + include_router
    api/routes/          # health, lives, streams (APIRouter per resource)
    services/            # youtube_service, chat_streamer, jev_classifier
```

### YouTube Data API v3

**Top lives by country** — `search.list`:

- `eventType=live`
- `type=video`
- `order=viewCount`
- `regionCode` = user-selected country
- Return top **5** results

**Stream metrics** — `videos.list` with `part=liveStreamingDetails,statistics` (e.g. `concurrentViewers`).

### Chat streaming (`pytchat`)

- Connect to the active `video_id` via InnerTube endpoints
- Yield micro-batches every ~3 seconds **or** chunks of 15–20 messages
- Runs as a background worker; does not block the API event loop

### JEV classifications (contract)

Each batch returns structured metrics. Expected labels:

| Field | Values |
|-------|--------|
| `intent` | `question` \| `hype/reaction` \| `technical_issue` \| `spam` |
| `sentiment` | `positive` \| `neutral` \| `negative` |
| `hype_score` | number 0–100 |

Sub-second inference is a hard expectation; keep batches small and the wrapper thin.

### Frontend / dashboard (Next.js)

- App under `frontend/src/`, created with the latest stable Next.js
- **Styling:** Tailwind CSS (utility-first); design tokens as CSS variables wired into Tailwind theme
- Browser calls Next.js `/api/*` only (never FastAPI URL); SSE via `EventSource` on `/api/streams/{id}/events`
- **Controls:** country dropdown (`regionCode`)
- **Live feed:** Top 5 stream cards (thumbnail, title, channel, live viewers)
- **Analytics (active stream):**
  - Chat hype/temperature gauge (0–100)
  - Sentiment breakdown (positive / neutral / negative)
  - Q&A feed: messages with `intent=question`, excluding spam

### Design direction — “Signal Room” (2026)

Trend anchor: **dark-first live ops / control-room dashboards** — high information density, minimal chrome, kinetic data, one electric accent. Feels like a live broadcast desk, not a marketing landing page or generic purple SaaS.

**Vibe:** eye-catching, modern, “on-air”. The UI should feel alive while the stream is connected (subtle pulse / temperature motion), calm when idle.

**Layout**

- One primary composition: country control + Top 5 stream strip + analytics for the active stream
- Minimal chrome: thin 1px borders, tight padding, no heavy card stacks or decorative boxes
- KPI / gauges first; Q&A feed as a dense scrolling column
- Prefer CSS Grid density over whitespace-heavy marketing layouts

**Color (CSS variables → Tailwind)**

| Token | Role | Direction |
|-------|------|-----------|
| `--bg` | Canvas | Near-black charcoal (`~#0c0f12`), not pure `#000` |
| `--surface` | Panels | Slightly lifted slate; depth via border, not thick shadows |
| `--fg` | Text | Warm off-white |
| `--muted` | Secondary | Soft gray-blue |
| `--accent` | Live / CTA | Electric mint / teal (one accent only — no purple/indigo) |
| `--live` | On-air marker | Hot coral / signal red |
| `--pos` / `--neu` / `--neg` | Sentiment | Green / amber / rose — semantic only, never decorative rainbow |

**Typography**

- Expressive display for brand / section titles (e.g. Syne, Outfit, or similar — **not** Inter / Roboto / system default)
- Tabular / monospace for live numbers and hype score (e.g. JetBrains Mono, IBM Plex Mono)
- Clear hierarchy: few sizes, tight tracking on display, readable body

**Motion & micro-interactions (when possible)**

Prefer intentional micro-transitions for presence and hierarchy — not noise. Use CSS / Tailwind transitions; short durations (~150–300ms). Respect `prefers-reduced-motion`. Add them where they fit without blocking MVP delivery.

**Prioritize when feasible:**

1. Soft live pulse on the active stream / “ON AIR” affordance
2. Hype gauge / temperature fills that ease as SSE updates arrive
3. Sentiment bars and Q&A rows that transition in on new data
4. Hover / focus on stream cards and controls (border/accent shift, not heavy scale)
5. Selection feedback and empty → loading → live fades

**Avoid:** bounce, long parallax, decorative particle loops, motion that delays reading data

**Do / Don't**

- Do: dark-first, data-dense, one accent, hairline borders, kinetic metrics when possible
- Don't: purple-on-white gradients, cream+serif+terracotta, broadsheet columns, neon glow stacks, pill-chip clutter, multi-layer shadows, emoji decoration
- Don't: treat stream thumbnails as inset “pretty cards” in a marketing hero — this is a tool UI

When implementing UI, define tokens in CSS first, then map them in Tailwind; keep the Signal Room look consistent across pages.

### Key invariants

- Official API only for discovery/metrics; chat goes through `pytchat` / InnerTube
- YouTube API key and FastAPI URL never exposed to the browser (`API_URL` is server-only; no `NEXT_PUBLIC_` backend URL)
- Browser → Next.js `/api/*` → FastAPI; never call FastAPI from client code
- Q&A feed shows only valid questions from JEV — never spam
- API is FastAPI under `server/src/`; live metrics via SSE only (no WebSockets)
- No DB in MVP — do not introduce persistence “for later” unless asked
- Keep server modules independent and swappable

---

## Commands

### Server (`server/`)

Requires [uv](https://docs.astral.sh/uv/).

```bash
cd server
uv sync
cp .env.example .env        # set YOUTUBE_API_KEY
uv run uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend (`frontend/`)

```bash
cd frontend
pnpm install
cp .env.example .env.local  # API_URL (server-only; FastAPI base)
pnpm dev
```

- FastAPI (internal): http://127.0.0.1:8000 (`/health`, `/docs`)
- UI + public API: http://localhost:3000 (`/api/health`, `/api/lives`, …)

## Docs

- [docs/](./docs/) — longer design notes and product description drafts
