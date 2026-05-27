import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from cogs.free_games import FreeGamesCog
from services.emoji_setup import EmojiSetup

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

TOKEN = os.environ["DISCORD_TOKEN"]

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    log.info("Bot 已上線：%s", bot.user)

    # 上傳 / 確認 Application Emoji（需要 assets/steam.png 和 assets/epic.png）
    emoji_setup = EmojiSetup(application_id=str(bot.application_id), token=TOKEN)
    emoji_ids = await emoji_setup.ensure_emojis()
    if emoji_ids:
        log.info("Application Emoji 就緒：%s", list(emoji_ids.keys()))
    else:
        log.info("未設定 Application Emoji，使用 Unicode emoji fallback")

    cog = FreeGamesCog(bot, emoji_ids=emoji_ids)
    await bot.add_cog(cog)

    # 全域同步（最長 1 小時生效）
    await bot.tree.sync()
    log.info("Slash commands 全域同步完成")

    # 對每個已加入的伺服器做即時同步（立即生效）
    for guild in bot.guilds:
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        log.info("Guild %s slash commands 即時同步完成", guild.name)

    for guild in bot.guilds:
        if guild.id not in [int(gid) for gid in cog._guild_channels._channels]:
            channel = await cog._setup_channel(guild)
            if channel:
                cog._guild_channels.set(guild.id, channel.id)
                await channel.send(
                    "👋 嗨！我是 **ClaimBot**，我會在這裡通知你 Steam 及 Epic Games 限時免費遊戲。\n"
                    "輸入 `/help` 查看所有指令說明 🎮"
                )
                log.info("已在伺服器 %s 建立頻道 %s", guild.name, channel.name)


bot.run(TOKEN)
