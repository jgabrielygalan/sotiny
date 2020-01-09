from discord.ext import commands
from draft import Draft
from draft import PickReturn

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
            await ctx.send("Draft in progress. Players: {p}".format(p=[p.nick for p in self.players.values()]))
        else:
            await ctx.send("{p} are registered for the next draft".format(p=[p.nick for p in self.players.values()]))

    @commands.command(name='start', help="Start the draft with the current self.players")
    async def start(self, ctx):
        if self.started:
            await ctx.send("Draft already start. Players: {p}".format(p=[p.nick for p in self.players.values()]))
            return
        if len(self.players) == 0:
            await ctx.send("Can't start the draft, there are no self.players registered")
            return
        self.started = True
        await ctx.send("Starting the draft with {p}".format(p=[p.mention for p in self.players.values()]))
        async with ctx.typing():
            self.draft = Draft(list(self.players.keys()))
            packs = self.draft.start()
            for p in self.players.values():
                await p.send("Draft has started. Here is your first pack. Type: >pick <cardname> to make your pick")
                await p.send(packs[p.id])
            await ctx.send("Pack 1 sent to all players")


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
            self.started = False
