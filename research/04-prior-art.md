# 04 — Prior art

A survey of existing 42-API tools and Discord bots, with what to copy
and what to avoid.

## Discord bots specifically

### `paotsaq/42discord_bot` (42 Lisboa)

- Stack: Python 3.9+, `discord.py`, modular `cogs/` layout.
- Community-managed bot for the 42Lisboa server.
- Token in `token.txt`; cogs split commands by feature.
- Pattern worth copying: clean separation of `bot.py` entry, `cogs/`
  command modules, `messages/` text templates, `scripts/` for
  out-of-band tasks like the OAuth callback server.

### `Asandolo/42bots`

- Ruby. Archived as of April 2025 — read-only.
- Small (one `bot.rb`, ~6 commits). Useful only as a sanity check
  that the basics fit in one file when you stay narrow.

### `intra-verify-42tokyo`

- Verifies that a Discord member is a 42Tokyo student via OAuth.
- Single-feature bot — exactly the kind of focused, real-problem build
  the hackathon brief rewards.

### `42intra_Pic`

- Posts the 42 intra profile picture for a given login.
- Trivial implementation; demonstrates the bare-minimum pattern of
  "Discord slash command → API call → embed reply".

## API libraries (copy these patterns)

### `hivehelsinki/42api-lib` (Python)

- Class-based wrapper: `IntraAPIClient` with `.get()`, `.pages()`,
  `.pages_threaded()`.
- Reads credentials from a config file.
- Threaded pagination for full-collection pulls.
- Worth using directly if the bot is in Python and you want to skip
  writing the request layer.

### `42Charts/42-api-aggregator` (Node.js)

- Production-grade aggregator that powers `42charts.com`.
- Demonstrates: cursor-style pagination, multi-token pooling for
  higher effective rate limits, persistent caching to a database.
- More complex than a hackathon needs, but useful for understanding
  what scaling out looks like.

### `goft` (Go CLI)

- Small CLI for poking the API. Good for ad-hoc data exploration
  while designing bot features.

### `RP42/pkg/api/` (Go)

- Concise location-fetching patterns. The structs and request
  builders are clear and minimal.

## Web tools and dashboards

### `42evaluators.com`

- Live web dashboard ranking and listing evaluators.
- Demonstrates how to surface `scale_teams` data usefully.
- Relevant for the "long review queue" theme — anything that helps
  students find an available evaluator faster is on-mission.

### `42Charts` / `42charts.com`

- Long-running stats site (deceased / replaced over time).
- Ideas worth borrowing: per-cohort cohort progress, logtime trends,
  retention dashboards.

### `intra42` (`pvarry/intra42`)

- Unofficial open-source 42 intranet app.
- Demonstrates a near-complete client of the API, including offline
  caching and OAuth UX.

### `42-blackhole-calculator` (`erdelp/42-blackhole-calculator`)

- Next.js + 42 OAuth.
- Pulls cursus_users to predict blackhole timing and pace.
- Caveat from the README: "freeze day calculation is not guaranteed
  to be working accurately because of unretrievable data from the
  42 API." Freeze data isn't exposed — don't promise users an exact
  freeze-aware blackhole date.

### `42-pcalculator` (`slqye/42-pcalculator`)

- Project-completion → level-gain + blackhole-gain calculator.
- The math here can be reused for a Discord `!simulate <project>`
  command: "what level/blackhole would I be at if I finish minishell?"

### `campus42` (`AlexEzzeddine/campus42`)

- Map of who's on campus.
- The pattern of listing active locations + grouping by row/post is
  directly applicable to a Discord "/whois-on-campus" command.

### `badge42`

- Generates dynamic SVG badges (level, logtime, etc.) for embedding
  in GitHub READMEs.
- Idea: the same data points work as Discord embed images.

## Patterns to copy

1. **Token-bucket rate limiting.** Every reliable client implements
   this. ~30 lines.
2. **Single shared token cache.** Don't refresh the token per request,
   per-user, or per-cog.
3. **Background loop polling, not on-demand fetching, for any
   "current state" feature.** Poll every N minutes, push to Discord
   via webhooks. Avoids spiking on user demand.
4. **Persist OAuth refresh tokens encrypted at rest.** A linked
   Discord ↔ 42 user is a high-value record. Don't keep the access
   token only — it expires; you need the refresh token to renew.
5. **Resolve campus_id and cursus_id once, hardcode after.** Saves
   a lookup on every other request.

## Patterns to avoid

1. **Fetching all users on a campus on demand.** That's ~1000+ items
   for 42Tokyo, which is 10+ pages, which is half your per-second
   budget. Pre-aggregate on a schedule.
2. **Storing raw 42 access tokens in plain text.** Even in a hackathon
   demo this is a bad look in front of judges.
3. **One-shot cron jobs for time-sensitive notifications.** A
   long-running process with an in-memory schedule is more reliable
   than `cron` for "remind me 30 min before my eval" features.
4. **Trusting `location` on the user object as live presence.** It's
   updated, but cache-laggy. Use the locations endpoint with
   `filter[active]=true` for live data.
5. **Duplicating intra features without adding Discord-side value.**
   The hackathon brief explicitly rewards solving a real 42Tokyo
   problem — a bot that just mirrors intra adds nothing the
   intranet doesn't already do.

## Reference list (curated)

The `leeoocca/awesome-42` repository at
<https://github.com/leeoocca/awesome-42> is the most comprehensive
maintained list of 42 community tools. Skim its "API & Bots"
sections before deciding what's worth building from scratch versus
forking.
