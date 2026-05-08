# 42Tokyo Discord QA Bot

A staff-support Discord bot for 42Tokyo. Students ask questions in Discord
with `/ask`; the bot answers from a knowledge graph of intra rules and
procedures, with inline citations. Greetings get a friendly reply; queries
the bot can't answer can be escalated to a staff channel.

Built around **LightRAG** (graph + vector retrieval) over the 42Tokyo
intra knowledge base — 60+ pages, mostly Japanese with some English.

## Architecture

```
                 Discord
                    │ /ask <question>
                    ▼
        ┌───────────────────────────────────────────────┐
        │ bot/__main__.py                               │
        │   • greeting / intent gate (no RAG for "hi")  │
        │   • slash command, deferred reply             │
        │   • answer / sources / escalation embed       │
        └─────────────────────┬─────────────────────────┘
                              │
                              ▼
        ┌───────────────────────────────────────────────┐
        │ bot/rag.py — LightRAG (mode = mix)            │
        │   1. extract entities from question      ←LLM │
        │   2. cosine over chunks (multilingual)   ←emb │
        │   3. graph traversal entity / relation        │
        │   4. answer assembly with [N] citations  ←LLM │
        └──┬──────────────────────────┬─────────────────┘
           │                          │
           ▼                          ▼
    sentence-transformers         Groq qwen3-32b      (ingest, recommended)
    paraphrase-multilingual       Gemini 2.5-flash    (queries / fallback)
    -MiniLM-L12-v2  (384-d)       Ollama qwen2.5:7b   (local fallback)

        ┌───────────────────────────────────────────────┐
        │ rag_storage/   (regenerable, gitignored)      │
        │   ├─ KV stores              (JSON)            │
        │   ├─ vector DB              (NanoVectorDB)    │
        │   └─ knowledge graph        (NetworkX, *.graphml)
        └───────────────────────────────────────────────┘
```

