#sotiny.py

import json
import os

from discord.ext import commands

from draft_cog import DraftCog
from image_cog import ImageCog

cfg = json.load(open('config.json'))
TOKEN = cfg['DISCORD_TOKEN']
PREFIX = ">"
if 'BOT_PREFIX' in cfg:
    PREFIX = cfg['BOT_PREFIX']

bot = commands.Bot(command_prefix=PREFIX)

@bot.event
async def on_ready() -> None:
    print(f'{bot.user.name} has connected to Discord!')


bot.add_cog(DraftCog(bot, cfg))
bot.load_extension('updater')
#bot.add_cog(ImageCog(bot))
bot.run(TOKEN)
