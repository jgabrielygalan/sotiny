from discord.ext import commands
from draft_guild import DraftGuild
import inspect


def inject_draft_guild(func):
    async def decorator(self, ctx, *args, **kwargs):
        if not ctx.guild:
            print("Context doesn't have a guild")
            return

        draft_guild = self.guilds_by_id[ctx.guild.id]
        print(f"Found guild: {draft_guild}")
        await func(self, draft_guild, ctx, *args, **kwargs)

    decorator.__name__ = func.__name__
    sig = inspect.signature(func)
    decorator.__signature__ = sig.replace(parameters=tuple(sig.parameters.values())[1:])  # from ctx onward
    return decorator


class DraftCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.guilds_by_id = {}

    @commands.Cog.listener()
    async def on_ready(self):
        print("Bot is ready (from the Cog)")
        for guild in self.bot.guilds:
            print("Ready on guild: {n}".format(n=guild.name))
            if not guild.id in self.guilds_by_id:
                self.guilds_by_id[guild.id] = DraftGuild(guild)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        print("Joined {n}: {r}".format(n=guild.name, r=guild.roles))
        if not guild.id in self.guilds_by_id:
            self.guilds_by_id[guild.id] = DraftGuild(guild)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        print("Removed from {n}: {r}".format(n=guild.name))
        if guild.id in self.guilds_by_id:
            del self.guilds_by_id[guild.id]

    @commands.command(name='play', help='Register to play a draft')
    @inject_draft_guild
    async def play(self, draft_guild, ctx):
        player = ctx.author
        if draft_guild.is_started():
            await ctx.send("A draft is already in progress. Try later when it's over")
            return
        if draft_guild.player_not_playing(player):
            print(f"{player.display_name} is not playing, registering")
            await draft_guild.add_player(player)
            await ctx.send("{mention}, I have registered you for the next draft".format(mention=ctx.author.mention))
        else:
            print(f"{player.display_name} is already playing, not registering")
            await ctx.send("{mention}, you are already registered for the next draft".format(mention=ctx.author.mention))

    @commands.command(name='players', help='List registered players for the next draft')
    @inject_draft_guild
    async def players(self, draft_guild, ctx):
        if draft_guild.is_started():
            await ctx.send("Draft in progress. Players: {p}".format(p=", ".join([p.display_name for p in draft_guild.get_players()])))
        else:
            await ctx.send("The following players are registered for the next draft: {p}".format(p=", ".join([p.display_name for p in draft_guild.get_players()])))

    @commands.command(name='start', help="Start the draft with the current self.players")
    @inject_draft_guild
    async def start(self, draft_guild, ctx, packs:int=None, cards:int=None):
        print(f"Start received {type(packs)} {type(cards)}")
        if draft_guild.is_started():
            await ctx.send("Draft already started. Players: {p}".format(p=[p.display_name for p in draft_guild.get_players()]))
            return
        if draft_guild.is_empty():
            await ctx.send("Can't start the draft, there are no registered players")
            return
        async with ctx.typing():
            await draft_guild.start(ctx, packs, cards)


    @commands.command(name='pick', help='Pick a card from the booster')
    async def pick(self, ctx, *, card):
        draft = next((x for x in self.guilds_by_id.values() if x.has_player(ctx.author.id)), None)
        if draft is None:
            await ctx.send("You are not registered for a draft")
            return

        await draft.pick(ctx.author.id, card_name=card)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, author) -> None:
        if author == self.bot.user:
            return
        draft = next((x for x in self.guilds_by_id.values() if x.has_message(reaction.message.id)), None)
        if draft is None:
            print("Discarded reaction: {m}".format(m=reaction.message))
            return 

        await draft.pick(author.id, message_id=reaction.message.id, emoji=reaction.emoji)

