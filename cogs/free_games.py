import logging
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands, tasks

from services.gamerpower_client import FreeGame, GamerPowerClient
from storage.seen_games import SeenGames

log = logging.getLogger(__name__)

SEEN_GAMES_PATH = Path("data/seen_games.json")
EMBED_COLOR = discord.Color(0x2ECC71)


def filter_new_games(games: list[FreeGame], seen_ids: set[str]) -> list[FreeGame]:
    return [g for g in games if g.id not in seen_ids]


def build_embed(game: FreeGame) -> discord.Embed:
    embed = discord.Embed(title=game.title, url=game.url, color=EMBED_COLOR)
    if game.image_url:
        embed.set_image(url=game.image_url)
    if game.url:
        embed.add_field(name="🎮 在 Steam 領取", value=f"[點我領取]({game.url})", inline=False)
    if game.expires_at:
        embed.add_field(name="⏰ 到期時間", value=game.expires_at, inline=False)
    embed.set_footer(text="資料來源：GamerPower")
    return embed


class FreeGamesCog(commands.Cog):
    def __init__(self, bot: commands.Bot, channel_id: int):
        self._bot = bot
        self._channel_id = channel_id
        self._client = GamerPowerClient()
        self._seen = SeenGames(SEEN_GAMES_PATH)
        self.check_free_games.start()

    def cog_unload(self):
        self.check_free_games.cancel()

    @tasks.loop(hours=6)
    async def check_free_games(self):
        channel = self._bot.get_channel(self._channel_id)
        if channel is None:
            log.error("找不到頻道 ID %s", self._channel_id)
            return

        games = await self._client.get_free_games()
        new_games = filter_new_games(games, self._seen.seen_ids)

        if not new_games:
            log.info("無新免費遊戲，跳過")
            return

        for game in new_games:
            await channel.send(embed=build_embed(game))

        self._seen.add({g.id for g in new_games})
        log.info("已發送 %d 款新免費遊戲", len(new_games))

    @check_free_games.before_loop
    async def before_check(self):
        await self._bot.wait_until_ready()

    @app_commands.command(name="freegames", description="查詢目前 Steam 限時免費遊戲")
    async def freegames(self, interaction: discord.Interaction):
        await interaction.response.defer()
        games = await self._client.get_free_games()
        if not games:
            await interaction.followup.send("目前沒有 Steam 限時免費遊戲 🎮")
            return
        for game in games:
            await interaction.followup.send(embed=build_embed(game))
