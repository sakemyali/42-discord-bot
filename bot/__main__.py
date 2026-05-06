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

from .rag import RagAnswer, build_rag, query, working_dir_path

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


def _build_answer_embed(question: str, ans: RagAnswer) -> discord.Embed:
    body = ans.text
    # Discord embed body cap is 4096; keep some headroom for refs section
    if len(body) > 3500:
        body = body[:3500].rstrip() + "..."
    embed = discord.Embed(
        title="Answer",
        description=body,
        color=discord.Color.green(),
    )
    embed.add_field(name="Question", value=question[:1024], inline=False)
    if ans.sources:
        sources = ", ".join(ans.sources[:8])
        if len(sources) > 1024:
            sources = sources[:1021] + "..."
        embed.add_field(name="Sources", value=sources, inline=False)
    embed.set_footer(text=f"mode: {ans.mode}")
    return embed


def _build_error_embed(question: str, err: str) -> discord.Embed:
    embed = discord.Embed(
        title="Could not answer",
        description="Something went wrong on our side. The staff have been notified.",
        color=discord.Color.red(),
    )
    embed.add_field(name="Question", value=question[:1024], inline=False)
    embed.add_field(name="Error", value=f"```{err[:500]}```", inline=False)
    return embed


def _build_greeting_embed(asker_name: str) -> discord.Embed:
    return discord.Embed(
        title="Hi!",
        description=_greeting_reply(asker_name),
        color=discord.Color.blurple(),
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
                embed=_build_greeting_embed(interaction.user.display_name)
            )
            return
        await interaction.response.defer(thinking=True)
        try:
            ans = await query(client.rag, question)
            await interaction.followup.send(embed=_build_answer_embed(question, ans))
        except Exception as exc:
            logger.exception("query failed")
            await client.post_to_staff(question, interaction.user)
            await interaction.followup.send(
                embed=_build_error_embed(question, str(exc))
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
