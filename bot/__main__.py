"""Discord bot entry point.

Runs an asyncio Discord client that, on /ask, queries LightRAG and replies
with the answer plus source filenames. Falls through to a friendly fallback
on any error so users never see a stack trace.
"""

from __future__ import annotations

import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from dotenv import load_dotenv

from .forty_two import (
    ActiveLocation,
    FortyTwoClient,
    FortyTwoError,
    FortyTwoUnknownLogin,
)
from .rag import QueryFailed, RagAnswer, build_rag, default_corpus_path, insert_documents, query, working_dir_path

if TYPE_CHECKING:
    from lightrag import LightRAG

# Discord message hard cap is 2000 chars. We trim with a tail "..." marker.
_DISCORD_MSG_CAP = 1900

logger = logging.getLogger("bot")

GREETING_EN_RE = re.compile(
    r"^\s*(hi|hello|hey|yo|gm|gn|hola|salut)[\s!.?]*\s*$",
    re.IGNORECASE,
)
GREETING_JA_RE = re.compile(
    r"^\s*(こん(にちは|ばんは)|おはよう(ございます)?|やあ|よっ|おーい|お疲れ様?(です)?)"
    r"[\s!.?。！？〜ー]*\s*$"
)
_JA_CHAR_RE = re.compile(r"[ぁ-んァ-ヴ一-龯]")


def _is_greeting(text: str) -> str | None:
    """Return 'ja' or 'en' if the message is a greeting, else None."""
    if not text:
        return None
    stripped = text.strip()
    if GREETING_JA_RE.match(stripped):
        return "ja"
    if GREETING_EN_RE.match(stripped):
        return "en"
    if len(stripped) <= 2:
        return "ja" if _JA_CHAR_RE.search(stripped) else "en"
    return None


def _greeting_reply(asker_name: str, lang: str) -> str:
    if lang == "ja":
        return (
            f"こんにちは、{asker_name}さん！👋\n"
            "42 Tokyoの校舎・課題・ピアレビュー・BlackHole などについて答えられます。"
            "`/ask` で気になることを聞いてみてください。\n\n"
            "**例:**\n"
            "• `/ask BlackHole の仕組みは？`\n"
            "• `/ask ピアレビューはどうやるの？`\n"
            "• `/ask 退学はどう申請しますか？`"
        )
    return (
        f"Hey {asker_name}! 👋\n"
        "Ask me anything about 42 Tokyo. Rules, projects, peer reviews, "
        "campus stuff, all of it. Use `/ask` with whatever you want to know.\n\n"
        "**Try:**\n"
        "• `/ask How does the Black Hole work?`\n"
        "• `/ask How do peer reviews work?`\n"
        "• `/ask How do I withdraw from 42 Tokyo?`"
    )


def _escalation_reply(question: str) -> str:
    if _JA_CHAR_RE.search(question):
        return (
            "申し訳ありません、その質問にはお答えできませんでしたので、"
            "スタッフに引き継ぎました。担当者からできるだけ早くお返事します。"
        )
    return (
        "I can't answer that one. I've passed it to staff and someone "
        "will get back to you as soon as they can."
    )


def _format_answer(ans: RagAnswer) -> str:
    """Plain-text reply: answer body only, like a staff DM."""
    body = ans.text.strip()
    msg = body if body else "No answer."
    if len(msg) > _DISCORD_MSG_CAP:
        msg = msg[:_DISCORD_MSG_CAP].rstrip() + "..."
    return msg


def _build_location_embed(login: str, loc: ActiveLocation) -> discord.Embed:
    """Bilingual EN/JA card for /search. Uses Discord's <t:UNIX:R> for live duration."""
    embed = discord.Embed(
        title=f"📍 {login}",
        color=discord.Color.blurple(),
    )
    if loc.cluster is not None:
        embed.add_field(
            name="🏢 Cluster / クラスター",
            value=f"**{loc.cluster}**",
            inline=True,
        )
        if loc.floor:
            embed.add_field(
                name="📐 Floor / 階",
                value=f"**{loc.floor}**",
                inline=True,
            )
        embed.add_field(
            name="⌨️ Row · Seat / 列・席",
            value=f"**R{loc.row} · P{loc.seat}**",
            inline=True,
        )
    else:
        embed.add_field(
            name="🖥️ Host / ホスト名",
            value=f"`{loc.host or '—'}`",
            inline=False,
        )

    duration_value = "—"
    if loc.begin_at:
        try:
            dt = datetime.fromisoformat(loc.begin_at.replace("Z", "+00:00"))
            unix = int(dt.timestamp())
            duration_value = f"<t:{unix}:R> · <t:{unix}:t>"
        except ValueError:
            duration_value = loc.begin_at
    embed.add_field(
        name="⏱️ Logged in / ログイン中",
        value=duration_value,
        inline=False,
    )
    embed.set_footer(text=f"host: {loc.host}" if loc.host else "")
    return embed


