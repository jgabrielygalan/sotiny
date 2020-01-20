import asyncio
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
        self.messages_by_player = {}

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
            await ctx.send("Draft in progress. Players: {p}".format(p=", ".join([p.display_name for p in self.players.values()])))
        else:
            await ctx.send("{p} are registered for the next draft".format(p=", ".join([p.display_name for p in self.players.values()])))

    @commands.command(name='start', help="Start the draft with the current self.players")
    async def start(self, ctx):
        if self.started:
            await ctx.send("Draft already start. Players: {p}".format(p=[p.display_name for p in self.players.values()]))
            return
        if len(self.players) == 0:
            await ctx.send("Can't start the draft, there are no registered players")
            return
        self.started = True
        await ctx.send("Starting the draft with {p}".format(p=[p.mention for p in self.players.values()]))
        async with ctx.typing():
            self.draft = Draft(list(self.players.keys()))
            self.draft.start()
            for p in self.players.values():
                self.messages_by_player[p.id] = []
            intro = "Draft has started. Here is your first pack. Type: >pick <cardname> to make your pick"
            await asyncio.gather(*[self.send_packs_to_player(intro, p, p.id) for p in self.players.values()])


    @commands.command(name='pick', help='Pick a card from the booster')
    async def pick(self, ctx, *, card):
        if ctx.author.id not in self.players:
            await ctx.send("You are not registered for the current draft")
            return

        state = self.draft.pick(ctx.author.id, card_name=card)
        await self.handle_pick_response(state, ctx, ctx.author.id)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, author) -> None:
        if author == self.bot.user:
            return
        if author.id not in self.players:
            await author.send("You are not registered for the current draft")
            return

        print("Reacted to: {m}".format(m=reaction.message.content))
        page_number = int(re.search(r'^(1|2|3)', reaction.message.content).group(1))
        item_number = NUMBERS_BY_EMOJI[reaction.emoji]
        print("User {u} reacted with {n} to message {i}".format(u=author.name, n=item_number, i=page_number))
        state = self.draft.pick(author.id, position=item_number+(5*(page_number-1)))
        await self.handle_pick_response(state, reaction.message.channel, author.id)

    async def handle_pick_response(self, state, messageable, player_id):
        if state == PickReturn.pick_error:
            await messageable.send("That card is not in the booster")
        else:
            print("Deleting {m}".format(m=self.messages_by_player[player_id]))
            [await message.delete() for message in self.messages_by_player[player_id]]
            self.messages_by_player[player_id].clear()

            if state == PickReturn.in_progress:
                await messageable.send("Waiting for other players to make their picks")
            elif state == PickReturn.next_booster:
                await asyncio.gather(*[self.send_packs_to_player("Your picks: \n{picks}\nNext pack:".format(picks=", ".join(self.draft.deck_of(p.id))), p, p.id) for p in self.players.values()])
            else:
                for player in self.players.values():
                    await player.send("The draft finished")
                    content = generate_file_content(self.draft.deck_of(player.id))
                    file=BytesIO(bytes(content, 'utf-8'))
                    await player.send(content="Your picks", file=File(fp=file, filename="picks.txt"))
                self.players.clear()
                self.started = False


    async def send_packs_to_player(self, intro, messageable, player_id):
        async with messageable.typing():
            await messageable.send(intro)
            cards = self.draft.pack_of(player_id).cards
            print(numpy.array(cards))
            list = numpy.array_split(numpy.array(cards),[5,10]) #split at positions 5 and 10, defaulting to empty arrays
            i = 1
            for l in list:
                if l is not None and len(l)>0:
                    image_file = await image_fetcher.download_image_async(l)
                    message = await send_image_with_retry(messageable, image_file, f"{i}")
                    #message = await messageable.send("")
                    self.messages_by_player[player_id].append(message)
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
