"""42 intra API client.

Thin async wrapper around the bits of the 42 API the bot needs:

  GET /v2/users/:login/locations?filter[active]=true&page[size]=1

returns the iMac the student is currently sitting at, if any. We use the
client_credentials OAuth flow — app-level token, no per-user consent — so
the bot can look up any login.

Token cache is in-memory; tokens last 7200s and we refresh ~60s early.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass

import aiohttp

OAUTH_TOKEN_URL = "https://api.intra.42.fr/oauth/token"
API_BASE = "https://api.intra.42.fr/v2"


class FortyTwoError(RuntimeError):
    """Anything wrong talking to the 42 API."""


class FortyTwoUnknownLogin(FortyTwoError):
    """The login doesn't exist on intra (404)."""


@dataclass
class ActiveLocation:
    """A student's current iMac session, parsed."""

    login: str
    host: str  # raw hostname, e.g. "c1r4p5"
    campus_id: int
    begin_at: str  # ISO-8601 from the API
    cluster: int | None  # parsed from host, None if format unknown
    row: int | None
    seat: int | None
    floor: str | None  # best-effort: first letter+digit chunk if it looks floor-ish


# Matches three integer triples after optional letter prefixes:
#   c1r4p5, e1r10p15, 1r4p5, 1-r4-p5, c1_r4_p5, etc.
_HOST_RE = re.compile(
    r"^(?P<a_letters>[a-zA-Z]*)(?P<a>\d+)[\-_]?"
    r"(?P<b_letters>[a-zA-Z]+)(?P<b>\d+)[\-_]?"
    r"(?P<c_letters>[a-zA-Z]+)(?P<c>\d+)$"
)


def parse_host(host: str) -> tuple[int | None, int | None, int | None, str | None]:
    """Parse `c1r4p5`-style hostnames into (cluster, row, seat, floor).

    Returns (None, None, None, None) when the format isn't recognized — the
    caller should still display the raw host so the student can read it.

    Floor heuristic: if the first label is `e` (étage) we take the first
    integer as a floor number (e.g. `e1r4p5` → floor "1F"). Otherwise None.
    """
    m = _HOST_RE.match(host or "")
    if not m:
        return None, None, None, None
    cluster = int(m.group("a"))
    row = int(m.group("b"))
    seat = int(m.group("c"))
    floor = None
    a_letters = m.group("a_letters").lower()
    if a_letters in {"e", "f"}:
        floor = f"{cluster}F"
    return cluster, row, seat, floor


class FortyTwoClient:
    """Async client for the 42 API. One instance per bot, reused.

    Owns its own aiohttp session lazily. Caller must `await close()` on shutdown
    if it cares — for a Discord bot that runs until killed, leaking the session
    is fine.
    """

    def __init__(self, uid: str, secret: str, campus_id: int | None = None) -> None:
        if not uid or not secret:
            raise FortyTwoError("FORTYTWO_UID and FORTYTWO_SECRET must be set")
        self.uid = uid
        self.secret = secret
        self.campus_id = campus_id
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        self._token_lock = asyncio.Lock()
        self._session: aiohttp.ClientSession | None = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def _ensure_token(self) -> str:
        async with self._token_lock:
            now = time.time()
            if self._token and now < self._token_expires_at - 60:
                return self._token
            session = await self._ensure_session()
            async with session.post(
                OAUTH_TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.uid,
                    "client_secret": self.secret,
                },
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise FortyTwoError(
                        f"OAuth token request failed ({resp.status}): {body[:200]}"
                    )
                data = await resp.json()
            self._token = data["access_token"]
            # API returns expires_in in seconds (typically 7200).
            self._token_expires_at = now + float(data.get("expires_in", 7200))
            return self._token

    async def get_active_location(self, login: str) -> ActiveLocation | None:
        """Return the user's current active iMac session, or None if not logged in.

        Raises FortyTwoUnknownLogin when the API 404s on the login.
        """
        token = await self._ensure_token()
        session = await self._ensure_session()
        url = f"{API_BASE}/users/{login}/locations"
        params = {"filter[active]": "true", "page[size]": "1"}
        async with session.get(
            url,
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status == 404:
                raise FortyTwoUnknownLogin(f"unknown 42 login: {login}")
            if resp.status != 200:
                body = await resp.text()
                raise FortyTwoError(
                    f"locations request failed ({resp.status}): {body[:200]}"
                )
            data = await resp.json()
        if not data:
            return None
        loc = data[0]
        host = loc.get("host") or ""
        cluster, row, seat, floor = parse_host(host)
        return ActiveLocation(
            login=login,
            host=host,
            campus_id=int(loc.get("campus_id", 0)),
            begin_at=loc.get("begin_at", ""),
            cluster=cluster,
            row=row,
            seat=seat,
            floor=floor,
        )
