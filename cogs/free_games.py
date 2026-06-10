import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands, tasks

from services.emoji_setup import EMOJI_NAMES
from services.epic_client import EpicClient, UpcomingGame
from services.gamerpower_client import FreeGame, GamerPowerClient, PLATFORM_LABELS
from services.itad_client import ITADClient, PriceDeal
from storage.guild_channels import GuildChannels
from storage.guild_dlc import GuildDLC
from storage.guild_platforms import GuildPlatforms
from storage.guild_price_alerts import GuildPriceAlerts
from storage.guild_roles import GuildRoles
from storage.seen_games import SeenGames
from storage.seen_price_lows import SeenPriceLows

log = logging.getLogger(__name__)

SEEN_GAMES_PATH = Path("data/seen_games.json")
EMBED_COLOR = discord.Color(0x2ECC71)       # Bot 通用顏色（/status、/help）
UPCOMING_COLOR = discord.Color(0xF5A623)
PRICE_LOW_COLOR = discord.Color(0xF0A500)   # 歷史新低通知

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
    dlc_suffix = " (DLC)" if game.kind == "dlc" else ""
    if emoji_id:
        embed.set_author(
            name=PLATFORM_AUTHOR_TEXT.get(game.platform, "限時免費") + dlc_suffix,
            icon_url=f"https://cdn.discordapp.com/emojis/{emoji_id}.png",
        )
    else:
        embed.set_author(name=PLATFORM_AUTHOR_FALLBACK.get(game.platform, "🎮 限時免費") + dlc_suffix)

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


def build_price_embed(deal: PriceDeal) -> discord.Embed:
    embed = discord.Embed(title=deal.title, url=deal.url, color=PRICE_LOW_COLOR)
    embed.set_author(name="📉 Steam 歷史新低")
    if deal.image_url:
        embed.set_image(url=deal.image_url)
    embed.add_field(
        name="💰 目前售價",
        value=f"**{deal.currency} {deal.current_price:.2f}** (-{deal.discount_pct}%)",
        inline=True,
    )
    embed.add_field(
        name="📉 歷史最低",
        value=f"{deal.currency} {deal.historical_low:.2f}",
        inline=True,
    )
    embed.add_field(
        name="🔖 原價",
        value=f"{deal.currency} {deal.original_price:.2f}",
        inline=True,
    )
    embed.set_footer(text="資料來源：IsThereAnyDeal")
    return embed


def build_price_view(deal: PriceDeal) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    if deal.url:
        view.add_item(discord.ui.Button(
            label="在 Steam 購買",
            url=deal.url,
            emoji="🛒",
            style=discord.ButtonStyle.link,
        ))
    return view


