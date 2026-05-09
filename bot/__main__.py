"""Discord bot entry point.

Runs an asyncio Discord client that, on /ask, queries LightRAG and replies
with the answer plus source filenames. Falls through to a friendly fallback
on any error so users never see a stack trace.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import discord
from discord import app_commands
from dotenv import load_dotenv

from .rag import QueryFailed, RagAnswer, build_rag, query, working_dir_path

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


def _format_error(err: str) -> str:
    """Plain-text error reply. Friendlier than a stack trace."""
    return (
        "I can't reach the language model right now. "
        "Try again in a few minutes, or ping a staff member directly.\n"
        f"_Detail: {err[:300]}_"
    )


class AskBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.guild_id = os.environ.get("DISCORD_GUILD_ID", "").strip()
        self.staff_channel_id = os.environ.get("STAFF_CHANNEL_ID", "").strip()
        self.admin_role_id = os.environ.get("ADMIN_ROLE_ID", "").strip()
        self.log_channel_id = os.environ.get("BOT_LOG_CHANNEL_ID", "").strip()
        self.rag: object | None = None  # LightRAG instance, set in setup_hook
        self.query_counts: dict[int, int] = {}  # user_id -> queries this session

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
    ) -> None:
        if not self.staff_channel_id:
            return
        try:
            ch = self.get_channel(int(self.staff_channel_id)) or await self.fetch_channel(
                int(self.staff_channel_id)
            )
        except Exception:
            logger.exception("could not fetch staff channel")
            return
        embed = discord.Embed(
            title=reason,
            description=question,
            color=discord.Color.orange(),
        )
        embed.add_field(name="Asked by", value=asker.mention, inline=False)
        mention = f"<@&{self.admin_role_id}>" if self.admin_role_id else ""
        try:
            await ch.send(
                content=mention or None,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(roles=True, users=True),
            )
        except Exception:
            logger.exception("failed to post to staff")


def build_client() -> AskBot:
    client = AskBot()

    @client.tree.command(name="ask", description="Ask the 42 Tokyo rules bot")
    @app_commands.describe(question="What do you want to know?")
    async def ask(interaction: discord.Interaction, question: str) -> None:
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
        try:
            ans = await query(client.rag, question)
            elapsed = time.monotonic() - start
            cached = elapsed < 1.0  # LLM calls take ≥2s; cache hits are sub-second
            if "[NO_CORPUS_ANSWER]" in ans.text:
                logger.info("escalating to staff (no answer in corpus): %s", question)
                await client.post_to_staff(
                    question, interaction.user,
                    reason="Outside corpus, needs human answer",
                )
                await interaction.followup.send(_escalation_reply(question))
                await client.post_log(
                    title="🟠 Escalated, outside corpus",
                    color=discord.Color.orange(),
                    fields=[
                        ("Asked by", f"{interaction.user.mention} (use #{count})"),
                        ("Question", question),
                        ("Time", f"{elapsed:.2f}s"),
                        ("Cached", "yes" if cached else "no"),
                    ],
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
