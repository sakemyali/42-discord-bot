# Research notes — 42Tokyo Discord Bot Hackathon

Pre-build research on the 42 API and how to use it for a Discord bot that
solves a real 42Tokyo community problem.

## Files

| # | File | What's in it |
|---|------|--------------|
| 1 | [01-api-fundamentals.md](./01-api-fundamentals.md) | App registration, OAuth2 flows, scopes, base URL, rate limits |
| 2 | [02-api-specification.md](./02-api-specification.md) | Pagination, filtering, sorting, range queries, error handling, headers |
| 3 | [03-endpoints-and-data.md](./03-endpoints-and-data.md) | Endpoint catalog grouped by resource, with key fields |
| 4 | [04-prior-art.md](./04-prior-art.md) | Existing 42 community tools, bots, libraries, patterns |
| 5 | [05-feature-ideas.md](./05-feature-ideas.md) | Hackathon themes mapped to concrete bot features and the API calls behind each |
| 6 | [06-architecture.md](./06-architecture.md) | Bot architecture, caching, hosting, OAuth strategy, rate-limit math |
| - | [sources.md](./sources.md) | Every URL referenced |

## TL;DR

- **API**: REST, JSON, base URL `https://api.intra.42.fr/v2`, OAuth2 (Client
  Credentials for service-level reads, Authorization Code for user-linked
  actions).
- **Rate limit**: 2 req/s, 1200 req/hour per app — must cache aggressively.
- **Most useful resources for a Discord bot**:
  - `users`, `cursus_users` (level, blackhole, grade, skills)
  - `projects_users` (status, marks, retries) — review queue / progress
  - `scale_teams` + `slots` (peer evaluations, available eval slots)
  - `locations` (who's on campus right now)
  - `events` + `events_users` (campus events, subscribers)
  - `achievements_users` (badges earned)
  - `correction_point_historics` (eval point ledger)
- **Core problems the hackathon brief calls out**:
  - **Community Activation** — declining campus visits, dormant
    events/associations, low interaction.
  - **Curriculum Support** — Black Hole risk, long review-queue waits,
    review cancellations, less peer discussion than Piscine.
  - **Staff Support** — manual ops, slow student→staff feedback, urgent
    support routing.
- **Constraints to keep in mind**:
  - 1–3 person team, must deploy as a Discord bot, IP transfers to 42, must
    be deployable to the 本科 production server.
  - Self-host dev/test; production hand-off is to 42 Tokyo staff.

## How to use these notes

Read in order 1 → 2 → 3 to understand the API surface. Skip to 5 if you
already know the API and want to brainstorm features. Read 6 before
writing code — it covers the rate-limit math and OAuth strategy that
shape architecture choices.
