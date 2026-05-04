# 02 — API specification (pagination, filters, sort, ranges, errors)

The 42 API follows a consistent set of conventions across all
collection endpoints. Learning these once removes 80% of the friction.

## Pagination

Every collection endpoint paginates.

| Param | Default | Max | Notes |
|-------|---------|-----|-------|
| `page` (or `page[number]`) | `1` | — | 1-indexed |
| `per_page` (or `page[size]`) | `30` | `100` | Always set explicitly to reduce request count |

Response headers:

| Header | Meaning |
|--------|---------|
| `X-Page` | Current page number |
| `X-Per-Page` | Items per page |
| `X-Total` | Total number of items across all pages (use this to compute total page count) |

Both `?page=2&per_page=100` and `?page[number]=2&page[size]=100` are
accepted. The shorter form is preferred in code samples.

To fetch a full collection efficiently:

```python
items = []
page = 1
while True:
    r = ic.get("/v2/cursus/21/users",
               params={"page": page, "per_page": 100})
    batch = r.json()
    if not batch:
        break
    items.extend(batch)
    if len(batch) < 100:   # last page
        break
    page += 1
```

## Filtering

```
GET /v2/users?filter[pool_year]=2024
GET /v2/users?filter[pool_year]=2024&filter[pool_month]=september,july
```

- Multiple values per field: comma-separated.
- Multiple fields: combine in the same query string.
- Field names match the canonical resource attribute names.

Common filters worth knowing:

| Resource | Filter | Example |
|----------|--------|---------|
| users | `pool_year`, `pool_month`, `staff?`, `kind` | `filter[staff?]=false` |
| cursus_users | `cursus_id`, `campus_id`, `user_id`, `grade` | `filter[cursus_id]=21` |
| projects_users | `project_id`, `cursus`, `marked`, `status` | `filter[status]=in_progress` |
| locations | `active`, `campus_id`, `user_id` | `filter[active]=true` |
| events | `future`, `campus_id`, `cursus_id` | `filter[future]=true` |
| scale_teams | `filled` | `filter[filled]=true` |

## Sorting

```
GET /v2/users?sort=-login          # descending
GET /v2/users?sort=kind,-login     # multi-key
```

Prefix with `-` for descending. Comma-separate for tiebreakers.

## Range queries

For endpoints that accept time-bounded queries (locations, projects,
scale_teams, events):

```
GET /v2/users/{login}/locations?range[begin_at]=2026-05-01T00:00:00Z,2026-05-04T00:00:00Z
```

Format: `range[field]=<start>,<end>` — both inclusive.

## Combining everything

```
GET /v2/campus/26/users
  ?filter[pool_year]=2024
  &filter[staff?]=false
  &range[updated_at]=2026-04-01T00:00:00Z,2026-05-01T00:00:00Z
  &sort=-correction_point
  &page=1
  &per_page=100
```

(`campus_id=26` is 42Tokyo. Confirm at runtime by `GET /v2/campus`.)

## Error codes

| HTTP | Meaning | What the bot should do |
|------|---------|------------------------|
| 200 | OK | — |
| 401 | Token invalid / expired | Refresh token and retry once |
| 403 | Scope insufficient or resource forbidden | Don't retry; surface a configuration error |
| 404 | Resource not found | Don't retry; cache the negative result short-term |
| 422 | Validation failed (write ops) | Surface the response body to the user |
| 429 | Rate limited | Backoff; honor `Retry-After` if present |
| 5xx | Server error | Exponential backoff with jitter, max ~3 retries |

## Recommended request wrapper

A thin wrapper that handles these cross-cutting concerns is worth
~50 lines of code and saves debugging:

- token refresh on 401
- automatic per-second throttle (token bucket)
- automatic backoff on 429 / 5xx
- pagination iterator
- request/response logging

Reference implementations to copy or learn from:

- `hivehelsinki/42api-lib` (Python) — `IntraAPIClient.get()`,
  `.pages()`, `.pages_threaded()`.
- `42Charts/42-api-aggregator` (Node.js) — production-grade aggregator.
- `RP42/pkg/api/` (Go) — concise location-fetching patterns.

## Response shape

Single resource:

```json
{ "id": 12345, "login": "abc", "...": "..." }
```

Collection:

```json
[ {...}, {...}, {...} ]
```

42 returns plain arrays (not envelopes). All metadata lives in headers.
