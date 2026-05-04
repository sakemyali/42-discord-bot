# 06 — Architecture notes

Practical considerations for shipping a Discord bot on top of the
42 API in hackathon time.

## Rate-limit math

The default budget is **2 req/s, 1200 req/hour per app**. That's
the binding constraint. The hourly cap is the surprising one — at
2 req/s sustained, you'd hit 7200/hour, so the bot is throttled to
~17% of its naive maximum.

Implications:

- A 1000-user 42Tokyo cohort cannot be polled per-user every hour.
  At 2 req/s that's exactly 1000/3600 ≈ 0.28 req/s — fine. But every
  feature that adds a per-user request multiplies. Two features =
  ~0.56 req/s on top of any user-triggered queries. Three features
  starts approaching the limit.
- **Aggregate by campus, not by user.** `GET /v2/campus/{id}/users`
  paginates 100/page → ~10 requests for the whole 42Tokyo cohort →
  one polling cycle every 5 minutes uses 120 req/hour, leaving
  1080/hour for everything else.
- **Cache aggressively.** Most data — events, project catalog,
  campus list, achievements catalog — changes daily at best. Cache
  for hours, not seconds.
- **User-triggered commands** should hit cache first, then API.
  Slash command latency budget is ~3 seconds (Discord interaction
  timeout), so deferred replies are essential for anything that
  fans out.

## Polling cadence cheat-sheet

| Data | Cadence | Why |
|------|---------|-----|
| Active locations on campus | 1–2 min | "Who's here right now" features |
| Upcoming evaluations (campus-wide) | 5 min | Cancellation detection |
| Per-user blackhole + projects | 30–60 min | Black Hole alerts and stale-project nudges |
| Events (campus) | 60 min | Weekly cadence; nothing is urgent |
| Project catalog | 24 h | Effectively static |
| Campus list | 7 d | Effectively static |
| Coalitions + scores | 6 h | Leaderboard updates |
| Achievements catalog | 7 d | Effectively static |
| Achievements earned (per-user) | 60 min | "You unlocked X" feels live enough at this rate |

## OAuth strategy

Two-tier:

1. **Bot-level token** (Client Credentials). One token, refreshed
   in-process. Used for all aggregate queries: campus locations,
   events, public profiles, leaderboards.
2. **Per-user tokens** (Authorization Code). Stored encrypted, one
   row per linked Discord ↔ 42 user. Used only for `/v2/me` and
   privileged reads. Refresh tokens persist across bot restarts.

User linking flow:

```
Discord: /link
  → bot DMs the user a one-time URL with a state nonce
  → user opens URL → 42 OAuth → callback to your webserver
  → webserver stores (discord_id, intra_login, access_token,
                      refresh_token, expires_at) encrypted
  → bot DMs "linked! you're now %login%"
```

For demo simplicity in the hackathon, Client Credentials alone is
enough for ~80% of the features in `05-feature-ideas.md`. Save
per-user OAuth for v2 if time runs out.

## Storage

For a hackathon, **SQLite with a single file** is the right answer:

- Easy to ship in the repo (the file itself can be `.gitignore`d
  and recreated by a `seed` script).
- Trivial backup.
- Works on a single host; no infra to deploy.

Schema sketch:

```sql
CREATE TABLE links (
    discord_id     TEXT PRIMARY KEY,
    intra_login    TEXT NOT NULL UNIQUE,
    access_token   BLOB NOT NULL,    -- encrypted with app key
    refresh_token  BLOB NOT NULL,    -- encrypted
    expires_at     INTEGER NOT NULL,
    linked_at      INTEGER NOT NULL
);

CREATE TABLE cache (
    key        TEXT PRIMARY KEY,
    value      BLOB NOT NULL,
    expires_at INTEGER NOT NULL
);

CREATE TABLE preferences (
    discord_id   TEXT NOT NULL,
    feature      TEXT NOT NULL,
    settings     TEXT NOT NULL,    -- JSON
    PRIMARY KEY (discord_id, feature)
);

CREATE TABLE jobs (
    id           INTEGER PRIMARY KEY,
    kind         TEXT NOT NULL,
    run_at       INTEGER NOT NULL,
    payload      TEXT NOT NULL
);
```

Encryption: use `cryptography.Fernet` (Python) or `libsodium`
secret-box. The key lives in an env var; if the env var is gone the
data is unreadable. Acceptable for a hackathon, sufficient for
production after a key-rotation policy.

