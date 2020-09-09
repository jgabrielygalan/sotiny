#sotiny.py

import json

from discord.ext import commands


cfg = json.load(open('config.json'))
TOKEN = cfg['DISCORD_TOKEN']
PREFIX = ">"
if 'BOT_PREFIX' in cfg:
    PREFIX = cfg['BOT_PREFIX']

bot = commands.Bot(command_prefix=PREFIX)

@bot.event
async def on_ready() -> None:
    print(f'{bot.user.name} has connected to Discord!')

bot.cfg = cfg
bot.load_extension('draft_cog')
bot.load_extension('updater')
bot.load_extension('botguild')
bot.load_extension("jishaku")
bot.run(TOKEN)
