import logging
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands, tasks

from services.gamerpower_client import FreeGame, GamerPowerClient
from storage.guild_channels import GuildChannels
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
    def __init__(self, bot: commands.Bot):
        self._bot = bot
        self._client = GamerPowerClient()
        self._seen = SeenGames(SEEN_GAMES_PATH)
        self._guild_channels = GuildChannels()
        self.check_free_games.start()

    def cog_unload(self):
        self.check_free_games.cancel()

    @tasks.loop(hours=6)
    async def check_free_games(self):
        channels = self._guild_channels.all_channels()
        if not channels:
            log.info("尚未有任何伺服器設定頻道，跳過")
            return

        games = await self._client.get_free_games()
        new_games = filter_new_games(games, self._seen.seen_ids)

        if not new_games:
            log.info("無新免費遊戲，跳過")
            return

        for channel_id in channels:
            channel = self._bot.get_channel(channel_id)
            if channel is None:
                log.warning("找不到頻道 ID %s，跳過", channel_id)
                continue
            for game in new_games:
                await channel.send(embed=build_embed(game))

        self._seen.add({g.id for g in new_games})
        log.info("已發送 %d 款新免費遊戲至 %d 個頻道", len(new_games), len(channels))

    @check_free_games.before_loop
    async def before_check(self):
        await self._bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        channel = await self._setup_channel(guild)
        if channel:
            self._guild_channels.set(guild.id, channel.id)
            await channel.send(
                "👋 嗨！我是 **ClaimBot**，我會在這裡通知你 Steam 限時免費遊戲。\n"
                "你也可以隨時輸入 `/freegames` 手動查詢目前的免費遊戲 🎮"
            )
            log.info("已在伺服器 %s 建立頻道 %s", guild.name, channel.name)

    async def _setup_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        existing = discord.utils.get(guild.text_channels, name="免費遊戲")
        if existing:
            return existing
        try:
            return await guild.create_text_channel(
                name="免費遊戲",
                topic="Steam 限時免費遊戲通知 | 由 ClaimBot 自動推送",
            )
        except discord.Forbidden:
            log.warning("在伺服器 %s 沒有建立頻道的權限", guild.name)
            return None

    @app_commands.command(name="setchannel", description="設定此頻道為免費遊戲通知頻道（需管理員權限）")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setchannel(self, interaction: discord.Interaction):
        self._guild_channels.set(interaction.guild_id, interaction.channel_id)
        await interaction.response.send_message(
            f"✅ 已將 {interaction.channel.mention} 設為本伺服器的免費遊戲通知頻道！",
            ephemeral=True,
        )
        log.info("伺服器 %s 設定頻道 %s", interaction.guild_id, interaction.channel_id)

    @setchannel.error
    async def setchannel_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ 需要「管理伺服器」權限才能設定通知頻道。", ephemeral=True)

    @app_commands.command(name="freegames", description="查詢目前 Steam 限時免費遊戲")
    async def freegames(self, interaction: discord.Interaction):
        await interaction.response.defer()
        games = await self._client.get_free_games()
        if not games:
            await interaction.followup.send("目前沒有 Steam 限時免費遊戲 🎮")
            return
        for game in games:
            await interaction.followup.send(embed=build_embed(game))
