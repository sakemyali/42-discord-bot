# 05 — Feature ideas mapped to the three themes

Each idea here is paired with the API endpoints behind it so the
team can estimate effort against complexity.

Format:

> **Feature name** — short pitch.
> **Endpoints**: which calls power it.
> **Why it solves a real problem**: tied to the brief.
> **Complexity**: rough relative effort (S/M/L).

---

## Theme 1 — Community Activation

The brief calls out: declining commitment, low campus-visit rates,
dormant events, dormant associations, low interaction.

### "Who's on campus right now?"

- **Pitch**: `/oncampus` slash command shows a live count and a
  randomized sample of students currently logged in at 42Tokyo, with
  their floor/row/post.
- **Endpoints**: `GET /v2/campus/{tokyo_id}/locations?filter[active]=true&per_page=100`
- **Why**: Reduces the "is anyone there?" hesitation that keeps people
  from coming in. Directly attacks the low-visit-rate problem.
- **Complexity**: S. One endpoint, one cache, one embed.

### "Pool buddies on campus"

- **Pitch**: `/mypool` shows which members of the user's piscine
  cohort are on campus right now.
- **Endpoints**:
  - `GET /v2/users/{me}` to read `pool_year` / `pool_month`
  - `GET /v2/campus/{tokyo_id}/users?filter[pool_year]=...&filter[pool_month]=...`
  - cross-reference with active locations.
- **Why**: Cohort affinity is the strongest social driver at 42.
  Surfacing "your batch is here" beats generic "people are here".
- **Complexity**: M. Cohort filter + active-locations join.

### Event nudges

- **Pitch**: Posts upcoming campus events to a configurable Discord
  channel 24h and 1h before they start, with a one-click subscribe
  link.
- **Endpoints**:
  - `GET /v2/campus/{tokyo_id}/events?filter[future]=true`
  - `GET /v2/events/{id}/users` for current subscriber count.
- **Why**: Dormant events are usually a discoverability problem, not
  a content problem. Discord push beats intranet pull.
- **Complexity**: M. Polling loop + state to avoid duplicate posts.

### Coalition leaderboard

- **Pitch**: Weekly post showing 42Tokyo coalition standings, point
  deltas, and the top 10 contributors.
- **Endpoints**: `GET /v2/coalitions`, `GET /v2/coalitions/{id}/scores`,
  `GET /v2/coalitions/{id}/coalitions_users`.
- **Why**: Coalitions are the game layer for community engagement.
  A Discord recap keeps it visible to people who don't open intra.
- **Complexity**: M. Pagination + chart rendering.

### "Solo today" matchmaker

- **Pitch**: Voluntary opt-in. Twice a day, the bot looks at active
  campus locations among opted-in users and pings small groups of
  ~3 to introduce them.
- **Endpoints**: locations + a small Discord-side opt-in store.
- **Why**: Manufactured serendipity. Replicates the Piscine
  table-hopping culture the brief calls out as missing in 本科.
- **Complexity**: M. The matching logic is small; the UX
  (consent, ghosting handling) is the hard part.

### Logtime streaks

- **Pitch**: Track each opted-in user's daily campus presence and
  award streak roles (3, 7, 14, 30 days). Public weekly recap.
- **Endpoints**: `GET /v2/users/{login}/locations?range[begin_at]=...`.
- **Why**: Quantifying habit + light social pressure. Common
  pattern in productivity apps; works because 42 already tracks
  presence.
- **Complexity**: M. Daily aggregation job + Discord role assignment.

---

## Theme 2 — Curriculum Support

The brief calls out: project management, Black Hole risk, lack of
discussion vs. Piscine, long review-queue waits, review cancellations.

### Black Hole radar

- **Pitch**: For each linked user, the bot DMs an alert at T-30, T-14,
  T-7, T-3, T-1 days from `blackhole_at`, with a link to the project
  most likely to push the date back.
- **Endpoints**:
  - `GET /v2/users/{me}/cursus_users` for `blackhole_at` and `level`.
  - `GET /v2/users/{me}/projects_users` for current projects and
    statuses.
- **Why**: Black Hole anxiety is the single most-mentioned 本科 pain
  point. A proactive nudge with a concrete suggested project beats a
  passive countdown.
- **Complexity**: M. Daily check + DM dispatch + simple "project
  worth most days" heuristic from public level/days tables.

### Review queue helper

- **Pitch**: `/findcorrector <project>` shows: number of open
  evaluation slots in the next 24h, who's offering them, and which
  ones are likely to be cancelled (based on the corrector's recent
  no-show ratio).
- **Endpoints**:
  - `GET /v2/projects/{project_id}/slots`
  - `GET /v2/users/{login}/scale_teams/as_corrector` to compute
    the no-show / `truant` ratio over the last N evaluations.
