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
from pathlib import Path

import discord
from discord import app_commands
from dotenv import load_dotenv

from .rag import QueryFailed, RagAnswer, build_rag, query, working_dir_path

# Discord message hard cap is 2000 chars. We trim with a tail "..." marker.
_DISCORD_MSG_CAP = 1900

logger = logging.getLogger("bot")

GREETING_RE = re.compile(
    r"^\s*(hi|hello|hey|yo|gm|gn|hola|salut|"
    r"こん(にちは|ばんは)|おはよう|やあ|よっ|おーい)"
    r"[\s!.?。！？]*\s*$",
    re.IGNORECASE,
)


def _is_greeting(text: str) -> bool:
    if not text:
        return False
    if len(text.strip()) <= 2:
        return True
    return bool(GREETING_RE.match(text))


def _greeting_reply(asker_name: str) -> str:
    return (
        f"こんにちは {asker_name}! 👋\n"
        "I can answer questions about 42 Tokyo rules, projects, peer reviews, "
        "campus, and more. Try `/ask` with something specific.\n\n"
        "**Examples:**\n"
        "• `/ask How does the Black Hole work?`\n"
        "• `/ask ピアレビューはどうやるの？`\n"
        "• `/ask 退学はどう申請しますか`"
    )


def _format_answer(ans: RagAnswer) -> str:
    """Plain-text reply: answer body, then a sources line."""
    body = ans.text.strip()
    parts = [body] if body else []
    if ans.sources:
        srcs = ", ".join(ans.sources[:8])
        parts.append(f"\n_Sources: {srcs}_")
    msg = "\n".join(parts) if parts else "No answer."
    if len(msg) > _DISCORD_MSG_CAP:
        msg = msg[:_DISCORD_MSG_CAP].rstrip() + "..."
    return msg


def _format_error(err: str) -> str:
    """Plain-text error reply. Friendlier than a stack trace."""
    return (
        "Sorry, I couldn't answer that just now — the language model is "
        "rate-limited or unreachable. Please try again in a few minutes, "
        "or ask a staff member directly.\n"
        f"_Detail: {err[:300]}_"
    )


class AskBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.guild_id = os.environ.get("DISCORD_GUILD_ID", "").strip()
        self.staff_channel_id = os.environ.get("STAFF_CHANNEL_ID", "").strip()
        self.rag: object | None = None  # LightRAG instance, set in setup_hook

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

    async def post_to_staff(self, question: str, asker: discord.abc.User) -> None:
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
            title="Question failed — needs staff input",
            description=question,
            color=discord.Color.orange(),
        )
        embed.add_field(name="Asked by", value=asker.mention, inline=False)
        try:
            await ch.send(embed=embed)
        except Exception:
            logger.exception("failed to post to staff")


def build_client() -> AskBot:
    client = AskBot()

    @client.tree.command(name="ask", description="Ask the 42 Tokyo rules bot")
    @app_commands.describe(question="What do you want to know?")
    async def ask(interaction: discord.Interaction, question: str) -> None:
        # Greetings + tiny inputs bypass RAG entirely
        if _is_greeting(question):
            await interaction.response.send_message(
                _greeting_reply(interaction.user.display_name)
            )
            return
        await interaction.response.defer(thinking=True)
        try:
            ans = await query(client.rag, question)
            await interaction.followup.send(_format_answer(ans))
        except QueryFailed as exc:
            logger.warning("query failed (LLM): %s", exc)
            await client.post_to_staff(question, interaction.user)
            await interaction.followup.send(_format_error(str(exc)))
        except Exception as exc:
            logger.exception("query failed (unexpected)")
            await client.post_to_staff(question, interaction.user)
            await interaction.followup.send(_format_error(str(exc)))

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
