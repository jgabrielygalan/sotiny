#sotiny.py

import os

from draft_cog import DraftCog
from image_cog import ImageCog

from dotenv import load_dotenv

from discord.ext import commands

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

bot = commands.Bot(command_prefix='>')

@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')


bot.add_cog(DraftCog(bot))
bot.add_cog(ImageCog(bot))
bot.run(TOKEN)

