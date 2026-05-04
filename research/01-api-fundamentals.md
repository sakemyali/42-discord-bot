# 01 — 42 API fundamentals

## App registration

Apps are created at <https://profile.intra.42.fr/oauth/applications>.

Required fields:

| Field | Notes |
|-------|-------|
| Name | Display name of the app |
| Redirect URI | One or more URIs where the OAuth server redirects after user authentication. Required for the Web Application Flow; can be left empty if only using Client Credentials. |
| Scopes | Set of permissions the app can request (see "Scopes" below). Default: `public`. |

After creation 42 issues:

- `UID` (a.k.a. `client_id`)
- `SECRET` (a.k.a. `client_secret`)

Treat the secret like a password — never commit it. Use environment
variables and a `.env.example` file in the repo.

## Base URL

```
https://api.intra.42.fr
```

API endpoints live under `/v2`, OAuth endpoints under `/oauth`.

| Endpoint | Purpose |
|----------|---------|
| `POST /oauth/token` | Exchange credentials for an access token |
| `GET /oauth/token/info` | Inspect a token (scopes, expiry, owner) |
| `GET /oauth/authorize` | Start the Web Application (Authorization Code) flow |
| `GET /v2/...` | All resource endpoints |

## OAuth2 flows

The 42 API supports two flows. Pick based on whether the data is
public-readable or tied to a specific user.

### A. Client Credentials Flow

Use when the bot reads public-ish data (e.g. campus events, public user
profiles, leaderboards).

```bash
curl -X POST https://api.intra.42.fr/oauth/token \
  -d grant_type=client_credentials \
  -d client_id=$UID \
  -d client_secret=$SECRET
```

Response:

```json
{
  "access_token": "abc...",
  "token_type": "bearer",
  "expires_in": 7200,
  "scope": "public",
  "created_at": 1443451918
}
```

- `expires_in` is 7200 seconds (2 hours).
- The bot should refresh the token a few minutes before expiry, not on
  every request.

Python sketch:

```python
import time, requests

class IntraToken:
    def __init__(self, uid, secret):
        self.uid, self.secret = uid, secret
        self._token, self._exp = None, 0

    def get(self):
        if self._token and time.time() < self._exp - 60:
            return self._token
        r = requests.post(
            "https://api.intra.42.fr/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.uid,
                "client_secret": self.secret,
            },
            timeout=10,
        )
        r.raise_for_status()
        d = r.json()
        self._token = d["access_token"]
        self._exp = time.time() + d["expires_in"]
        return self._token
```

### B. Web Application Flow (Authorization Code)

Use when a Discord user wants the bot to act on their personal 42
data (their own grade, schedule, slots, etc.) — i.e. account-link
flows.

1. Redirect the user to:
   ```
   https://api.intra.42.fr/oauth/authorize
     ?client_id=UID
     &redirect_uri=https://yourapp/callback
     &response_type=code
     &scope=public projects
     &state=<csrf token>
   ```
2. 42 redirects back to `redirect_uri?code=...&state=...`.
3. Exchange the code for a token:
   ```bash
   curl -X POST https://api.intra.42.fr/oauth/token \
     -d grant_type=authorization_code \
     -d client_id=$UID \
     -d client_secret=$SECRET \
     -d code=$CODE \
     -d redirect_uri=https://yourapp/callback
   ```
4. Persist the resulting `access_token` + `refresh_token` keyed by the
   Discord user ID. Use the refresh token to renew without prompting
   the user again.

For a Discord bot, the standard pattern is a small companion webserver
hosting `/login` and `/callback`, with a `/link` slash command that
DMs the user a one-time URL. After callback, store the linkage in a
database (Discord ID ↔ 42 login ↔ encrypted tokens).

## Scopes

The 42 API gates richer data behind scopes. Default access is `public`.
Known scopes referenced in community projects and documentation:

| Scope | Purpose |
|-------|---------|
| `public` | Default. Public profile data, projects, events. |
| `projects` | Project-specific endpoints, including some write ops on `projects_users`. |
| `profile` | Authenticated user's own profile details. |
| `elearning` | E-learning videos and progress. |
| `forum` | Read/write forum posts. |
| `tig` | Internal staff/TIG operations (rarely granted to community apps). |

Request only what you need. Adding more scopes is allowed later by
editing the app registration.

## Rate limits

Defaults per app (not per user):

- **2 requests per second**
- **1200 requests per hour**

This is the single hardest constraint when designing a multi-user Discord
bot. See [06-architecture.md](./06-architecture.md) for the math and
caching strategy.

42 staff can raise limits on request, but do not assume that.

## Headers required on every request

```
Authorization: Bearer <ACCESS_TOKEN>
```

Optional but useful:
- `Accept: application/json` (default anyway)
- `User-Agent: <yourbot>/<version>` — be a good citizen, makes API
  abuse traceable for 42 staff.

## Common gotchas

- Dates are ISO-8601 in UTC; convert in code, not in templates.
- `null` is used liberally — every "optional" field really can be
  missing.
- Some endpoints accept POST/PATCH but the app needs a relevant scope.
  Read-only is the safe default.
- The API can return 429 if you exceed the per-second limit before
  you exceed the per-hour limit. Treat both as backoff signals.
- The official docs at `api.intra.42.fr/apidoc` sometimes block
  scrapers; community references like the `leeoocca/awesome-42` list
  and `hivehelsinki/42api-lib` source are reliable mirrors of the
  important parts.
