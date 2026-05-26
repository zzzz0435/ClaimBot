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

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    log.info("Bot 已上線：%s", bot.user)
    await bot.add_cog(FreeGamesCog(bot))
    await bot.tree.sync()
    log.info("Slash commands 已同步")


bot.run(TOKEN)
