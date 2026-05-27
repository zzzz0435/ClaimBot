import logging
from datetime import datetime, timezone
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands, tasks

from services.emoji_setup import EMOJI_NAMES
from services.epic_client import EpicClient, UpcomingGame
from services.gamerpower_client import FreeGame, GamerPowerClient, PLATFORM_LABELS
from storage.guild_channels import GuildChannels
from storage.guild_platforms import GuildPlatforms
from storage.guild_roles import GuildRoles
from storage.seen_games import SeenGames

log = logging.getLogger(__name__)

SEEN_GAMES_PATH = Path("data/seen_games.json")
UPCOMING_COLOR = discord.Color(0xF5A623)

# 每個平台的 Embed 顏色
PLATFORM_COLORS: dict[str, discord.Color] = {
    "steam": discord.Color(0x2ECC71),
    "epic-games-store": discord.Color(0x0074E4),
}

# Author 欄文字（有 Application Emoji 時搭配 icon_url，沒有時加前綴 emoji）
PLATFORM_AUTHOR_TEXT: dict[str, str] = {
    "steam": "Steam 限時免費",
    "epic-games-store": "Epic Games 限時免費",
}
PLATFORM_AUTHOR_FALLBACK: dict[str, str] = {
    "steam": "🎮 Steam 限時免費",
    "epic-games-store": "⚡ Epic Games 限時免費",
}


def filter_new_games(games: list[FreeGame], seen_ids: set[str]) -> list[FreeGame]:
    return [g for g in games if g.id not in seen_ids]


def build_embed(game: FreeGame, emoji_ids: dict[str, int] | None = None) -> discord.Embed:
    color = PLATFORM_COLORS.get(game.platform, discord.Color(0x2ECC71))
    embed = discord.Embed(title=game.title, url=game.url, color=color)

    # Author 欄：有 Application Emoji 時用品牌 Logo 作為 icon，否則用 Unicode emoji
    emoji_id = (emoji_ids or {}).get(game.platform)
    if emoji_id:
        embed.set_author(
            name=PLATFORM_AUTHOR_TEXT.get(game.platform, "限時免費"),
            icon_url=f"https://cdn.discordapp.com/emojis/{emoji_id}.png",
        )
    else:
        embed.set_author(name=PLATFORM_AUTHOR_FALLBACK.get(game.platform, "🎮 限時免費"))

    if game.image_url:
        embed.set_image(url=game.image_url)

    if game.worth:
        embed.add_field(name="💰 原價", value=game.worth, inline=True)

    if game.expires_at:
        embed.add_field(
            name="⏰ 限免截止",
            value=(
                discord.utils.format_dt(game.expires_at, style="F")
                + "\n"
                + discord.utils.format_dt(game.expires_at, style="R")
            ),
            inline=True,
        )

    embed.set_footer(text="資料來源：GamerPower")
    return embed


def build_view(game: FreeGame, emoji_ids: dict[str, int] | None = None) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    if game.url:
        platform_label = PLATFORM_LABELS.get(game.platform, game.platform)

        # 按鈕 emoji：有 Application Emoji 用品牌 Logo，否則用 🎮
        emoji_id = (emoji_ids or {}).get(game.platform)
        if emoji_id:
            emoji_name = EMOJI_NAMES.get(game.platform, "emoji")
            button_emoji: discord.PartialEmoji | str = discord.PartialEmoji(
                name=emoji_name, id=emoji_id
            )
        else:
            button_emoji = "🎮"

        view.add_item(discord.ui.Button(
            label=f"在 {platform_label} 領取",
            url=game.url,
            emoji=button_emoji,
            style=discord.ButtonStyle.link,
        ))
    return view


