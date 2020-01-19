import numpy
import re
import tempfile
from io import BytesIO
from discord.ext import commands
from draft import Draft
from draft import PickReturn
from discord import File
import image_fetcher


EMOJIS_BY_NUMBER = {1 : '1⃣', 2 : '2⃣', 3 : '3⃣', 4 : '4⃣', 5 : '5⃣'}
NUMBERS_BY_EMOJI = {'1⃣' : 1, '2⃣' : 2, '3⃣' : 3, '4⃣' : 4, '5⃣' : 5}


class DraftCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = {}
        self.started = False

    @commands.command(name='play', help='Register to play a draft')
    async def play(self, ctx):
        player = ctx.author
        if self.started:
            await ctx.send("A draft is already in progress. Try later when it's over")
            return
        if player.id not in self.players:
            self.players[player.id] = player
            await ctx.send("{mention}, I have registered you for the next draft".format(mention=ctx.author.mention))
        else:
            await ctx.send("{mention}, you are already registered for the next draft".format(mention=ctx.author.mention))

    @commands.command(name='players', help='List registered players for the next draft')
    async def players(self, ctx):
        if self.started:
            await ctx.send("Draft in progress. Players: {p}".format(p=[p.display_name for p in self.players.values()]))
        else:
            await ctx.send("{p} are registered for the next draft".format(p=[p.display_name for p in self.players.values()]))

    @commands.command(name='start', help="Start the draft with the current self.players")
    async def start(self, ctx):
        if self.started:
            await ctx.send("Draft already start. Players: {p}".format(p=[p.display_name for p in self.players.values()]))
            return
        if len(self.players) == 0:
            await ctx.send("Can't start the draft, there are no players registered")
            return
        self.started = True
        await ctx.send("Starting the draft with {p}".format(p=[p.mention for p in self.players.values()]))
        async with ctx.typing():
            self.draft = Draft(list(self.players.keys()))
            packs = self.draft.start()
            for p in self.players.values():
                await p.send("Draft has started. Here is your first pack. Type: >pick <cardname> to make your pick")
                await send_cards_to_user(ctx, p, packs[p.id].cards)


    @commands.command(name='pick', help='Pick a card from the booster')
    async def pick(self, ctx, *, card):
        if ctx.author.id not in self.players:
            await ctx.send("You are not registered for the current draft")
            return

        #await ctx.send("You picked {card}".format(card=card))
        state = self.draft.pick(ctx.author.id, card_name=card)
        await self.handle_pick_response(state, ctx)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, author) -> None:
        if author == self.bot.user:
            return
        if author.id not in self.players:
            await author.send("You are not registered for the current draft")
            return

        page_number = int(re.search(r'(1|2|3)\.', reaction.message.content).group(1))
        item_number = NUMBERS_BY_EMOJI[reaction.emoji]
        print("User {u} reacted with {n} to message {i}".format(u=author.name, n=item_number, i=page_number))
        state = self.draft.pick(author.id, position=item_number+(5*(page_number-1)))
        await self.handle_pick_response(state, reaction.message.channel)

    async def handle_pick_response(self, state, messageable):
        if state == PickReturn.pick_error:
            await messageable.send("That card is not in the booster")
        elif state == PickReturn.in_progress:
            await messageable.send("Waiting for other players to make their picks")
        elif state == PickReturn.next_booster:
            packs = self.draft.state
            for player in self.players.values():
                await player.send("Your picks: ")
                # await send_cards_to_user(messageable, player, self.draft.decks[player.id], False)
                await player.send(", ".join(self.draft.decks[player.id]))
                await player.send("Next pack:")
                await send_cards_to_user(messageable, player, packs[player.id].cards)
        else:
            for player in self.players.values():
                await player.send("The draft finished. Your picks: ")
                #await send_cards_to_user(messageable, player, self.draft.decks[player.id], False)
                content = generate_file_content(self.draft.decks[player.id])
                file=BytesIO(bytes(content, 'utf-8'))
                await player.send(content="Your picks", file=File(fp=file, filename="picks.txt"))
            self.players.clear()
            self.started = False


async def send_cards_to_user(messageable, user, cards, pickable=True):
    async with messageable.typing():
        print(numpy.array(cards))
        list = numpy.array_split(numpy.array(cards),[5,10]) #split at positions 5 and 10, defaulting to empty arrays
        i = 1
        for l in list:
            if l is not None and len(l)>0:
                image_file = await image_fetcher.download_image_async(l)
                await send_image_with_retry(user, image_file)
                if pickable:
                    message = await user.send("{i}. Click a number below or type >pick <card name>".format(i=i))
                    i += 1
                    for j in range(1,len(l)+1):
                        await message.add_reaction(EMOJIS_BY_NUMBER[j])

async def send_image_with_retry(user, image_file: str, text: str = '') -> None:
    message = await send(user, file=File(image_file), content=text)
    if message and message.attachments and message.attachments[0].size == 0:
        print('Message size is zero so resending')
        await message.delete()
        message = await send(user, file=File(image_file), content=text)
    return message

async def send(user, content: str, file = None):
    new_s = escape_underscores(content)
    return await user.send(file=file, content=new_s)

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

def generate_file_content(cards):
    return "\n".join(["1 {c}".format(c=card) for card in cards])