The graph that ships in this repo (593 entities / 269 relations) was
built once via a one-off cached-response trick (see
[Ingest](#ingest)). For real production rebuilds, use **Groq Dev tier**.

## Project layout

```
discordBot/
├── bot/
│   ├── __init__.py
│   ├── __main__.py          # discord client + /ask + greeting gate
│   ├── ingest.py            # CLI: walk corpus/ and ainsert into LightRAG
│   ├── llm.py               # deprecated stub (LightRAG handles generation now)
│   └── rag.py               # build_rag, query, citation extraction
├── corpus/
│   ├── README.md
│   └── intra/               # 60 converted intra pages — the knowledge base
├── cache/
│   ├── claude_chunks.jsonl    # 100 chunks dumped via LightRAG's chunker
│   └── claude_responses.json  # cached entity-extraction responses (replay source)
├── scripts/
│   ├── convert_qa.py        # HTML/PDF → markdown (trafilatura + bs4 + pdftotext)
│   ├── dump_chunks.py       # walk corpus → cache/claude_chunks.jsonl
│   ├── claude_ingest.py     # ingest using cached responses (no API calls)
│   ├── ingest_status.py     # snapshot for `make ingest-status`
│   └── retry_failed.py      # cleanup + retry for stuck docs (Ollama path)
├── research/                # pre-build design notes (8 docs)
├── Q&A/                     # local-only raw HTML/PDF source (gitignored)
├── rag_storage/             # generated LightRAG state (gitignored)
├── .env.example
├── .gitignore
├── Makefile
├── README.md
└── requirements.txt
```

Local-only, not committed: `.env`, `Q&A/`, `rag_storage/`, `lightrag.log`,
`REVIEW.md`, `.venv/`.

## Quick start

### 1. Discord application

1. <https://discord.com/developers/applications> → **New Application**.
2. **Bot** tab → **Reset Token** → copy.
3. **OAuth2 → URL Generator**: scopes `bot` + `applications.commands`;
   permissions `View Channel`, `Send Messages`, `Embed Links`,
   `Read Message History`. Open the generated URL, invite the bot to a
   test server.

### 2. Configure

```sh
cp .env.example .env
```

Required: `DISCORD_TOKEN`. Strongly recommended: `DISCORD_GUILD_ID`
(your test server's id, with Developer Mode on; right-click the icon →
Copy Server ID) so slash commands sync instantly.

Optional:
- `GROQ_API_KEY` — fast ingest path (free tier limited; see below).
- `STAFF_CHANNEL_ID` — Discord channel that gets posted to on errors / escalations.

### 3. Install Ollama + pull a model (optional, for local fallback)

```sh
brew install ollama
ollama serve &              # keep running in background
ollama pull qwen2.5:7b      # ~4.7 GB, used as the local fallback LLM
```

### 4. Build + run

```sh
make install                # creates .venv, installs deps
make convert                # only if you have raw HTML/PDF in Q&A/
make ingest-replay          # replay the checked-in graph (~14s, no API)
                            # OR  make ingest   (rebuild via Groq, ~30 min)
make run                    # start the Discord bot
```

In Discord:

```
/ask How does the Black Hole work?
/ask ピアレビューはどうやるの？
/ask hi
```

Replies are an embed with the answer + cited filenames + the query mode used.

## Make targets

| Target | What it does |
|---|---|
| `make install` | Create `.venv`, install all requirements |
| `make convert` | `Q&A/` (raw HTML/PDF) → `corpus/intra/` (markdown) via trafilatura |
| `make ingest` | Build the LightRAG graph using whichever LLM is in `.env` (Gemini → Groq → Ollama auto-detect). Slow first time. |
| `make ingest-replay` | Replay the checked-in `cache/claude_responses.json` to rebuild the exact shipped graph in ~14s, no API tokens spent. |
| `make ingest-status` | Show progress, ETA, recent log lines |
| `make ingest-tail` | `tail -f` the live ingest log |
| `make run` | Start the Discord bot |
| `make webui` | Launch LightRAG visualization UI on `:9621` |
| `make clean` | Remove generated state and pycache |

## Ingest

LightRAG's ingest extracts entities and relations from each chunk via an
LLM call. For 60 docs / 100 chunks that's ~100-200 LLM round-trips with
prompts of ~5-7K tokens each — which is the bottleneck.

Three paths to populate `rag_storage/`:

### `make ingest-replay` (default, no API)

The graph that ships in this repo (`cache/claude_responses.json`,
~163KB) was generated once by reading every chunk by hand and writing
the entity/relation tuples in LightRAG's expected delimited format
(`entity<|#|>name<|#|>type<|#|>desc` etc.), keyed by content hash. The
ingest script (`scripts/claude_ingest.py`) injects a fake `llm_model_func`
that looks up cached responses instead of calling any external API.

For this build I produced those responses by hand-running Claude over
the corpus inside a Claude Code session — pure time/token efficiency,
since I was already in the loop. **For a production rebuild on fresh
data, do NOT do this — use Groq.**

```sh
make ingest-replay  # ~14 seconds, deterministic
```

Result: 593 entities / 269 relations / 100 chunk vectors / 60 docs.

### `make ingest` with Groq Dev tier (recommended for fresh corpora)

The free-tier 6K TPM cap is below LightRAG's prompt size, so the free
tier will fail. The Dev tier (~$3 one-time top-up) lifts it.

```sh
# in .env:
GROQ_API_KEY=gsk_...
GROQ_MODEL=qwen/qwen3-32b
LLM_PROVIDER=groq
```

Then `make ingest` — ~30 min for the full corpus.

### `make ingest` with Ollama (local, slow, free)

Set `LLM_PROVIDER=ollama` in `.env`. Runs locally on `qwen2.5:7b` (or
similar). Plan on 5-7 hours unattended on an M-series Mac. Larger docs
may hit timeouts; `scripts/retry_failed.py` retries those with smaller
chunks.

## Query-time LLM

Queries are always single small calls (~1-2K tokens with retrieved
context), so any of Gemini free / Groq free / Ollama work. Order of
preference: Gemini 2.5-flash-lite (fast, free 15 RPM / 1000 RPD) →
Groq → Ollama. Auto-detected from `.env`.

## Inspecting the knowledge graph

After ingest, launch the LightRAG webui:

```sh
make webui
```

Then open <http://localhost:9621>. Tabs: knowledge graph (entities +
relations, draggable), documents, query, server logs.

Note: webui queries use Ollama bindings; the bot uses sentence-
transformers for embeddings, so search results in the webui won't match
the bot. **Use the webui for graph + chunk inspection, the bot for
actual answers.**

## Adding more documents

Two paths.

**If you have HTML pages saved from intra** (login required, so save them
manually in your logged-in browser):

1. Drop the saved `.html` files into `Q&A/` (gitignored).
2. `make convert` — produces clean markdown in `corpus/intra/`.
3. `make ingest` — LightRAG hashes content; unchanged docs are skipped.
4. Restart the bot.

**If you already have markdown** — just drop `.md` or `.txt` files
anywhere under `corpus/` (subdirs are walked) and `make ingest`.

## Troubleshooting

### Webui knowledge graph is empty

The lightrag-server loads the graph file once at startup and doesn't
auto-reload. After running `make ingest-replay` or `make ingest`,
restart the webui (`kill <pid> && make webui`) so it picks up the
populated graph.

The webui uses Ollama `all-minilm` for embeddings (384-d, matches our
storage) — not the same model as the bot uses. So similarity scores in
the webui's "Query" tab will be off-axis. Use the webui for inspection
only; use the Discord bot for real querying.

### Ingest leaves some docs in `failed` status (Ollama path)

Big multi-page docs sometimes hit `httpx.ReadTimeout` or LightRAG's
internal worker timeout when local `qwen2.5:7b` takes too long. Re-running
`make ingest` doesn't retry them — LightRAG creates `dup-*` ghost entries.
Use the surgical retry helper:

```sh
.venv/bin/python scripts/retry_failed.py
```

It cleans `dup-*` entries, flips `failed` → `pending`, and re-runs the
proper LightRAG retry pipeline with smaller chunks (600 tokens) and
bumped timeouts (900s).

### Query latency is high (60–200s)

That's local Ollama doing real work for every `/ask`. Discord lets
you wait up to 15 min on a deferred reply, so it works — but it's not
snappy. Add a `GEMINI_API_KEY` or `GROQ_API_KEY` to `.env` and queries
drop to ~3-5 seconds.

### Slash commands don't show up

Set `DISCORD_GUILD_ID` in `.env` to your test server's id and restart.
Without it, sync is global and takes up to an hour to propagate.

## Roadmap

- 42 API integration: identity verification, `/me` dashboard, Black Hole alerts.
- Feedback loop: thumbs-up/down reactions feed a curated answer store.
- Eval set + retrieval metrics.
- Hyperlinked citations back to the source intra page.
