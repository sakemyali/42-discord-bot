# 03 — Endpoints and data models

A practical catalog of the endpoints most useful to a Discord bot,
grouped by resource. Field names are the canonical 42 attribute names;
where a field is critical for hackathon use cases it is annotated.

Endpoint counts (e.g. "5 endpoints") are from the public docs index and
include create/update/delete variants — most bots only need the GET
listed below.

---

## Users (`/v2/users`)

15 endpoints. Core resource — almost every other endpoint joins back
here.

| Method | Path | Notes |
|--------|------|-------|
| GET | `/v2/users` | List all users — heavy, paginate aggressively |
| GET | `/v2/users/:id` | One user, by numeric id or login |
| GET | `/v2/me` | The authenticated user (web flow only) |
| GET | `/v2/campus/:campus_id/users` | All users of a campus |
| GET | `/v2/cursus/:cursus_id/users` | All users in a cursus |

Key fields on a user:

| Field | Use |
|-------|-----|
| `id`, `login`, `email`, `displayname` | Identity |
| `image.link`, `image.versions.{small,medium,large,micro}` | Avatar |
| `correction_point` | Eval points (currency for booking peer reviews) |
| `wallet` | Internal currency used for some events / vouchers |
| `pool_year`, `pool_month` | Piscine cohort — useful for clustering and "your batch is on campus" features |
| `location` | Currently-occupied workstation, e.g. `e1r1p1`. `null` = not on campus |
| `cursus_users[]` | Embedded summary of cursus participation |
| `projects_users[]` | Embedded summary of projects |
| `achievements[]` | Earned badges |
| `staff?` | Boolean — useful to filter out staff |
| `created_at`, `updated_at` | The latter is set on most state changes |

`location` being a single string is a common surprise. To get full
session history, use the locations endpoints below.

---

## Cursus users (`/v2/cursus_users`)

3 listing endpoints + graph + create.

| Method | Path | Notes |
|--------|------|-------|
| GET | `/v2/cursus_users` | All cursus enrollments across the network |
| GET | `/v2/users/:user_id/cursus_users` | One user's cursus enrollments |
| GET | `/v2/cursus/:cursus_id/users` | Alternative — same data sliced by cursus |
| GET | `/v2/cursus_users/:id/graph` | Skill graph for one cursus enrollment |

Key fields:

| Field | Use |
|-------|-----|
| `id` | Cursus enrollment id |
| `begin_at` | When the user started the cursus |
| `end_at` | When the cursus ended (null = ongoing) |
| `blackhole_at` | The Black Hole deadline. **Single most important field for curriculum-support bots.** |
| `grade` | "Cadet", "Member", etc. |
| `level` | Decimal level (e.g. `8.42`) |
| `skills[]` | Per-skill levels |
| `cursus.id`, `cursus.name`, `cursus.slug` | Which cursus (`42cursus` is the main one) |
| `has_coalition` | Whether coalition data exists |
| `user.id`, `user.login` | Joined user info |

For 42Tokyo 本科 (Common Core / 42cursus), `cursus.slug == "42cursus"`.
Filter by `filter[cursus_id]=21` (the canonical id of `42cursus`).

---

## Projects users (`/v2/projects_users`)

3 listing endpoints + show + update.

| Method | Path | Notes |
|--------|------|-------|
| GET | `/v2/projects_users` | All project participations |
| GET | `/v2/users/:user_id/projects_users` | One user's projects |
| GET | `/v2/projects/:project_id/projects_users` | Everyone working on a project |
| GET | `/v2/projects_users/:id` | One participation |

Key fields:

| Field | Use |
|-------|-----|
| `id` | Participation id |
| `occurrence` | Retry counter — `0` = first attempt, `1`+ = retries |
| `final_mark` | Score (0–125 typical) |
| `status` | One of: `creating_group`, `searching_a_group`, `in_progress`, `waiting_for_correction`, `finished`, `parent` |
| `validated?` | Boolean — passed (≥ 50% on most projects) |
| `current_team_id` | Linked `team` resource |
| `marked` | Has been graded |
| `marked_at` | When the final mark was set |
| `retriable_at` | When the user can retry after a fail |
| `project.id`, `project.name`, `project.slug` | Joined project info |