- **Why**: Long waits and review cancellations are explicitly named
  in the brief. Adding signal ("this corrector cancelled 3 of their
  last 10") improves slot selection without adding load on the API.
- **Complexity**: L. Slot data is volatile, the no-show heuristic
  needs careful caching, and the UI needs to be tight.

### Eval reminders + cancellation early-warning

- **Pitch**: When a linked user has a `scale_team` scheduled, the bot
  pings them T-30 min, and if it sees the slot disappear / change
  before that, it posts a "your eval was cancelled — here are open
  slots in the next 4h".
- **Endpoints**:
  - `GET /v2/users/{me}/scale_teams?filter[future]=true`
  - polling on the slot id every few minutes near the scheduled
    time.
- **Why**: Direct mitigation of a brief-named problem. Saves
  students from showing up to a cancelled review.
- **Complexity**: M. Per-user polling needs care to stay under
  rate limits — see the math in `06-architecture.md`.

### Project group finder

- **Pitch**: `/findgroup <project>` lists everyone on 42Tokyo who has
  `status == "searching_a_group"` for the project, with their level
  and last-active timestamp.
- **Endpoints**:
  - `GET /v2/projects/{project_id}/projects_users?filter[campus]={tokyo}&filter[status]=searching_a_group`
- **Why**: Group projects (e.g. minishell, ft_transcendence) often
  stall on group-formation. Solves a friction the intranet does
  poorly.
- **Complexity**: S. One endpoint, one embed.

### "Stuck on a project?" mentor matcher

- **Pitch**: For project X, return the 5 most recent students who
  finished it with a high mark and are still active on campus. They
  are likely candidates for help.
- **Endpoints**:
  - `GET /v2/projects/{id}/projects_users?filter[campus]={tokyo}&filter[status]=finished&sort=-marked_at`
  - cross-check active locations.
- **Why**: Bridges the "less discussion than Piscine" gap by surfacing
  a concrete, askable peer.
- **Complexity**: M. Two-step query + ranking heuristic.

### Personal dashboard

- **Pitch**: `/me` returns an embed: level, blackhole, current
  projects with statuses, eval points, recent achievements,
  logtime this week.
- **Endpoints**:
  - `GET /v2/users/{me}` (or `/v2/me` with web flow)
  - `GET /v2/users/{me}/cursus_users`
  - `GET /v2/users/{me}/projects_users`
  - `GET /v2/users/{me}/locations?range[begin_at]=<7d ago>,<now>`
- **Why**: A familiar "everything in one glance" view that reduces
  context switching to the intranet.
- **Complexity**: M. Heavy on requests — use embedded fields on the
  user object where possible to consolidate.

---

## Theme 3 — Staff Support

The brief calls out: routine ops automation, student → staff feedback
channels, urgent support routing.

### Anonymous-to-staff feedback channel

- **Pitch**: `/feedback <text>` from any verified 42Tokyo student
  posts an anonymous, timestamped message to a staff-only Discord
  channel, with a follow-up tag and a thread for staff response.
- **Endpoints**:
  - Verification only: `GET /v2/me` to confirm 42 identity at the
    `/link` step.
- **Why**: Lowers the friction of speaking up. The threading +
  anonymity is a Discord-native UX that intranet ticketing can't
  match.
- **Complexity**: M. Mostly Discord plumbing, very little 42 API.

### "Help! I'm stuck" triage

- **Pitch**: `/help-me` with category options (eval issue, blackhole,
  account, mental-health) opens a structured ticket in a private
  staff channel and pings the right staff group.
- **Endpoints**:
  - `GET /v2/me` to identify the student.
  - `GET /v2/users/{me}/cursus_users` to attach context (level,
    blackhole) automatically.
- **Why**: Urgent support routing is named in the brief. Pre-filling
  context cuts back-and-forth.
- **Complexity**: M.

### "Who hasn't logged in this week?"

- **Pitch**: Daily/weekly summary post to a staff channel listing
  students who haven't logged in for N days, sorted by how close
  they are to blackhole.
- **Endpoints**:
  - `GET /v2/cursus/{42cursus}/users?filter[campus_id]={tokyo}` (paginate).
  - `GET /v2/users/{login}/locations?range[begin_at]=<7d ago>,<now>` per
    user — heavy. Better: `GET /v2/campus/{tokyo}/locations?range[begin_at]=<7d ago>,<now>&per_page=100` and dedupe by user.
- **Why**: Lets staff intervene before the Black Hole. Replaces a
  manual spreadsheet pull.
- **Complexity**: L. Heavy aggregation; needs a nightly job and a
  caching layer.

### "Eval no-show" report

- **Pitch**: Daily report listing scheduled evaluations that ended
  with `truant` set, grouped by corrector. Helps staff see patterns.
- **Endpoints**:
  - `GET /v2/scale_teams?filter[campus]={tokyo}&range[begin_at]=<24h>` then
    inspect the `truant` field.
- **Why**: The review-cancellation problem from the curriculum brief
  has a staff-side analog: identifying serial cancellers.
- **Complexity**: M.

### Auto-FAQ from intra

- **Pitch**: `/faq <question>` searches the 42 forum (`topics` /
  `messages`) and the bot's own FAQ store, returning the top three
  matches.
- **Endpoints**:
  - `GET /v2/topics`, `GET /v2/messages` (requires `forum` scope).
- **Why**: Routine staff time goes to repeated questions. Auto-FAQ
  shifts that onto self-service, with the option for staff to mark
  the answer canonical.
- **Complexity**: L. Scope acquisition + search relevance.

### "Office hours open" indicator

- **Pitch**: Staff toggle a `/staff-on` command; bot updates a
  voice-channel name or role to "Staff available — DM the channel"
  and pings active students.
- **Endpoints**: none (Discord-only).
- **Why**: Replaces the constant "are any staff free right now?"
  question. Trivial to ship, surprisingly impactful.
- **Complexity**: S.

---

## Recommended hackathon scope

For a 1–3 person team and a graded demo, the strongest single
direction is **Curriculum Support**, anchored on:

1. **Black Hole radar** (proactive DMs based on `blackhole_at`).
2. **Review queue helper** (`/findcorrector`).
3. **Personal dashboard** (`/me`).

These three together form a coherent "your project life, on Discord"
narrative that:
- Solves problems the brief explicitly names.
- Demos visually well (DMs landing on schedule, slot-finder UI,
  embed dashboard).
- Stays inside one OAuth flow and one durable identity-link store.
- Re-uses the same five or six endpoints across all features, which
  keeps the rate-limit and caching design simple.

If the team has bandwidth for a fourth feature, **"Pool buddies on
campus"** (Community Activation) is the cheapest way to add a second
theme to the demo, since it shares the locations cache.
