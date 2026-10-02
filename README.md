# yt-stream-vibes

Real-time live-stream vibe analyzer (“Signal Room”). Discover top YouTube/Twitch lives, connect to a stream, and watch chat classification update live — vibe radar, streamer↔chat alignment, word cloud, and an ingested chat feed — without reading every message.

**Audience:** stream operators, community managers, and analysts who need live chat signal at a glance.

**Core loop:** browse or paste a live URL → connect → watch vibe metrics and chat enrichments update over SSE.

---

## What it does

| Capability | Detail |
| ---------- | ------ |
| **Live discovery** | Top live streams (YouTube Americas / LatAm by concurrent viewers; Twitch via Helix) |
| **URL paste** | Resolve a YouTube or Twitch URL → stream metadata → connect |
| **Chat ingest** | Micro-batches (~3s or 15–20 messages) from the active stream |
| **JEV classification** | Per-message intent, hype score, and vibe axis via [TypeSafe](https://typesafe.ai) / JEV |
| **Vibe radar** | Six axes: Laughs, Hype, Troll, Support, Tension, Curiosity |
| **Streamer alignment** | YouTube-only: Faster-Whisper STT of stream audio vs recent chat topic sync |
| **Word cloud / theme** | Keyword extraction + optional one-liner theme (OpenAI) from speech + chat windows |
| **Session lifecycle** | In-memory analysis session; idle disconnect tears down the worker |

Spam is JEV `intent=spam` only — no separate heuristic detector.

---

## Stack

| Layer | Choice | Role |
| ----- | ------ | ---- |
| Discovery | YouTube Data API v3 · Twitch Helix | Top lives + stream metadata |
| YouTube chat | `pytchat` (InnerTube) | Live chat without official chat API quota |
| Twitch chat | TwitchIO + operator bot token | EventSub / chat ingest (no end-user OAuth) |
| Classification | TypeSafe SDK (JEV) | Structured labels on chat micro-batches |
| Streamer STT | `yt-dlp` + ffmpeg + Faster-Whisper | YouTube audio → transcript for alignment |
| Theme / keywords | OpenAI (optional) | Soft-fail one-liner + normalized word cloud |
| API | FastAPI + uvicorn via **uv** | REST + SSE (internal; not browser-facing) |
| BFF | Next.js App Router `/api/*` | Proxies REST + SSE; hides backend URL |
| Frontend | Next.js 16 · React 19 · Tailwind 4 · **pnpm** | Signal Room dashboard |
| Charts | Apache ECharts (`echarts-for-react`) | Vibe radar and live gauges |
| Persistence | None (MVP) | Metrics live in memory for the active session only |

API keys and secrets stay server-side only. The browser never sees `API_URL` or platform credentials.

---

## Architecture

```
Browser
  │  /api/* only (never FastAPI URL)
  ▼
Next.js BFF  (frontend/src/app/api)
  │  API_URL (server-only)
  ▼
FastAPI  (server/src)
  │
  ├─ /api/lives              → LiveSourceAdapter.list_top_lives
  ├─ /api/streams/resolve    → URL parse + adapter.resolve_stream
  ├─ /api/streams/{id}/connect → SessionRegistry.create
  └─ /api/sessions/{id}/…
         ├─ chat/events  (SSE)
         └─ stats/events (SSE)
              │
              ▼
         LiveSourceAdapter
              ├── YouTubeAdapter → youtube_service + chat_streamer (pytchat)
              │                   + audio_streamer (Whisper, optional)
              └── TwitchAdapter  → twitch_helix + twitch_chat
              │
              ▼
         jev_classifier (platform-agnostic batches)
              │
              ▼
         alignment_engine · theme_summarizer · llm_keywords
```

Routes and JEV never call YouTube/Twitch SDKs directly. Discovery and chat go through `LiveSourceAdapter` (`server/src/adapters/`) so platforms stay swappable behind one contract.

### Session model

Connecting a stream creates an **in-memory analysis session** (`session_registry`):

1. Background worker pulls chat micro-batches from the adapter.
2. Batches are classified with JEV (intent, hype, vibe).
3. Optional YouTube STT feeds recent streamer speech into classification context and topic sync.
4. Dual SSE fanout: **chat** (enriched messages) and **stats** (radar, alignment, spam rate, word cloud, theme).
5. `DELETE /api/sessions/{id}` (or idle disconnect) stops the worker and drops the session.

Nothing is persisted across restarts.

---

## Technical decisions

### Why a BFF (Next.js `/api/*` → FastAPI)?

The UI must never hold platform API keys or the FastAPI base URL. Next.js route handlers proxy REST and SSE with a server-only `API_URL`. Client code uses relative `/api/...` paths only — including `EventSource` for SSE.

### Why `LiveSourceAdapter`?

Product surfaces (YouTube and Twitch) share the same connect → classify → SSE loop. Adapters normalize metadata and chat batches; routes stay platform-agnostic. Adding a source means a new adapter, not new route logic.

### Why InnerTube chat (`pytchat`) instead of the official YouTube Live Chat API?

Official chat polling burns quota quickly at live volume. `pytchat` uses InnerTube endpoints for ingest. Discovery/metrics still use the Data API (`search.list` / `videos.list`) where official APIs are the right tool.

### Why SSE instead of WebSockets?

Live metrics are one-way server → client. SSE maps cleanly to Next.js proxying, reconnects, and dual channels (`chat` / `stats`) without a custom WS protocol. FastAPI `StreamingResponse` + BFF pipe is enough for MVP.

### Why in-memory sessions (no DB)?

MVP needs a live window for the active connection, not history. A future vibe aggregator can sit behind a thin store interface without changing classifiers or SSE contracts. Avoiding a DB keeps the loop simple and deployable as a single worker process.

### Why JEV / TypeSafe for classification?

Sub-second structured inference on small batches (intent, hype score, vibe axes, topic sync) with a thin Python wrapper. Spam and Q&A filtering are label-driven (`intent=spam` / `intent=question`), not hand-tuned heuristics.

### Why streamer STT only on YouTube?

Alignment (“is chat on the same topic as the streamer?”) needs recent speech. YouTube live audio is reachable via `yt-dlp` + ffmpeg → Faster-Whisper. Twitch audio ingest is out of scope for now; Twitch sessions still get chat vibes and radar without speech context.

**Ops note:** YouTube CDN often returns HTTP 403 on googlevideo segments from datacenter IPs. Local runs usually work; cloud STT typically needs residential egress / proxy and logged-in cookies (see `server/.env.example`).

### Why an operator Twitch bot (no end-user login)?

Twitch chat requires an authorized bot account (`user:read:chat`). Credentials are operator-configured env vars — the product does not implement viewer OAuth.

### Design: “Signal Room”

Dark-first live-ops UI: high information density, hairline borders, one electric mint accent, kinetic metrics (radar / gauges) while connected. Charts use Apache ECharts; display + mono typefaces, not generic SaaS defaults. See `AGENTS.md` for the full design direction.

---

## JEV classification contract

| Field | Values |
| ----- | ------ |
| `intent` | `question` \| `hype/reaction` \| `technical_issue` \| `spam` |
| `vibe` | `laughter_humor` \| `hype_pog` \| `troll_sarcasm` \| `support_wholesome` \| `tension_drama` \| `curiosity_context` |
| `hype_score` | 0–100 |
| topic sync | Used for streamer↔chat alignment labels (`In Perfect Sync` / `Partial Engagement` / `Off Topic / Disconnected`) |

Classification can use `stream_topic`, `streamer_speech`, and `recent_chat` as context when present.

---

## Repo layout

```
yt-stream-vibes/
├── AGENTS.md                 # Agent/contributor guidance + design tokens
├── README.md
├── bruno/                    # API collection (health, lives, streams, sessions)
├── frontend/                 # Next.js — pnpm
│   ├── .env.example          # API_URL (server-only)
│   └── src/
│       ├── app/
│       │   ├── api/          # BFF → FastAPI
│       │   ├── page.tsx      # Home: URL paste + live strip
│       │   └── streaming/[platform]/[streamId]/
│       ├── components/       # Signal Room UI (radar, chat feed, …)
│       └── lib/backend.ts    # server-only FastAPI base URL helper
└── server/                   # FastAPI — uv
    ├── .env.example
    ├── pyproject.toml
    └── src/
        ├── main.py
        ├── api/routes/       # health, lives, streams, sessions
        ├── adapters/         # LiveSourceAdapter + YouTube + Twitch
        └── services/         # chat, JEV, sessions, STT, alignment, …
```

---

## Getting started

### Prerequisites

- Python ≥ 3.12
- Node ≥ 20 (Next.js 16)
- [uv](https://docs.astral.sh/uv/) and [pnpm](https://pnpm.io/) installed globally
- Optional for YouTube STT: system `ffmpeg` and `yt-dlp` on `PATH`

### 1. Configure env

```bash
# Server
cp server/.env.example server/.env
# Required for YouTube discovery + JEV:
#   YOUTUBE_API_KEY, TYPESAFE_API_KEY
# Twitch (optional):
#   TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET, TWITCH_BOT_USER_ID, TWITCH_BOT_TOKEN
# Theme one-liner (optional):
#   OPENAI_API_KEY

# Frontend
cp frontend/.env.example frontend/.env.local
# API_URL=http://127.0.0.1:8000
```

### 2. Install dependencies

```bash
cd server && uv sync
cd ../frontend && pnpm install
```

### 3. Run

```bash
# Terminal 1 — FastAPI (port 8000)
cd server
uv run uvicorn src.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2 — Next.js (port 3000)
cd frontend
pnpm dev
```

- UI + public API: [http://localhost:3000](http://localhost:3000)
- FastAPI (internal): [http://127.0.0.1:8000](http://127.0.0.1:8000) (`/health`, `/docs`)
- Bruno collection: `bruno/` against the FastAPI origin

---

## Key invariants

- Discovery + chat ingest only via `LiveSourceAdapter` — never from `api/routes`
- Browser → Next.js `/api/*` → FastAPI; never call FastAPI from client code
- `API_URL` is server-only (no `NEXT_PUBLIC_` backend URL)
- Live metrics via SSE only (no WebSockets)
- No database in MVP — sessions are in-memory
- Q&A / spam filtering is JEV label-driven

---

## Out of scope (for now)

- Durable persistence / vibe aggregator (message → vibe history)
- Multi-user auth
- Auto-reply or moderation actions on YouTube/Twitch
- Twitch streamer audio STT
- Separate spam heuristics beyond JEV `intent=spam`

---

## License / attribution

YouTube content and branding remain subject to [YouTube Terms of Service](https://www.youtube.com/t/terms). The UI includes YouTube attribution where embeds are shown.
