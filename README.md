# 42Tokyo Discord QA Bot

A staff-support Discord bot for 42Tokyo. Students ask questions in Discord
with `/ask`; the bot answers from a curated knowledge graph of intra rules
and procedures, citing the source. Greetings get a friendly reply; off-
topic or low-confidence queries can be escalated to a staff channel.

Built around **LightRAG** (graph + vector retrieval) over the 42Tokyo
intra knowledge base (60+ pages, mostly Japanese, some English).

## Architecture

```
            ┌────────────────────────────────────────┐
            │ Discord                                │
            │     /ask <question>                    │
            └──────────────────┬─────────────────────┘
                               │
                               ▼
            ┌──────────────────────────────────────────┐
            │ bot/__main__.py                          │
            │   • greeting/intent gate                 │
            │   • slash command, deferred reply        │
            │   • answer / source / escalation embed   │
            └──────────────────┬───────────────────────┘
                               │
                               ▼
            ┌──────────────────────────────────────────┐
            │ bot/rag.py — LightRAG (mode = mix)       │
            │   1. extract entities from question      │  ← LLM
            │   2. cosine over chunks (multilingual)   │  ← embedder
            │   3. graph traversal entity / relation   │
            │   4. assemble + answer with citations    │  ← LLM
            └──┬─────────────────┬─────────────────────┘
               │                 │
               ▼                 ▼
       sentence-transformers   Ollama   ────►  qwen2.5:7b  (queries, free, local)
       paraphrase-multi-       (or)
       lingual-MiniLM-L12-v2   Groq     ────►  qwen/qwen3-32b  (ingest, free*, fast)

            ┌──────────────────────────────────────────┐
            │ rag_storage/  (regenerable, gitignored)  │
            │   ├─ KV (JSON)                           │
            │   ├─ vector DB (NanoVectorDB)            │
            │   └─ knowledge graph (NetworkX, .graphml)│
            └──────────────────────────────────────────┘
```

\* Groq free tier caps at 6K tokens-per-minute per request; for the full
ingest of this corpus, the local Ollama path is the practical default.
See [LLM choices](#llm-choices) below.

## What it answers

Drop `.md` or `.txt` files into `corpus/`. The bot will retrieve and
answer from them with inline citations. The default knowledge base
includes 60 pages of converted 42Tokyo intra rules, peer-review
guidelines, exam policies, campus rules, and FAQs.

## Quick start

### 1. Create a Discord bot

1. Go to <https://discord.com/developers/applications>, click **New Application**.
2. Open the **Bot** tab → click **Reset Token** → copy the token.
3. Open **OAuth2 → URL Generator**.
   - Scopes: `bot`, `applications.commands`
   - Permissions: `View Channel`, `Send Messages`, `Embed Links`, `Read Message History`
4. Open the generated URL in a browser, invite the bot to a test server.

### 2. Configure

```sh
cp .env.example .env
```

At minimum set `DISCORD_TOKEN`. Strongly recommended: `DISCORD_GUILD_ID`
(your test server's id, with Developer Mode on; right-click the server icon
→ Copy Server ID) so slash commands sync instantly instead of taking up
to an hour.

Optional:
- `GROQ_API_KEY` — fast ingest path. Free tier at <https://console.groq.com/keys>.
- `STAFF_CHANNEL_ID` — where errors and escalations get posted.

### 3. Install Ollama + pull a model

```sh
brew install ollama
ollama serve &              # keep running in the background
ollama pull qwen2.5:7b      # ~4.7 GB, used for query answer generation
```

### 4. Add corpus + ingest + run

```sh
make install      # creates .venv, installs Python deps
make convert      # only if you have raw HTML/PDF in Q&A/, see below
make ingest       # build the LightRAG knowledge graph (slow first time)
make run          # start the Discord bot
```

In Discord:

```
/ask How does the Black Hole work?
/ask ピアレビューはどうやるの？
/ask hi
```

The bot replies with an answer + the source filenames.

## Inspecting the knowledge graph

After ingest, launch the LightRAG webui:

```sh
make webui
```

Then open <http://localhost:9621> for a visual map of entities,
relations, and source chunks.

## Adding more documents

The simple path:

1. Drop `.md` or `.txt` files anywhere under `corpus/` (subdirs are walked).
2. `make ingest` — LightRAG hashes content; unchanged docs are skipped.
3. Restart the bot.

If you have raw HTML pages saved from intra (Notion / Google Drive /
Wiki style), drop them into `Q&A/` (gitignored) and run:

```sh
make convert      # scripts/convert_qa.py: trafilatura → markdown
```

This produces clean markdown in `corpus/intra/` ready to ingest.

## LLM choices

LightRAG calls the LLM at two distinct times:

| Phase | What happens | Default | Why |
|---|---|---|---|
| **Ingest** | Entity / relation extraction per chunk | Ollama qwen2.5:7b | Free, runs locally, ~2–7h overnight on a Mac |
| **Query** | Final answer generation | Ollama qwen2.5:7b | Free, private, ~30–90s per query |

Set `GROQ_API_KEY` to switch ingest to Groq's free tier (~10x faster) —
but be aware: Groq free tier caps at 6K tokens-per-minute, which is at
or below LightRAG's prompt size. For this corpus, **stick with Ollama
for ingest**. If you want fast Groq ingest, upgrade to Groq Dev tier
(~$3 one-time for the full corpus).

Queries always run on local Ollama for privacy and zero per-query cost.

## Project layout

```
discordBot/
├── bot/
│   ├── __init__.py
│   ├── __main__.py        # discord client + /ask + greeting gate
│   ├── ingest.py          # CLI: corpus → LightRAG graph
│   ├── llm.py             # deprecated stub (LightRAG handles generation)
│   └── rag.py             # LightRAG wrapper, query, source extraction
├── corpus/
│   ├── README.md          # how to add documents
│   └── intra/             # 60 converted intra pages (the knowledge base)
├── scripts/
│   ├── convert_qa.py      # HTML/PDF → markdown via trafilatura
│   └── ingest_status.py   # progress / ETA snapshot for `make ingest-status`
├── research/              # pre-build design notes
├── Q&A/                   # local-only raw HTML/PDF source (gitignored)
├── rag_storage/           # generated LightRAG state (gitignored)
├── .env.example
├── Makefile               # install / ingest / run / webui / convert / status
├── README.md
└── requirements.txt
```

## Make targets

| Target | What it does |
|---|---|
| `make install` | Create `.venv` and install requirements |
| `make convert` | Convert raw HTML/PDF in `Q&A/` to markdown in `corpus/intra/` |
| `make ingest` | Build the LightRAG graph (slow first time) |
| `make ingest-status` | Show ingest progress, ETA, recent log lines |
| `make ingest-tail` | `tail -f` the live ingest log |
| `make run` | Start the Discord bot |
| `make webui` | Launch the LightRAG visualization UI on `:9621` |
| `make clean` | Remove generated state and pycache |

## Roadmap

- 42 API integration: identity verification, `/me` dashboard, Black Hole alerts.
- Feedback loop: thumbs-up/down reactions feed a curated answer store.
- Eval set + retrieval metrics.
- Source-citation hyperlinks back to the source intra page.
