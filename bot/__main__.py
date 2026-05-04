from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import discord
from discord import app_commands
from dotenv import load_dotenv

from .llm import LLMReply, answer
from .rag import Hit, Index, default_index_path

logger = logging.getLogger("bot")


def _load_index() -> Index:
    path = default_index_path()
    if not path.exists():
        print(
            f"Index not found at {path}.\n"
            "Run `make ingest` (or `python -m bot.ingest`) first.",
            file=sys.stderr,
        )
        sys.exit(1)
    return Index.load(path)


def _format_sources(hits: list[Hit]) -> str:
    seen: list[str] = []
    for h in hits:
        s = h.chunk.short_source()
        if s not in seen:
            seen.append(s)
    return ", ".join(seen) if seen else "—"


def _build_embed(
    question: str, reply: LLMReply, hits: list[Hit], escalated: bool
) -> discord.Embed:
    color = (
        discord.Color.orange() if escalated else discord.Color.green()
    )
    title = (
        "Could not answer with confidence"
        if escalated
        else ("Answer" if reply.used_llm else "Top matches")
    )
    embed = discord.Embed(title=title, description=reply.text, color=color)
    embed.add_field(name="Question", value=question[:1024], inline=False)
    embed.add_field(
        name="Sources",
        value=_format_sources(hits) if hits else "—",
        inline=False,
    )
    if hits:
        scores = ", ".join(f"{h.score:.2f}" for h in hits[:3])
        embed.set_footer(text=f"top scores: {scores}")
    return embed


class AskBot(discord.Client):
    def __init__(self, index: Index):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.index = index
        self.guild_id = os.environ.get("DISCORD_GUILD_ID", "").strip()
        self.staff_channel_id = os.environ.get("STAFF_CHANNEL_ID", "").strip()
        self.min_sim = float(os.environ.get("MIN_SIMILARITY", "0.35"))

    async def setup_hook(self) -> None:
        if self.guild_id:
            guild = discord.Object(id=int(self.guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info("synced commands to guild %s", self.guild_id)
        else:
            await self.tree.sync()
            logger.info("synced commands globally (may take up to 1h)")

    async def _post_escalation(
        self, question: str, asker: discord.abc.User, hits: list[Hit]
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
        snippets = ""
        for h in hits[:3]:
            txt = h.chunk.text.strip().replace("\n\n", "\n")
            if len(txt) > 400:
                txt = txt[:400] + "..."
            snippets += f"\n**{h.chunk.short_source()}** (score {h.score:.2f})\n{txt}\n"
        embed = discord.Embed(
            title="Question needs staff input",
            description=question,
            color=discord.Color.orange(),
        )
        embed.add_field(name="Asked by", value=asker.mention, inline=False)
        if snippets:
            embed.add_field(name="Top corpus matches", value=snippets[:1024], inline=False)
        try:
            await ch.send(embed=embed)
        except Exception:
            logger.exception("failed to post escalation")


def build_client(index: Index) -> AskBot:
    client = AskBot(index)

    @client.tree.command(name="ask", description="Ask the 42Tokyo rules bot")
    @app_commands.describe(question="What do you want to know?")
    async def ask(interaction: discord.Interaction, question: str) -> None:
        await interaction.response.defer(thinking=True)
        hits = client.index.query(question, k=3)
        top_score = hits[0].score if hits else 0.0
        escalate = top_score < client.min_sim
        if escalate:
            reply = LLMReply(
                text=(
                    "I do not have enough information to answer that with "
                    "confidence. Escalating to staff."
                ),
                used_llm=False,
            )
            await client._post_escalation(question, interaction.user, hits)
        else:
            ctx = [(h.chunk.short_source(), h.chunk.text) for h in hits]
            reply = await answer(question, ctx)
        embed = _build_embed(question, reply, hits, escalated=escalate)
        await interaction.followup.send(embed=embed)

    return client


def main() -> int:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    token = os.environ.get("DISCORD_TOKEN", "").strip()
    if not token:
        print("DISCORD_TOKEN is not set. Copy .env.example to .env and fill it in.",
              file=sys.stderr)
        return 1
    index = _load_index()
    client = build_client(index)
    client.run(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
