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
    sentence-transformers         Ollama qwen2.5:7b   (queries — local, free)
    paraphrase-multilingual       (or)
    -MiniLM-L12-v2  (384-d)       Groq qwen3-32b      (ingest fast path*)

        ┌───────────────────────────────────────────────┐
        │ rag_storage/   (regenerable, gitignored)      │
        │   ├─ KV stores              (JSON)            │
        │   ├─ vector DB              (NanoVectorDB)    │
        │   └─ knowledge graph        (NetworkX, *.graphml)
        └───────────────────────────────────────────────┘
```

\* Groq's free tier caps at 6K tokens-per-minute per request, which is
**below** LightRAG's prompt size for entity extraction. So Ollama is
the practical default for full-corpus ingest. See [LLM choices](#llm-choices).

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
├── scripts/
│   ├── convert_qa.py        # HTML/PDF → markdown (trafilatura + bs4 + pdftotext)
│   ├── ingest_status.py     # snapshot for `make ingest-status`
│   └── retry_failed.py      # cleanup + retry for stuck docs (see below)
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

### 3. Install Ollama + pull a model

```sh
brew install ollama
ollama serve &              # keep running in background
ollama pull qwen2.5:7b      # ~4.7 GB, used for query answers (and ingest if no Groq key)
```

### 4. Build + run

```sh
make install                # creates .venv, installs deps
make convert                # only if you have raw HTML/PDF in Q&A/
make ingest                 # build the LightRAG knowledge graph
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
| `make ingest` | Build the LightRAG graph. Slow first time (entity extraction). |
| `make ingest-status` | Show progress, ETA, recent log lines |
| `make ingest-tail` | `tail -f` the live ingest log |
| `make run` | Start the Discord bot |
| `make webui` | Launch LightRAG visualization UI on `:9621` |
| `make clean` | Remove generated state and pycache |

## LLM choices

LightRAG calls the LLM at two distinct phases:

| Phase | Default | Why |
|---|---|---|
| **Ingest** (entity / relation extraction) | Ollama `qwen2.5:7b` | Free, local, no rate limits. Slow (~2–7h overnight on a Mac). |
| **Query** (answer generation) | Ollama `qwen2.5:7b` | Free, private, ~30–90s per query on an M-series Mac. |

Setting `GROQ_API_KEY` switches *ingest* to Groq (10× faster on paper) —
**but** Groq's free tier caps at 6K tokens-per-minute per request, which
is at or below the size of LightRAG's entity-extraction prompt. Most
docs will fail with HTTP 413. Choices:

- **Stick with Ollama for ingest** (default, what most people should do).
- **Pay for Groq Dev tier** (~$3 one-time for the full corpus, ~30 min ingest).

Queries always run on local Ollama — privacy + zero per-query cost.

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

### Ingest leaves some docs in `failed` status

Big multi-page docs sometimes hit `httpx.ReadTimeout` or LightRAG's
internal worker timeout when `qwen2.5:7b` takes too long to extract
entities from a chunk. Re-running `make ingest` doesn't retry them
(LightRAG creates `dup-*` ghost entries instead). Use the surgical
retry helper:

```sh
.venv/bin/python scripts/retry_failed.py
```

It cleans `dup-*` noise from `kv_store_doc_status.json`, flips
`failed`-status entries back to `pending`, and re-runs the proper
LightRAG retry pipeline (`apipeline_process_enqueue_documents`) with
smaller chunks (600 tokens) and bumped timeouts (900s).

If the same docs still fail after that, the realistic options are
(a) accept the partial graph and ship, (b) clean re-ingest from scratch
with `make clean && make ingest`, or (c) pay for Groq Dev tier and
re-ingest fast.

### Query latency is high (60–200s)

That's local Ollama doing real work for every `/ask`. Discord lets
you wait up to 15 min on a deferred reply, so it works — but it's not
snappy. If you want sub-second queries, swap the query LLM to Groq
(loses privacy) or upgrade hardware.

### Slash commands don't show up

Set `DISCORD_GUILD_ID` in `.env` to your test server's id and restart.
Without it, sync is global and takes up to an hour to propagate.

## Roadmap

- 42 API integration: identity verification, `/me` dashboard, Black Hole alerts.
- Feedback loop: thumbs-up/down reactions feed a curated answer store.
- Eval set + retrieval metrics.
- Hyperlinked citations back to the source intra page.