def _format_error(err: str) -> str:
    """Plain-text error reply. Friendlier than a stack trace."""
    return (
        "I can't reach the language model right now. "
        "Try again in a few minutes, or ping a staff member directly.\n"
        f"_Detail: {err[:300]}_"
    )


@dataclass
class EscalationContext:
    """One in-flight `[NO_CORPUS_ANSWER]` escalation awaiting a staff answer."""

    staff_thread_id: int
    student_thread_id: int
    asker_id: int
    channel_id: int
    question: str
    created_at: datetime


class AskBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        # Required to read `reaction.message.content` so we can ingest staff
        # answers back into LightRAG. Must also be toggled on in the Discord
        # Developer Portal → Bot tab → "Message Content Intent".
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.guild_id = os.environ.get("DISCORD_GUILD_ID", "").strip()
        self.staff_channel_id = os.environ.get("STAFF_CHANNEL_ID", "").strip()
        self.admin_role_id = os.environ.get("ADMIN_ROLE_ID", "").strip()
        self.log_channel_id = os.environ.get("BOT_LOG_CHANNEL_ID", "").strip()
        # Comma-separated channel IDs where /ask is allowed. Empty = unrestricted.
        # Authoritative restriction is per-channel slash-command visibility in
        # Server Settings → Integrations; this is a fallback guard.
        raw_ask_channels = os.environ.get("ASK_CHANNEL_IDS", "").strip()
        self.allowed_channel_ids: set[int] = {
            int(x) for x in (p.strip() for p in raw_ask_channels.split(",")) if x.isdigit()
        }
        self.rag: "LightRAG | None" = None  # set in setup_hook
        self.query_counts: dict[int, int] = {}  # user_id -> queries this session
        # Keyed by staff_thread_id. In-memory only — restart drops in-flight escalations.
        self.pending_escalations: dict[int, EscalationContext] = {}
        # 42 API client for /search. Built lazily so the bot still boots if creds
        # aren't configured — /search will then return a friendly "not configured".
        self.forty_two: FortyTwoClient | None = None
        ft_uid = os.environ.get("FORTYTWO_UID", "").strip()
        ft_secret = os.environ.get("FORTYTWO_SECRET", "").strip()
        if ft_uid and ft_secret:
            try:
                self.forty_two = FortyTwoClient(uid=ft_uid, secret=ft_secret)
            except FortyTwoError:
                logger.exception("FortyTwoClient init failed; /search disabled")

    async def setup_hook(self) -> None:
        wd = working_dir_path()
        if not wd.exists() or not any(wd.iterdir()):
            print(
                f"LightRAG storage at {wd} is empty.\n"
                "Run `make ingest` (or `python -m bot.ingest`) first.",
                file=sys.stderr,
            )
            sys.exit(1)
        logger.info("loading LightRAG storage from %s", wd)
        self.rag = await build_rag()
        if self.guild_id:
            guild = discord.Object(id=int(self.guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info("synced commands to guild %s", self.guild_id)
        else:
            await self.tree.sync()
            logger.info("synced commands globally (may take up to 1h)")

    async def on_ready(self) -> None:
        logger.info("bot ready as %s", self.user)
        await self.post_log(
            title="🟢 Bot online",
            color=discord.Color.green(),
            fields=[("Logged in as", str(self.user))],
        )

    async def post_log(
        self,
        title: str,
        color: discord.Color,
        fields: list[tuple[str, str]],
        ping_admin: bool = False,
    ) -> None:
        if not self.log_channel_id:
            return
        try:
            ch = self.get_channel(int(self.log_channel_id)) or await self.fetch_channel(
                int(self.log_channel_id)
            )
        except Exception:
            logger.exception("could not fetch log channel")
            return
        embed = discord.Embed(
            title=title,
            color=color,
            timestamp=datetime.now(timezone.utc),
        )
        for name, value in fields:
            if not value:
                continue
            # Discord field value cap is 1024 chars
            embed.add_field(name=name, value=value[:1020] + ("…" if len(value) > 1020 else ""), inline=False)
        mention = (
            f"<@&{self.admin_role_id}>"
            if ping_admin and self.admin_role_id
            else None
        )
        try:
            await ch.send(
                content=mention,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(roles=True),
            )
        except Exception:
            logger.exception("failed to post to log channel")

    async def post_to_staff(
        self,
        question: str,
        asker: discord.abc.User,
        reason: str = "Question failed, needs staff input",
    ) -> discord.Message | None:
        if not self.staff_channel_id:
            return None
        try:
            ch = self.get_channel(int(self.staff_channel_id)) or await self.fetch_channel(
                int(self.staff_channel_id)
            )
        except Exception:
            logger.exception("could not fetch staff channel")
            return None
        embed = discord.Embed(
            title=reason,
            description=question,
            color=discord.Color.orange(),
        )
        embed.add_field(name="Asked by", value=asker.mention, inline=False)
        mention = f"<@&{self.admin_role_id}>" if self.admin_role_id else ""
        try:
            return await ch.send(
                content=mention or None,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(roles=True, users=True),
            )
        except Exception:
            logger.exception("failed to post to staff")
            return None

    async def on_raw_reaction_add(
        self, payload: discord.RawReactionActionEvent
    ) -> None:
        """Resolve a staff escalation when an admin reacts ✅ in the staff thread.

        Uses the *raw* reaction event (not on_reaction_add) so we don't depend on
        the bot having the reacted-to message in its in-memory cache — admin
        replies in a freshly created thread aren't always cached.
        """
        if self.user is not None and payload.user_id == self.user.id:
            return
        if str(payload.emoji) != "✅":
            return
        ctx = self.pending_escalations.get(payload.channel_id)
        if ctx is None:
            return
        member = payload.member  # populated for guild reactions
        if member is None or member.bot:
            return
        if not self.admin_role_id:
            logger.info("✅ reaction in staff thread but ADMIN_ROLE_ID not set; ignoring")
            return
        try:
            admin_role_id = int(self.admin_role_id)
        except ValueError:
            return
        if not any(r.id == admin_role_id for r in member.roles):
            logger.info(
                "✅ reaction by %s but they lack admin role %s; ignoring",
                member, self.admin_role_id,
            )
            return
        # Fetch the reacted-to message; it may not be in the bot's cache.
        try:
            channel = self.get_channel(payload.channel_id) or await self.fetch_channel(
                payload.channel_id
            )
            if not isinstance(channel, (discord.TextChannel, discord.Thread)):
                logger.warning("escalation channel %s is not text-capable", payload.channel_id)
                return
            answer_msg = await channel.fetch_message(payload.message_id)
        except Exception:
            logger.exception("could not fetch reacted message for resolution")
            return
        # Pop before resolving so a second admin reacting is a no-op.
        self.pending_escalations.pop(ctx.staff_thread_id, None)
        await self._resolve_escalation(ctx, answer_msg, member)

    async def _resolve_escalation(
        self,
        ctx: EscalationContext,
        answer_msg: discord.Message,
        admin: discord.Member,
    ) -> None:
        """Forward staff answer to student, ingest into corpus + LightRAG, archive thread."""
        answer_text = (answer_msg.content or "").strip()
        is_ja = bool(_JA_CHAR_RE.search(ctx.question))
        prefix = "担当者からの回答です:" if is_ja else "Answer from staff:"

        # 1. Forward to student thread — highest priority.
        try:
            thread = self.get_channel(ctx.student_thread_id) or await self.fetch_channel(
                ctx.student_thread_id
            )
            if isinstance(thread, (discord.Thread, discord.TextChannel)):
                await thread.send(
                    f"<@{ctx.asker_id}> {prefix}\n\n{answer_text}",
                    allowed_mentions=discord.AllowedMentions(users=True),
                )
            else:
                logger.warning("student thread %s is not text-capable", ctx.student_thread_id)
        except Exception:
            logger.exception("failed to forward staff answer to student thread")

        # 2. Persist to corpus on disk + ingest into running LightRAG. Best-effort.
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        slug = f"discord-qa/{today}-staff-answer-{ctx.staff_thread_id}.md"
        md = (
            f"# {ctx.question[:80]}\n\n"
            f"**Source**: 42 Tokyo Discord, {today}\n"
            f"**Tags**: staff-answer, escalation\n\n"
            f"## Q\n\n{ctx.question}\n\n"
            f"## A\n\n(@{admin.name}, staff): {answer_text}\n"
        )
        ingest_status = "ok"
        try:
            disk_path = default_corpus_path() / slug
            disk_path.parent.mkdir(parents=True, exist_ok=True)
            disk_path.write_text(md, encoding="utf-8")
        except Exception as exc:
            logger.exception("failed to write staff answer to corpus on disk")
            ingest_status = f"disk write failed: {type(exc).__name__}"
        try:
            if self.rag is not None:
                await insert_documents(self.rag, [(slug, md)])
        except Exception as exc:
            logger.exception("failed to ingest staff answer into LightRAG")
            # Disk write may have succeeded — preserve that signal.
            ingest_status = (
                f"ingest failed: {type(exc).__name__}"
                if ingest_status == "ok"
                else f"{ingest_status}; ingest failed: {type(exc).__name__}"
            )

        # 3. Archive + lock the staff thread.
        try:
            if isinstance(answer_msg.channel, discord.Thread):
                await answer_msg.channel.edit(archived=True, locked=True)
        except Exception:
            logger.exception("failed to archive staff thread")

        # 4. Log the resolution.
        await self.post_log(
            title="🟢 Resolved",
            color=discord.Color.green(),
            fields=[
                ("Asked by", f"<@{ctx.asker_id}>"),
                ("Question", ctx.question),
                ("Answer", answer_text),
                ("Resolved by", admin.mention),
                ("Ingest", ingest_status),
            ],
        )


def build_client() -> AskBot:
    client = AskBot()

    @client.tree.command(name="ask", description="Ask the 42 Tokyo rules bot")
    @app_commands.describe(question="What do you want to know?")
    async def ask(interaction: discord.Interaction, question: str) -> None:
        if (
            client.allowed_channel_ids
            and interaction.channel_id not in client.allowed_channel_ids
        ):
            first = next(iter(client.allowed_channel_ids))
            await interaction.response.send_message(
                f"Please use this in <#{first}>.", ephemeral=True,
            )
            return
        client.query_counts[interaction.user.id] = (
            client.query_counts.get(interaction.user.id, 0) + 1
        )
        count = client.query_counts[interaction.user.id]
        # Greetings + tiny inputs bypass RAG entirely
        greeting_lang = _is_greeting(question)
        if greeting_lang:
            await interaction.response.send_message(
                _greeting_reply(interaction.user.display_name, greeting_lang)
            )
            await client.post_log(
                title="👋 Greeting",
                color=discord.Color.blurple(),
                fields=[
                    ("Asked by", f"{interaction.user.mention} (use #{count})"),
                    ("Input", question),
                    ("Lang", greeting_lang),
                ],
            )
            return
        await interaction.response.defer(thinking=True)
        start = time.monotonic()
        if client.rag is None:
            await interaction.followup.send(_format_error("RAG not initialized"))
            return
        try:
            ans = await query(client.rag, question)
            elapsed = time.monotonic() - start
            cached = elapsed < 1.0  # LLM calls take ≥2s; cache hits are sub-second
            if "[NO_CORPUS_ANSWER]" in ans.text:
                logger.info("escalating to staff (no answer in corpus): %s", question)
                staff_msg = await client.post_to_staff(
                    question, interaction.user,
                    reason="Outside corpus, needs human answer",
                )
                staff_thread: discord.Thread | None = None
                if staff_msg is not None:
                    try:
                        staff_thread = await staff_msg.create_thread(
                            name=f"Q: {question[:60]}",
                            auto_archive_duration=1440,
                        )
                    except Exception:
                        logger.exception("failed to create staff thread")

                student_msg = await interaction.followup.send(
                    _escalation_reply(question), wait=True,
                )
                student_thread: discord.Thread | None = None
                try:
                    # interaction.followup.send returns a WebhookMessage with
                    # no guild attached, and Message.create_thread requires a
                    # guild. Refetch via the channel to get a proper Message.
                    channel = interaction.channel
                    if isinstance(channel, (discord.TextChannel, discord.Thread)):
                        proper_student_msg = await channel.fetch_message(student_msg.id)
                        student_thread = await proper_student_msg.create_thread(
                            name=f"Q from {interaction.user.display_name}",
                            auto_archive_duration=1440,
                        )
                    else:
                        logger.warning(
                            "can't create student thread: channel %s is not text-capable",
                            type(channel).__name__,
                        )
                except Exception:
                    logger.exception("failed to create student thread")

                if staff_thread is not None and student_thread is not None:
                    client.pending_escalations[staff_thread.id] = EscalationContext(
                        staff_thread_id=staff_thread.id,
                        student_thread_id=student_thread.id,
                        asker_id=interaction.user.id,
                        channel_id=interaction.channel_id or 0,
                        question=question,
                        created_at=datetime.now(timezone.utc),
                    )

                fields = [
                    ("Asked by", f"{interaction.user.mention} (use #{count})"),
                    ("Question", question),
                    ("Time", f"{elapsed:.2f}s"),
                    ("Cached", "yes" if cached else "no"),
                ]
                if staff_thread is not None:
                    fields.append(("Staff thread", staff_thread.mention))
                await client.post_log(
                    title="🟠 Escalated, outside corpus",
                    color=discord.Color.orange(),
                    fields=fields,
                )
                return
            await interaction.followup.send(_format_answer(ans))
            await client.post_log(
                title="💬 Answered",
                color=discord.Color.blue(),
                fields=[
                    ("Asked by", f"{interaction.user.mention} (use #{count})"),
                    ("Question", question),
                    ("Answer", ans.text),
                    ("Sources", ", ".join(ans.sources[:8]) if ans.sources else "none"),
                    ("Time", f"{elapsed:.2f}s"),
                    ("Cached", "yes" if cached else "no"),
                    ("Mode", ans.mode),
                ],
            )
        except QueryFailed as exc:
            elapsed = time.monotonic() - start
            logger.warning("query failed (LLM): %s", exc)
            await client.post_to_staff(question, interaction.user)
            await interaction.followup.send(_format_error(str(exc)))
            await client.post_log(
                title="🔴 LLM error",
                color=discord.Color.red(),
                fields=[
                    ("Asked by", f"{interaction.user.mention} (use #{count})"),
                    ("Question", question),
                    ("Error", str(exc)),
                    ("Time", f"{elapsed:.2f}s"),
                ],
                ping_admin=True,
            )
        except Exception as exc:
            elapsed = time.monotonic() - start
            logger.exception("query failed (unexpected)")
            await client.post_to_staff(question, interaction.user)
            await interaction.followup.send(_format_error(str(exc)))
            await client.post_log(
                title="🔴 Unexpected error",
                color=discord.Color.red(),
                fields=[
                    ("Asked by", f"{interaction.user.mention} (use #{count})"),
                    ("Question", question),
                    ("Error", str(exc)),
                    ("Time", f"{elapsed:.2f}s"),
                ],
                ping_admin=True,
            )

    @client.tree.command(
        name="search",
        description="Find a 42 student's current iMac (cluster, row, seat).",
    )
    @app_commands.describe(login="42 intra login, e.g. emoulaya")
    async def search(interaction: discord.Interaction, login: str) -> None:
        if (
            client.allowed_channel_ids
            and interaction.channel_id not in client.allowed_channel_ids
        ):
            first = next(iter(client.allowed_channel_ids))
            await interaction.response.send_message(
                f"Please use this in <#{first}>.", ephemeral=True,
            )
            return
        login = login.strip().lstrip("@")
        if not login:
            await interaction.response.send_message(
                "Please provide a 42 login.", ephemeral=True,
            )
            return
        if client.forty_two is None:
            await interaction.response.send_message(
                "42 API isn't configured on this bot. Set `FORTYTWO_UID` "
                "and `FORTYTWO_SECRET` in `.env` and restart.",
                ephemeral=True,
            )
            return
        await interaction.response.defer(thinking=True)
        try:
            loc = await client.forty_two.get_active_location(login)
        except FortyTwoUnknownLogin:
            await interaction.followup.send(
                f"No 42 user `{login}`.", ephemeral=True,
            )
            return
        except FortyTwoError as exc:
            logger.warning("42 API call failed for %s: %s", login, exc)
            await interaction.followup.send(
                "Couldn't reach the 42 API right now. Try again in a minute.",
                ephemeral=True,
            )
            return
        if loc is None:
            await interaction.followup.send(
                f"`{login}` isn't logged in at any iMac right now.",
            )
            return

        embed = _build_location_embed(login, loc)
        await interaction.followup.send(embed=embed)

        await client.post_log(
            title="🔎 Searched location",
            color=discord.Color.blurple(),
            fields=[
                ("Searched by", interaction.user.mention),
                ("Login", login),
                ("Host", loc.host or "—"),
            ],
        )

    return client


def main() -> int:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    token = os.environ.get("DISCORD_TOKEN", "").strip()
    if not token:
        print(
            "DISCORD_TOKEN is not set. Copy .env.example to .env and fill it in.",
            file=sys.stderr,
        )
        return 1
    client = build_client()
    client.run(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