def build_upcoming_embed(game: UpcomingGame) -> discord.Embed:
    embed = discord.Embed(title=game.title, url=game.url, color=UPCOMING_COLOR)
    if game.image_url:
        embed.set_image(url=game.image_url)
    if game.start_date:
        embed.add_field(
            name="📅 開始免費",
            value=(
                discord.utils.format_dt(game.start_date, style="F")
                + "\n"
                + discord.utils.format_dt(game.start_date, style="R")
            ),
            inline=True,
        )
    if game.end_date:
        embed.add_field(
            name="⏰ 結束時間",
            value=(
                discord.utils.format_dt(game.end_date, style="F")
                + "\n"
                + discord.utils.format_dt(game.end_date, style="R")
            ),
            inline=True,
        )
    embed.set_footer(text="即將免費 | Epic Games")
    return embed


def build_upcoming_view(game: UpcomingGame) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    if game.url:
        view.add_item(discord.ui.Button(
            label="在 Epic Games 查看",
            url=game.url,
            emoji="🔗",
            style=discord.ButtonStyle.link,
        ))
    return view


class FreeGamesCog(commands.Cog):
    def __init__(self, bot: commands.Bot, emoji_ids: dict[str, int] | None = None):
        self._bot = bot
        self._emoji_ids: dict[str, int] = emoji_ids or {}
        self._client = GamerPowerClient()
        self._epic_client = EpicClient()
        self._seen = SeenGames(SEEN_GAMES_PATH)
        self._guild_channels = GuildChannels()
        self._guild_roles = GuildRoles()
        self._guild_platforms = GuildPlatforms()
        self._last_check: datetime | None = None
        self.check_free_games.start()

    def cog_unload(self):
        self.check_free_games.cancel()

    @tasks.loop(hours=6)
    async def check_free_games(self):
        guild_items = self._guild_channels.all_items()
        if not guild_items:
            log.info("尚未有任何伺服器設定頻道，跳過")
            return

        needed_platforms: set[str] = set()
        for guild_id, _ in guild_items:
            needed_platforms.update(self._guild_platforms.get(guild_id))

        games = await self._client.get_free_games(list(needed_platforms))
        new_games = filter_new_games(games, self._seen.seen_ids)

        if not new_games:
            log.info("無新免費遊戲，跳過")
            self._last_check = datetime.now(timezone.utc)
            return

        total_sent = 0
        for guild_id, channel_id in guild_items:
            channel = self._bot.get_channel(channel_id)
            if channel is None:
                log.warning("找不到頻道 ID %s，跳過", channel_id)
                continue

            guild_platforms = self._guild_platforms.get(guild_id)
            guild_games = [g for g in new_games if g.platform in guild_platforms]
            if not guild_games:
                continue

            role_id = self._guild_roles.get(guild_id)
            content = f"<@&{role_id}>" if role_id else None

            for game in guild_games:
                await channel.send(content=content, embed=build_embed(game, self._emoji_ids), view=build_view(game, self._emoji_ids))
                total_sent += 1

        self._seen.add({g.id for g in new_games})
        self._last_check = datetime.now(timezone.utc)
        log.info("已發送 %d 則通知，新遊戲 %d 款至 %d 個伺服器", total_sent, len(new_games), len(guild_items))

    @check_free_games.before_loop
    async def before_check(self):
        await self._bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        channel = await self._setup_channel(guild)
        if channel:
            self._guild_channels.set(guild.id, channel.id)
            await channel.send(
                "👋 嗨！我是 **ClaimBot**，我會在這裡通知你 Steam 及 Epic Games 限時免費遊戲。\n"
                "可用指令：`/freegames` 手動查詢、`/upcoming` 即將免費、"
                "`/setchannel` 設定頻道、`/setrole` 設定通知身份組、`/setplatforms` 設定平台 🎮\n"
                "輸入 `/help` 查看所有指令說明。"
            )
            log.info("已在伺服器 %s 建立頻道 %s", guild.name, channel.name)

    async def _setup_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        existing = discord.utils.get(guild.text_channels, name="免費遊戲")
        if existing:
            return existing
        try:
            return await guild.create_text_channel(
                name="免費遊戲",
                topic="Steam & Epic Games 限時免費遊戲通知 | 由 ClaimBot 自動推送",
            )
        except discord.Forbidden:
            log.warning("在伺服器 %s 沒有建立頻道的權限", guild.name)
            return None

    # ── /status ───────────────────────────────────────────────────────────────

    @app_commands.command(name="status", description="顯示 ClaimBot 目前的設定狀態")
    async def status(self, interaction: discord.Interaction):
        embed = discord.Embed(title="📊 ClaimBot 狀態", color=EMBED_COLOR)

        # 通知頻道
        channel_id = self._guild_channels._channels.get(str(interaction.guild_id))
        if channel_id:
            ch = self._bot.get_channel(channel_id)
            channel_text = ch.mention if ch else f"⚠️ 頻道已失效（ID: {channel_id}）"
        else:
            channel_text = "❌ 未設定（請執行 `/setchannel`）"
        embed.add_field(name="📢 通知頻道", value=channel_text, inline=False)

        # 通知身份組
        role_id = self._guild_roles.get(interaction.guild_id)
        if role_id:
            role = interaction.guild.get_role(role_id)
            role_text = role.mention if role else f"⚠️ 身份組已失效（ID: {role_id}）"
        else:
            role_text = "未設定"
        embed.add_field(name="🔔 通知身份組", value=role_text, inline=True)

        # 監控平台
        platforms = self._guild_platforms.get(interaction.guild_id)
        platform_text = " + ".join(PLATFORM_LABELS.get(p, p) for p in platforms)
        embed.add_field(name="🎮 監控平台", value=platform_text, inline=True)

        # 上次 / 下次檢查時間
        if self._last_check:
            last_text = discord.utils.format_dt(self._last_check, style="R")
        else:
            last_text = "尚未執行"
        embed.add_field(name="🕐 上次檢查", value=last_text, inline=True)

        next_iter = self.check_free_games.next_iteration
        next_text = discord.utils.format_dt(next_iter, style="R") if next_iter else "未知"
        embed.add_field(name="⏳ 下次檢查", value=next_text, inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /setchannel ──────────────────────────────────────────────────────────

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

    # ── /setrole ─────────────────────────────────────────────────────────────

    @app_commands.command(name="setrole", description="設定免費遊戲通知要 @mention 的身份組（留空清除）")
    @app_commands.describe(role="要被 ping 的身份組；不填則清除設定")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setrole(self, interaction: discord.Interaction, role: discord.Role | None = None):
        if role is None:
            self._guild_roles.clear(interaction.guild_id)
            await interaction.response.send_message("✅ 已清除通知身份組設定。", ephemeral=True)
        else:
            self._guild_roles.set(interaction.guild_id, role.id)
            await interaction.response.send_message(
                f"✅ 已設定 {role.mention} 為免費遊戲通知身份組。", ephemeral=True
            )
        log.info("伺服器 %s 設定通知身份組 %s", interaction.guild_id, role)

    @setrole.error
    async def setrole_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ 需要「管理伺服器」權限才能設定通知身份組。", ephemeral=True)

    # ── /setplatforms ─────────────────────────────────────────────────────────

    @app_commands.command(name="setplatforms", description="設定要接收哪些平台的遊戲通知（需管理員權限）")
    @app_commands.describe(platforms="選擇要接收通知的平台")
    @app_commands.choices(platforms=[
        app_commands.Choice(name="Steam + Epic Games（全部）", value="all"),
        app_commands.Choice(name="僅 Steam", value="steam"),
        app_commands.Choice(name="僅 Epic Games", value="epic-games-store"),
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setplatforms(self, interaction: discord.Interaction, platforms: str):
        if platforms == "all":
            platform_list = ["steam", "epic-games-store"]
            label = "Steam + Epic Games"
        else:
            platform_list = [platforms]
            label = PLATFORM_LABELS.get(platforms, platforms)

        self._guild_platforms.set(interaction.guild_id, platform_list)
        await interaction.response.send_message(
            f"✅ 已設定通知平台為：**{label}**", ephemeral=True
        )
        log.info("伺服器 %s 設定通知平台 %s", interaction.guild_id, platform_list)

    @setplatforms.error
    async def setplatforms_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ 需要「管理伺服器」權限才能設定通知平台。", ephemeral=True)

    # ── /upcoming ─────────────────────────────────────────────────────────────

    @app_commands.command(name="upcoming", description="查詢 Epic Games 即將免費的遊戲")
    async def upcoming(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        games = await self._epic_client.get_upcoming_games()
        if not games:
            await interaction.followup.send("目前沒有 Epic Games 即將免費的遊戲預告 🎮", ephemeral=True)
            return

        await interaction.followup.send(
            f"📅 **即將免費的 Epic Games 遊戲（共 {len(games)} 款）**",
            ephemeral=True,
        )
        for game in games:
            await interaction.followup.send(
                embed=build_upcoming_embed(game),
                view=build_upcoming_view(game),
                ephemeral=True,
            )

    # ── /help ─────────────────────────────────────────────────────────────────

    @app_commands.command(name="help", description="顯示 ClaimBot 所有指令說明")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📖 ClaimBot 指令說明",
            description="ClaimBot 會自動偵測 Steam 及 Epic Games 的限時免費遊戲並推送通知。",
            color=EMBED_COLOR,
        )
        embed.add_field(
            name="🔍 `/freegames`",
            value="立即查詢目前所有限時免費遊戲，並發送至本伺服器的通知頻道。",
            inline=False,
        )
        embed.add_field(
            name="📅 `/upcoming`",
            value="查詢 Epic Games **即將**免費的遊戲預告（含開始時間）。",
            inline=False,
        )
        embed.add_field(
            name="📊 `/status`",
            value="查看目前的設定狀態：頻道、身份組、平台、上次 / 下次檢查時間。",
            inline=False,
        )
        embed.add_field(
            name="📢 `/setchannel`",
            value="將**目前所在頻道**設為免費遊戲通知頻道。\n🔒 需要「管理伺服器」權限。",
            inline=False,
        )
        embed.add_field(
            name="🔔 `/setrole [@身份組]`",
            value="設定有新遊戲時要 @mention 的身份組。\n不填參數則**清除**現有設定。\n🔒 需要「管理伺服器」權限。",
            inline=False,
        )
        embed.add_field(
            name="🎮 `/setplatforms`",
            value=(
                "設定要接收哪些平台的通知：\n"
                "・**Steam + Epic Games**（預設，全部）\n"
                "・**僅 Steam**\n"
                "・**僅 Epic Games**\n"
                "🔒 需要「管理伺服器」權限。"
            ),
            inline=False,
        )
        embed.set_footer(text="Bot 每 6 小時自動檢查一次新遊戲")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /freegames ────────────────────────────────────────────────────────────

    @app_commands.command(name="freegames", description="查詢目前限時免費遊戲")
    async def freegames(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        channel_id = self._guild_channels._channels.get(str(interaction.guild_id))
        target = self._bot.get_channel(channel_id) if channel_id else None

        if target is None:
            await interaction.followup.send("❌ 尚未設定通知頻道，請先執行 `/setchannel`。", ephemeral=True)
            return

        guild_platforms = self._guild_platforms.get(interaction.guild_id)
        games = await self._client.get_free_games(guild_platforms)

        if not games:
            await interaction.followup.send("目前沒有限時免費遊戲 🎮", ephemeral=True)
            return

        role_id = self._guild_roles.get(interaction.guild_id)
        content = f"<@&{role_id}>" if role_id else None

        for game in games:
            await target.send(content=content, embed=build_embed(game, self._emoji_ids), view=build_view(game, self._emoji_ids))

        await interaction.followup.send(f"✅ 已發送至 {target.mention}", ephemeral=True)
