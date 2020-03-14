from discord import File
from discord.ext import commands

import image_fetcher


class ImageCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='image', help='Pull an image')
    async def play(self, ctx, *args):
    	print(args)
    	image_file = await image_fetcher.download_image_async(args)
    	await send_image_with_retry(ctx.channel, image_file)


async def send_image_with_retry(channel, image_file: str, text: str = '') -> None:
    message = await send(channel, file=File(image_file), content=text)
    if message and message.attachments and message.attachments[0].size == 0:
        print('Message size is zero so resending')
        await message.delete()
        await send(channel, file=File(image_file), content=text)

async def send(channel, content: str, file = None):
    new_s = escape_underscores(content)
    return await channel.send(file=file, content=new_s)

def escape_underscores(s: str) -> str:
    new_s = ''
    in_url, in_emoji = False, False
    for char in s:
        if char == ':':
            in_emoji = True
        elif char not in 'abcdefghijklmnopqrstuvwxyz_':
            in_emoji = False
        if char == '<':
            in_url = True
        elif char == '>':
            in_url = False
        if char == '_' and not in_url and not in_emoji:
            new_s += '\\_'
        else:
            new_s += char
    return new_s
