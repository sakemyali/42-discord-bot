# 42Tokyo Discord QA Bot

A staff-support Discord bot. Students ask questions in Discord with `/ask`;
the bot answers from a vetted corpus of rules and procedures, citing the
source. When it is not confident, it forwards the question to a staff
channel instead of guessing.

## Status

MVP. One slash command (`/ask`), one corpus folder, optional Groq for nicer
phrasing, optional staff escalation channel.

## Quick start

### 1. Create a Discord bot

1. Go to <https://discord.com/developers/applications>, click **New Application**.
2. Open the **Bot** tab → click **Reset Token** → copy the token.
3. Under **Privileged Gateway Intents**, leave everything off (the bot does
   not need them for slash commands).
4. Open the **OAuth2 → URL Generator** tab.
   - Scopes: `bot`, `applications.commands`
   - Bot permissions: `Send Messages`, `Embed Links`, `Use Slash Commands`,
     `Read Message History`
5. Open the generated URL in a browser, choose your test server, and invite
   the bot.

### 2. Configure

```sh
cp .env.example .env
```

Fill in:

- `DISCORD_TOKEN` — required, from step 1.
- `DISCORD_GUILD_ID` — optional but strongly recommended in development.
  Your test-server id (right-click the server in Discord with developer
  mode on → Copy Server ID). Without this, slash commands take up to 1
  hour to appear.
- `GROQ_API_KEY` — optional. Sign up at <https://console.groq.com/keys>
  for a free key. If empty, the bot returns the top-3 corpus chunks
  verbatim instead of generating an answer.
- `STAFF_CHANNEL_ID` — optional. Discord channel id where the bot posts
  questions it cannot answer. Without it, escalation is silent.
- `MIN_SIMILARITY` — escalation threshold. Default `0.35`. Raise it to
  escalate more aggressively, lower it to be more lenient.

### 3. Add documents

Drop `.md` or `.txt` files into `corpus/`. Replace `example-rules.md` with
your own content. See `corpus/README.md` for format notes.

### 4. Install + run

```sh
make install   # creates .venv and installs requirements
make ingest    # builds the embedding index from corpus/
make run       # starts the bot
```

The first `ingest` downloads the embedding model (~80 MB). Subsequent
runs are fast.

In Discord, type `/ask How does the Black Hole work?` and the bot replies
with an answer plus the source filenames.

## How it works

```
                 +--------------+
   /ask question | Discord bot  |
   ------------> |  (bot/...)   |
                 +------+-------+
                        |
                        v
                 +------+-------+
                 |  RAG index   |   sentence-transformers + cosine
                 | (pickle on   |
                 |  disk)       |
                 +------+-------+
                        |
            top-3 chunks + scores
                        |
                        v
        +--------+-+----+----+--------+
        | score  | <  threshold       |
        |  yes   |        no          |
        +---+----+--------------------+
            |              |
            v              v
       Escalate to     Generate with
       staff channel   Groq (or fall
       (no answer)     back to top-3
                       chunks verbatim)
```

## Project layout

```
discordBot/
├── bot/
│   ├── __init__.py
│   ├── __main__.py    # discord client + /ask command
│   ├── ingest.py      # CLI: build the corpus index
│   ├── llm.py         # optional Groq client
│   └── rag.py         # chunking, embedding, retrieval
├── corpus/            # your knowledge documents (.md, .txt)
├── data/              # generated; index.pkl lives here (gitignored)
├── research/          # design notes
├── .env.example
├── Makefile
├── README.md
└── requirements.txt
```

## Roadmap

- LightRAG backend for graph-based retrieval over a larger corpus.
- 42 API integration: identity verification, `/me` dashboard, Black Hole alerts.
- Feedback loop: thumbs-up / thumbs-down reactions feed back into a
  curated answer store.
- Eval set + retrieval metrics.
