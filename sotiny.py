#sotiny.py

import json
import os

from discord.ext import commands
import dotenv

dotenv.load_dotenv()

PREFIX = os.getenv('BOT_PREFIX', default='>')
bot = commands.Bot(command_prefix=commands.when_mentioned_or(PREFIX))

@bot.event
async def on_ready() -> None:
    print(f'{bot.user.name} has connected to Discord!')

bot.load_extension('draft_cog')
bot.load_extension('updater')
bot.load_extension('botguild')
bot.load_extension("jishaku")
bot.run(os.getenv('DISCORD_TOKEN'))