`status == "waiting_for_correction"` is the field that powers any
"who's stuck waiting for a peer review?" feature.

---

## Scale teams (`/v2/scale_teams`) — peer evaluations

9 listing endpoints. The richest resource for curriculum/staff features.

| Method | Path | Notes |
|--------|------|-------|
| GET | `/v2/scale_teams` | All evaluations |
| GET | `/v2/users/:user_id/scale_teams` | A user's evaluations (as corrector OR corrected) |
| GET | `/v2/users/:user_id/scale_teams/as_corrector` | Only those they evaluated |
| GET | `/v2/users/:user_id/scale_teams/as_corrected` | Only those they were evaluated in |
| GET | `/v2/teams/:team_id/scale_teams` | Evaluations for a specific team |

Key fields:

| Field | Use |
|-------|-----|
| `id` | Eval id |
| `begin_at` | When the eval is scheduled |
| `scale.id`, `scale.duration` | Which scale was used and how long it allots |
| `corrector.id`, `corrector.login` | Who evaluated |
| `correcteds[].login` | Who was evaluated (can be a team) |
| `final_mark` | Score given |
| `comment`, `feedback` | Free-text |
| `feedback_rating` | Star rating from corrected → corrector |
| `truant` | Object — set if someone no-showed |
| `flag.name` | Outcome flag: "Ok", "Empty work", "Cheat", "Crash", etc. |
| `filled?` | Has both parties filled feedback |

`filter[future]=true` returns upcoming evaluations. Combined with a
campus filter via the user join, this is "who has evals coming up
today?" — directly addresses the review-cancellation issue.

---

## Slots (`/v2/slots`) — eval availability

4 listing + create.

| Method | Path | Notes |
|--------|------|-------|
| GET | `/v2/slots` | All slots |
| GET | `/v2/me/slots` | Authenticated user's slots |
| GET | `/v2/projects/:project_id/slots` | Open slots for a project, current user can book |

Key fields:

| Field | Use |
|-------|-----|
| `id` | Slot id |
| `begin_at`, `end_at` | Time window |
| `scale_team` | Linked eval (null = not yet booked) |
| `user` | Owner of the slot (the corrector) |

A slot is a 30-min-to-2-week window a user offers themselves as an
evaluator. Booking it pairs the slot with a scale_team. This is the
data behind any "long review queue" mitigation.

---

## Locations (`/v2/locations`) — campus presence

3 listing + create + close.

| Method | Path | Notes |
|--------|------|-------|
| GET | `/v2/locations` | All sessions globally |
| GET | `/v2/users/:user_id/locations` | Sessions of one user |
| GET | `/v2/campus/:campus_id/locations` | Sessions of one campus |

Key fields:

| Field | Use |
|-------|-----|
| `id` | Session id |
| `begin_at` | Login time |
| `end_at` | Logout time (null = still active) |
| `host` | Workstation name (e.g. `e1r1p1`) |
| `campus_id` | Campus |
| `primary` | Was this the primary session that day |

Common queries:

```
GET /v2/campus/26/locations?filter[active]=true&per_page=100
  → who's on campus right now (42Tokyo campus_id is the one to confirm)

GET /v2/users/abc/locations?range[begin_at]=2026-04-01T00:00:00Z,2026-05-01T00:00:00Z
  → the user's logtime sessions for April

GET /v2/users/abc/locations?filter[active]=true
  → the user's currently-active session (or empty)
```

Logtime is computed by summing `(end_at or now) - begin_at` over a
period. There is no direct "logtime in seconds" field — the bot has
to aggregate.

---

## Events (`/v2/events`) and events_users

5 listing + create.

