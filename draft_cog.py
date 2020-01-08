from discord.ext import commands
from draft import Draft
from draft import PickReturn

class DraftCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = {}

    @commands.command(name='play', help='Register to play a draft')
    async def play(self, ctx):
        player = ctx.author
        if player.id not in self.players:
            self.players[player.id] = player
            await player.send("Successfully registered")
            await ctx.send("{mention}, I have registered you for the next draft".format(mention=ctx.author.mention))
        else:
            await player.send("You were already registered")
            await ctx.send("{mention}, you are already registered for the next draft".format(mention=ctx.author.mention))


    @commands.command(name='start', help="Start the draft with the current self.players")
    async def start(self, ctx):
        if len(self.players) == 0:
            await ctx.send("Can't start the draft, there are no self.players registered")
            return
        await ctx.send("Starting the draft with {p}".format(p=[p.mention for p in self.players.values()]))
        async with ctx.typing():
            self.draft = Draft(list(self.players.keys()))
            packs = self.draft.start()
            for p in self.players.values():
                await p.dm_channel.send("Draft has started. Here is your first pack. Type: >pick <cardname> to make your pick")
                await p.dm_channel.send(packs[p.id])
            await ctx.send("Sent pack 1 to all self.players")


    @commands.command(name='pick', help='Pick a card from the booster')
    async def pick(self, ctx, *, card):
        if ctx.author.id not in self.players:
            await ctx.send("You are not registered for the current draft")
            return

        await ctx.send("You picked {card}".format(card=card))
        state = self.draft.pick(ctx.author.id, card)
        if state == PickReturn.pick_error:
            await ctx.send("That card is not in the booster")
        elif state == PickReturn.in_progress:
            await ctx.send("Waiting for other self.players to make their picks")
        elif state == PickReturn.next_booster:
            packs = self.draft.state
            for player in self.players.values():
                await player.dm_channel.send("Your picks: ")
                await player.dm_channel.send(self.draft.decks[player.id])
                await player.dm_channel.send("Next pack:")
                await player.dm_channel.send(packs[player.id])
        else:
            for player in self.players.values():
                await player.dm_channel.send("The draft finished")
                await player.dm_channel.send("Your picks: ")
                await player.dm_channel.send(self.draft.decks[player.id])
            self.players.clear()
