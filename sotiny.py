
import os
import random

CUBE_CARDS = 'EternalPennyDreadfulCube.txt'

from dotenv import load_dotenv

from discord.ext import commands

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')

bot = commands.Bot(command_prefix='>>>')

@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')
    
@bot.command(name='reparte', help='reparte cartas')
async def repartir(ctx):

    with open(CUBE_CARDS) as f:
        read_cards = f.read().splitlines()


    cube = read_cards
    players = 4
    draft = {}

    for p in range(players):
        draft[f'player_{p}'] = []

        for i in range(15):
            card = cube.pop(random.randint(0, len(cube)))
            draft[f'player_{p}'].append(card)


    response = "\n".join(draft['player_0'])

    
    await ctx.send(response)
    
#client.run(TOKEN)




bot.run('NjYzMDI3MjY5NjAxNTkxMzI3.XhCjYg.V4f6J8u9KmPHJhrXkXkcmCSnQyw')
