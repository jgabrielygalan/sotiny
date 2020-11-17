#sotiny.py

import os

import dotenv
from discord.ext import commands

dotenv.load_dotenv()

if not os.path.exists('drafts'):
    os.mkdir('drafts')

PREFIX = os.getenv('BOT_PREFIX', default='>')
bot = commands.Bot(command_prefix=commands.when_mentioned_or(PREFIX))
bot.owner_ids = {154363842451734528, 323861986356232204, 411664250768195586}

@bot.event
async def on_ready() -> None:
    print(f'{bot.user.name} has connected to Discord!')

bot.load_extension('draft_cog')
bot.load_extension('updater')
bot.load_extension('botguild')
bot.load_extension("jishaku")
bot.run(os.getenv('DISCORD_TOKEN'))
