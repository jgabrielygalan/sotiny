
import os
import discord

from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')

client = discord.Client()

@client.event
async def on_ready():
    print(f'{client.user.name} has connected to Discord!')
    

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content == '>>>repartecartas':
        response = 'momentito estoy barajando...'
        await message.channel.send(response)
    elif message.content == 'raise-exception':
        raise discord.DiscordException
        
    
    
#client.run(TOKEN)

client.run('NjYzMDI3MjY5NjAxNTkxMzI3.XhCjYg.V4f6J8u9KmPHJhrXkXkcmCSnQyw')