class FreeGamesCog(commands.Cog):
    def __init__(
        self,
        bot: commands.Bot,
        emoji_ids: dict[str, int] | None = None,
        itad_key: str | None = None,
    ):
        self._bot = bot
        self._emoji_ids: dict[str, int] = emoji_ids or {}
        self._client = GamerPowerClient()
        self._epic_client = EpicClient()
        self._itad_client = ITADClient(itad_key) if itad_key else None
        self._seen = SeenGames(SEEN_GAMES_PATH)
        self._guild_channels = GuildChannels()
        self._guild_roles = GuildRoles()
        self._guild_platforms = GuildPlatforms()
        self._guild_dlc = GuildDLC()
        self._guild_price_alerts = GuildPriceAlerts()
        self._seen_price_lows = SeenPriceLows()
        self._last_check: datetime | None = None
        self._check_lock = asyncio.Lock()
        self.check_free_games.start()

    def cog_unload(self):
        self.check_free_games.cancel()

    @tasks.loop(hours=6)
    async def check_free_games(self):
        try:
            await self._do_check()
        except Exception:
            # 未預期例外若外洩會讓 tasks.loop 永久停擺，吞下並等待下次排程
            log.exception("排程檢查發生未預期錯誤，等待下次排程重試")

    async def _do_check(self):
        if self._check_lock.locked():
            log.info("檢查已在進行中，跳過")
            return
        async with self._check_lock:
            if self._seen.needs_migration():
                self._seen.migrate([g.id for g in self._bot.guilds])

            guild_items = self._guild_channels.all_items()
            if not guild_items:
                log.info("尚未有任何伺服器設定頻道，跳過")
                return

            needed_platforms: set[str] = set()
            need_dlc = False
            for guild_id, _ in guild_items:
                needed_platforms.update(self._guild_platforms.get(guild_id))
                if self._guild_dlc.get(guild_id):
                    need_dlc = True

            games = await self._client.get_free_games(list(needed_platforms), include_dlc=need_dlc)
            if not games:
                log.info("目前無免費遊戲")

            total_sent = 0

            for guild_id, channel_id in guild_items:
                channel = self._bot.get_channel(channel_id)
                if channel is None:
                    log.warning("找不到頻道 ID %s，跳過", channel_id)
                    continue

                guild_platforms = self._guild_platforms.get(guild_id)
                guild_include_dlc = self._guild_dlc.get(guild_id)
                guild_seen = self._seen.seen_ids(guild_id)
                guild_games = [
                    g for g in games
                    if g.platform in guild_platforms
                    and g.id not in guild_seen
                    and (g.kind == "game" or guild_include_dlc)
                ]
                if not guild_games:
                    continue

                role_id = self._guild_roles.get(guild_id)
                content = f"<@&{role_id}>" if role_id else None
                newly_seen: set[str] = set()

                for game in guild_games:
                    try:
                        await channel.send(
                            content=content,
                            embed=build_embed(game, self._emoji_ids),
                            view=build_view(game, self._emoji_ids),
                        )
                        newly_seen.add(game.id)
                        total_sent += 1
                    except discord.HTTPException as e:
                        log.error(
                            "發送失敗 guild=%s channel=%s game=%s: %s",
                            guild_id, channel_id, game.id, e,
                        )

                if newly_seen:
                    self._seen.add(guild_id, newly_seen)

            await self._check_price_lows(guild_items)

            self._last_check = datetime.now(timezone.utc)
            log.info("已發送 %d 則通知至 %d 個伺服器", total_sent, len(guild_items))

    async def _check_price_lows(self, guild_items: list[tuple[int, int]]) -> None:
        if self._itad_client is None:
            return
        alert_guilds = [(gid, cid) for gid, cid in guild_items if self._guild_price_alerts.get(gid)]
        if not alert_guilds:
            return

        deals = await self._itad_client.get_steam_historical_lows()
        if not deals:
            return

        for guild_id, channel_id in alert_guilds:
            channel = self._bot.get_channel(channel_id)
            if channel is None:
                log.warning("歷史新低通知：找不到頻道 %s，跳過", channel_id)
                continue
            role_id = self._guild_roles.get(guild_id)
            content = f"<@&{role_id}>" if role_id else None
            for deal in deals:
                if not self._seen_price_lows.is_new_low(guild_id, deal.id, deal.current_price):
                    continue
                try:
                    await channel.send(
                        content=content,
                        embed=build_price_embed(deal),
                        view=build_price_view(deal),
                    )
                    self._seen_price_lows.mark(guild_id, deal.id, deal.current_price)
                except discord.HTTPException as e:
                    log.error(
                        "歷史新低通知發送失敗 guild=%s game=%s: %s",
                        guild_id, deal.id, e,
                    )

    @check_free_games.before_loop
    async def before_check(self):
        await self._bot.wait_until_ready()

    async def initialize_guild(self, guild: discord.Guild) -> None:
        if self._guild_channels.has(guild.id):
            return
        channel = await self._setup_channel(guild)
        if channel:
            self._guild_channels.set(guild.id, channel.id)
            try:
                await channel.send(
                    "👋 嗨！我是 **ClaimBot**，我會在這裡通知你 Steam 及 Epic Games 限時免費遊戲。\n"
                    "輸入 `/help` 查看所有指令說明 🎮"
                )
            except discord.HTTPException as e:
                log.warning("在伺服器 %s 發送歡迎訊息失敗: %s", guild.name, e)
            log.info("已在伺服器 %s 建立頻道 %s", guild.name, channel.name)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        await self.initialize_guild(guild)

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
        channel_id = self._guild_channels.get(interaction.guild_id)
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

        # DLC 設定
        dlc_enabled = self._guild_dlc.get(interaction.guild_id)
        embed.add_field(name="📦 DLC 通知", value="✅ 開啟" if dlc_enabled else "❌ 關閉", inline=True)

        # 歷史新低通知
        price_enabled = self._guild_price_alerts.get(interaction.guild_id)
        price_text = "✅ 開啟" if price_enabled else "❌ 關閉"
        if price_enabled and self._itad_client is None:
            price_text += " ⚠️（未設定 ITAD_KEY）"
        embed.add_field(name="📉 歷史新低通知", value=price_text, inline=True)

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

    # ── /setdlc ───────────────────────────────────────────────────────────────

    @app_commands.command(name="setdlc", description="設定是否接收 DLC / 遊戲內容物通知（需管理員權限）")
    @app_commands.describe(enabled="開啟後會一併通知 DLC 及遊戲內容物")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setdlc(self, interaction: discord.Interaction, enabled: bool):
        self._guild_dlc.set(interaction.guild_id, enabled)
        status = "✅ 已開啟" if enabled else "❌ 已關閉"
        await interaction.response.send_message(
            f"{status} DLC / 遊戲內容物通知。", ephemeral=True
        )
        log.info("伺服器 %s 設定 DLC 通知 %s", interaction.guild_id, enabled)

    @setdlc.error
    async def setdlc_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ 需要「管理伺服器」權限才能設定 DLC 通知。", ephemeral=True)

    # ── /setpricelow ──────────────────────────────────────────────────────────

    @app_commands.command(name="setpricelow", description="設定是否接收 Steam 歷史最低價格通知（需管理員權限）")
    @app_commands.describe(enabled="開啟後當 Steam 知名遊戲達到歷史新低時會發送通知")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setpricelow(self, interaction: discord.Interaction, enabled: bool):
        if self._itad_client is None:
            await interaction.response.send_message(
                "❌ 此功能需要在伺服器設定 `ITAD_KEY` 環境變數，請聯絡 Bot 管理員。",
                ephemeral=True,
            )
            return
        self._guild_price_alerts.set(interaction.guild_id, enabled)
        status = "✅ 已開啟" if enabled else "❌ 已關閉"
        await interaction.response.send_message(
            f"{status} Steam 歷史新低價格通知。\n"
            "（條件：評論數 ≥ 500 的遊戲，達到 Steam 歷史最低價時通知）",
            ephemeral=True,
        )
        log.info("伺服器 %s 設定歷史新低通知 %s", interaction.guild_id, enabled)

    @setpricelow.error
    async def setpricelow_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ 需要「管理伺服器」權限才能設定歷史新低通知。", ephemeral=True)

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
        embed.add_field(
            name="📦 `/setdlc [true/false]`",
            value=(
                "開啟或關閉 DLC / 遊戲內容物通知。\n"
                "預設**關閉**（只通知完整遊戲）。\n"
                "🔒 需要「管理伺服器」權限。"
            ),
            inline=False,
        )
        embed.add_field(
            name="📉 `/setpricelow [true/false]`",
            value=(
                "開啟或關閉 Steam **歷史新低**價格通知。\n"
                "條件：評論數 ≥ 500 的知名遊戲，達到 Steam 歷史最低價時通知。\n"
                "預設**關閉**。🔒 需要「管理伺服器」權限。"
            ),
            inline=False,
        )
        embed.add_field(
            name="⚡ `/checknow`",
            value="立即觸發免費遊戲檢查，不等下次排程。\n🔒 需要「管理伺服器」權限。",
            inline=False,
        )
        embed.set_footer(text="Bot 每 6 小時自動檢查一次新遊戲")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /checknow ─────────────────────────────────────────────────────────────

    @app_commands.command(name="checknow", description="立即觸發免費遊戲檢查並發送通知（需管理員權限）")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def checknow(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            await self._do_check()
        except Exception:
            log.exception("/checknow 檢查失敗")
            await interaction.followup.send("❌ 檢查過程發生錯誤，請稍後再試或查看伺服器日誌。", ephemeral=True)
            return
        await interaction.followup.send("✅ 檢查完成，有新遊戲的話已發送通知。", ephemeral=True)

    @checknow.error
    async def checknow_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ 需要「管理伺服器」權限才能執行此指令。", ephemeral=True)

    # ── /freegames ────────────────────────────────────────────────────────────

    @app_commands.command(name="freegames", description="查詢目前限時免費遊戲")
    async def freegames(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        channel_id = self._guild_channels.get(interaction.guild_id)
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

        sent = 0
        for game in games:
            try:
                await target.send(
                    content=content,
                    embed=build_embed(game, self._emoji_ids),
                    view=build_view(game, self._emoji_ids),
                )
                sent += 1
            except discord.HTTPException as e:
                log.error("手動發送失敗 channel=%s game=%s: %s", target.id, game.id, e)

        if sent:
            await interaction.followup.send(f"✅ 已發送 {sent} 款遊戲至 {target.mention}", ephemeral=True)
        else:
            await interaction.followup.send("❌ 發送失敗，請確認 Bot 在該頻道有發訊息的權限。", ephemeral=True)
