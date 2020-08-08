import os
import discord
from discord.ext import commands
import image_fetcher

class SelfGuild(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def get_server(self) -> discord.Guild:
        for guild in self.bot.guilds:
            if guild.name == self.bot.user.name:
                return guild
        return await self.bot.create_guild(self.bot.user.name)

    async def get_emoji(self, name: str) -> discord.Emoji:
        for emoji in self.bot.emojis:
            if emoji.name == name:
                return emoji
        path = os.path.join('emoji_images', name + '.png')
        if not os.path.exists(path):
            await image_fetcher.download_scryfall_card_image(name, path, 'art_crop')

        guild = await self.get_server()
        print(f'Uploading {name} to {guild.name}')
        with open(path, 'rb') as f:
            emoji = await guild.create_custom_emoji(name=name, image=f.read())
        return emoji

def setup(bot: commands.Bot) -> None:
    os.mkdir('emoji_images')
    bot.add_cog(SelfGuild(bot))