| Method | Path | Notes |
|--------|------|-------|
| GET | `/v2/events` | All events |
| GET | `/v2/campus/:campus_id/events` | Events at one campus |
| GET | `/v2/cursus/:cursus_id/events` | Events for one cursus |
| GET | `/v2/users/:user_id/events` | Events the user is registered for |
| GET | `/v2/events/:event_id/users` | Users registered for an event |

Key fields on an event:

| Field | Use |
|-------|-----|
| `id`, `name`, `description` | Display |
| `kind` | "rush", "workshop", "association", "meetup", "conference", "other" |
| `begin_at`, `end_at` | Schedule |
| `location` | Physical location string |
| `max_people`, `nbr_subscribers` | Capacity / current count |
| `campus_ids[]` | Which campuses host it |
| `cursus_ids[]` | Which cursuses |

Use `filter[future]=true` for upcoming events.

`events_users` (join table) is what gives you subscribers; create an
event_user via POST to register a user (requires user-token + scopes).

---

## Achievements (`/v2/achievements` and `/v2/achievements_users`)

| Method | Path | Notes |
|--------|------|-------|
| GET | `/v2/achievements` | All achievements (catalog) |
| GET | `/v2/users/:user_id/achievements` | User's earned achievements |
| GET | `/v2/achievements/:achievement_id/users` | Earners of one achievement |

Achievement fields: `id`, `name`, `description`, `tier`, `kind`,
`visible`, `image`, `nbr_of_success`.

A nice "unlock recently" Discord notification source.

---

## Coalitions (`/v2/coalitions` and `/v2/coalitions_users`)

| Method | Path |
|--------|------|
| GET | `/v2/coalitions` |
| GET | `/v2/users/:user_id/coalitions_users` |
| GET | `/v2/coalitions/:coalition_id/coalitions_users` |
| GET | `/v2/coalitions/:coalition_id/scores` |

Coalition fields: `id`, `name`, `slug`, `image_url`, `cover_url`,
`color`, `score`, `user_id` (leader). Coalition_users gives per-user
scores in coalition leaderboards.

42Tokyo coalitions are the local pool teams used for community
gamification — relevant for the activation theme.

---

## Correction point historics

| Method | Path |
|--------|------|
| GET | `/v2/users/:user_id/correction_point_historics` |

Returns a ledger of `+`/`-` changes to a user's `correction_point`,
each tied to a `reason`. Useful for "you earned 1 point evaluating X"
or trend graphs.

---

## Other resources worth knowing

| Resource | Brief |
|----------|-------|
| `/v2/campus` | List of campuses; resolve `42Tokyo` → numeric `id` once and hardcode. |
| `/v2/projects` | Catalog of all projects; `slug`-keyed (e.g. `libft`, `minishell`). |
| `/v2/teams` | Project teams; supports group-based work. |
| `/v2/feedbacks` | Free-text feedback objects attached to scale_teams or events. |
| `/v2/exams`, `/v2/exams_users` | Exam definitions and per-user attempts. |
| `/v2/quests`, `/v2/quests_users` | The "quest" tree of project requirements. |
| `/v2/groups`, `/v2/groups_users` | Tag-style staff/student groups. |
| `/v2/titles`, `/v2/titles_users` | Earned titles (rare). |
| `/v2/skills` | Skill catalog (joined into cursus_users.skills). |
| `/v2/notes` | Staff notes on students (`tig` scope). |
| `/v2/topics`, `/v2/messages` | Forum threads and posts (`forum` scope). |
| `/v2/partnerships` | Partner companies / sponsors. |
| `/v2/mailings` | Bulk mailing definitions (staff). |

## Resolving 42Tokyo's IDs

Before hardcoding anything, resolve the canonical IDs once:

```
GET /v2/campus
  → find { "name": "Tokyo", ... } and note its id
GET /v2/cursus
  → find { "slug": "42cursus", ... } and note its id (typically 21)
```

Cache these in a config file. They are stable.
