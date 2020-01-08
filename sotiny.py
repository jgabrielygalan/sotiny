import os
import random

from draft import Draft
from draft_cog import DraftCog

CUBE_CARDS = 'EternalPennyDreadfulCube.txt'

from dotenv import load_dotenv

from discord.ext import commands

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')


bot = commands.Bot(command_prefix='>')

@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')


bot.add_cog(DraftCog(bot))
bot.run('NjYzMDI3MjY5NjAxNTkxMzI3.XhCjYg.V4f6J8u9KmPHJhrXkXkcmCSnQyw')

