#sotiny.py

import os
import json
import logging

from draft_cog import DraftCog
from image_cog import ImageCog

from discord.ext import commands


logging.basicConfig(filename='test.log', format='%(asctime)s - %(name)s - %(levelname)s: %(message)s', level=logging.INFO)
logger = logging.getLogger('sotiny')


cfg = json.load(open('config.json'))
TOKEN = cfg['DISCORD_TOKEN']
PREFIX = "--"
if 'BOT_PREFIX' in cfg:
    PREFIX = cfg['BOT_PREFIX']

bot = commands.Bot(command_prefix=PREFIX)

@bot.event
async def on_ready():
    logger.info(f'{bot.user.name} has connected to Discord!')


bot.add_cog(DraftCog(bot))
#bot.add_cog(ImageCog(bot))
bot.run(TOKEN)

