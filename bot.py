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


class ClaimBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.default())
        self._ready_done = False

    async def setup_hook(self):
        emoji_setup = EmojiSetup(application_id=str(self.application_id), token=TOKEN)
        emoji_ids = await emoji_setup.ensure_emojis()
        if emoji_ids:
            log.info("Application Emoji 就緒：%s", list(emoji_ids.keys()))
        else:
            log.info("未設定 Application Emoji，使用 Unicode emoji fallback")

        cog = FreeGamesCog(self, emoji_ids=emoji_ids)
        await self.add_cog(cog)
        await self.tree.sync()
        log.info("Slash commands 全域同步完成")

    async def on_ready(self):
        cog: FreeGamesCog | None = self.cogs.get("FreeGamesCog")  # type: ignore

        if not self._ready_done:
            log.info("Bot 已上線：%s", self.user)
            if cog and cog._seen.needs_migration():
                cog._seen.migrate([g.id for g in self.guilds])
            for guild in self.guilds:
                try:
                    self.tree.clear_commands(guild=guild)
                    await self.tree.sync(guild=guild)
                    log.info("Guild %s 專屬指令已清除", guild.name)
                except Exception as e:
                    log.error("Guild %s 指令清除失敗: %s", guild.name, e)
            self._ready_done = True
        else:
            log.info("Bot 重新連線：%s", self.user)

        for guild in self.guilds:
            try:
                if cog:
                    await cog.initialize_guild(guild)
            except Exception as e:
                log.error("Guild %s 初始化失敗: %s", guild.name, e)


bot = ClaimBot()
bot.run(TOKEN)