## Bot architecture

A small, single-process bot is enough:

```
+---------------------------------------------------+
|                      Discord                      |
+--------------------------+------------------------+
                           | gateway events / interactions
+--------------------------v------------------------+
|                      Bot process                  |
|  +-----------+  +-------------+  +-------------+  |
|  | command   |  | scheduler   |  | webserver   |  |
|  | handlers  |  | (polling +  |  | (OAuth      |  |
|  | (cogs)    |  |  reminders) |  |  callback)  |  |
|  +-----+-----+  +------+------+  +------+------+  |
|        |               |                |         |
|  +-----v---------------v----------------v------+  |
|  |       42 API client (token + cache)         |  |
|  +-------------------+--------------------------+  |
|                      |                             |
|                  +---v----+                        |
|                  | SQLite |                        |
|                  +--------+                        |
+----------------------------------------------------+
```

Components:

- **Command handlers**: one `cog` per feature (`me`, `oncampus`,
  `findcorrector`, `link`, `feedback`, …).
- **Scheduler**: a single async loop that runs jobs from the `jobs`
  table on schedule. Replace `cron` with this — it survives
  restarts cleanly because state is in SQLite.
- **Webserver**: small (Flask / FastAPI / aiohttp) for OAuth
  callback only. Same process, so no separate deploy.
- **42 API client**: token refresh, rate limiting, caching. ~150
  lines.

## Language choice

Python with `discord.py` is the lowest-friction option:

- `discord.py` is mature and widely documented.
- Async fits the polling-heavy workload.
- `requests`/`httpx` make API calls trivial.
- `apscheduler` or a hand-rolled async loop covers the scheduler.

Node.js with `discord.js` works equally well; pick whichever the
team is fastest in. Avoid mixing: one language for the bot, one
language for the OAuth callback is overkill.

## Hosting

For development:

- Run locally; ngrok the OAuth callback during testing.

For demo / hand-off to 42 production:

- Single VPS or container is fine. The brief says winning teams
  get dev support to deploy on the 本科 production server, so
  packaging matters more than infra automation:
  - Provide a `docker-compose.yml` with the bot, the SQLite
    volume, and an `.env.example`.
  - Document the env vars (`DISCORD_TOKEN`, `INTRA_UID`,
    `INTRA_SECRET`, `OAUTH_CALLBACK_URL`, `ENCRYPTION_KEY`).
  - Include a `Makefile` with `make run`, `make migrate`,
    `make seed`.

## Security notes

- **Never log tokens.** Filter them out of structured logs at the
  request-client level.
- **Never echo user data to public channels by default.** Default to
  ephemeral replies; let users opt into public.
- **Verify Discord interaction signatures** if exposing an HTTP
  endpoint for slash commands (only relevant if not using gateway).
- **Discord token rotation**: store in env, not in code. The
  Discord developer portal lets you reset the token if leaked.
- **42 OAuth state parameter**: required to prevent CSRF on the
  callback. Use a random, per-user, time-bound nonce.
- **PII in the database**: 42 logins are public, but linked
  Discord IDs ↔ 42 logins is more sensitive. Don't expose this
  mapping in any command output.

## What to build first (concretely)

1. Day 1: Skeleton bot + `/ping`. Prove gateway works.
2. Day 1: 42 API client with Client Credentials auth + rate
   limiter + caching. Prove a `GET /v2/campus` works.
3. Day 1: `/oncampus` and `/me` (using login parameter, not OAuth).
   Wins a quick visible result.
4. Day 2: SQLite + OAuth callback + `/link`. Now `/me` works on
   the user's own account.
5. Day 2: Scheduler + Black Hole radar DMs. The killer feature.
6. Day 2-3: `/findcorrector`. Eval-cancellation early-warning.
7. Day 3: Polish, embeds, error handling, deploy script, demo
   video.

## Demo-day checklist

- All commands work without a debugger attached.
- The bot recovers from a restart mid-session (state in SQLite).
- A live `/me` and a live `/findcorrector` against the real API
  during the demo (not pre-recorded), with at least one fallback
  embed if the API is slow.
- Clear "what 42 problem this solves" in slide 1, not slide 5.
- Repo has a working `make run` from a fresh clone with only the
  env file set.
