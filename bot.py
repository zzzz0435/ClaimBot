import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from cogs.free_games import FreeGamesCog

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

TOKEN = os.environ["DISCORD_TOKEN"]
CHANNEL_ID = int(os.environ["DISCORD_CHANNEL_ID"])

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        log.error("無效的 DISCORD_CHANNEL_ID：%s，Bot 停止", CHANNEL_ID)
        await bot.close()
        return
    log.info("Bot 已上線：%s，目標頻道：#%s", bot.user, channel.name)
    await bot.add_cog(FreeGamesCog(bot, CHANNEL_ID))


bot.run(TOKEN)
