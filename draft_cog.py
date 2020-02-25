from discord.ext import commands
from draft_guild import GuildDraft
from guild import Guild
import inspect
from cog_exceptions import UserFeedbackException
import traceback
import utils


DEFAULT_PACK_NUMBER = 3
DEFAULT_CARD_NUMBER = 15


def inject_guild(func):
    async def decorator(self, ctx, *args, **kwargs):
        if not ctx.guild:
            print("Context doesn't have a guild")
            await ctx.send("You can't use this command in a private message")
            return

        guild = self.guilds_by_id[ctx.guild.id]
        print(f"Found guild: {guild}")
        await func(self, guild, ctx, *args, **kwargs)

    decorator.__name__ = func.__name__
    sig = inspect.signature(func)
    decorator.__signature__ = sig.replace(parameters=tuple(sig.parameters.values())[1:])  # from ctx onward
    return decorator

class DraftCog(commands.Cog, name="CubeDrafter"):
    def __init__(self, bot, cfg):
        self.bot = bot
        self.cfg = cfg
        self.guilds_by_id = {}

    async def cog_command_error(self, ctx, error):
        print(error)
        traceback.print_exception(type(error), error, error.__traceback__)
        if isinstance(error, UserFeedbackException):
            await ctx.send(f"{ctx.author.mention}: {error}")
        elif isinstance(error, commands.PrivateMessageOnly):
            await ctx.send("That command can only be used in Private Message with the bot")
        else:
            await ctx.send("There was an error processing your command")

    @commands.Cog.listener()
    async def on_ready(self):
        print("Bot is ready (from the Cog)")
        for guild in self.bot.guilds:
            print("Ready on guild: {n}".format(n=guild.name))
            if not guild.id in self.guilds_by_id:
                self.guilds_by_id[guild.id] = Guild(guild)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        print("Joined {n}: {r}".format(n=guild.name, r=guild.roles))
        if not guild.id in self.guilds_by_id:
            self.guilds_by_id[guild.id] = Guild(guild)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        print("Removed from {n}".format(n=guild.name))
        if guild.id in self.guilds_by_id:
            del self.guilds_by_id[guild.id]

    @commands.command(name='play', help='Register to play a draft')
    @inject_guild
    async def play(self, guild: Guild, ctx):
        player = ctx.author
        print(f"Registering {player.display_name} for the next draft")
        await guild.add_player(player)
        await ctx.send("{mention}, I have registered you for the next draft".format(mention=ctx.author.mention))

    @commands.command(name='cancel', help='Cancel your registration for the draft. Only allowed before it starts')
    @inject_guild
    async def cancel(self, guild: Guild, ctx):
        player = ctx.author
        if guild.is_player_registered(player):
            print(f"{player.display_name} cancels registration")
            await guild.remove_player(player)
            await ctx.send("{mention}, you are no longer registered for the next draft".format(mention=ctx.author.mention))
        else:
            print(f"{player.display_name} is not registered, can't cancel")
            await ctx.send("{mention}, you are not registered for the draft, I can't cancel".format(mention=ctx.author.mention))

    @commands.command(name='players', help='List registered players for the next draft')
    @inject_guild
    async def players(self, guild, ctx):
        if guild.no_registered_players():
            await ctx.send("No players registered for the next draft")
        else:
            await ctx.send("The following players are registered for the next draft: {p}".format(p=", ".join([p.display_name for p in guild.get_registered_players()])))

    @commands.command(name='start', help="Start the draft with the registered players. Packs is the number of packs to open per player (default 3). cards is the number of cards per booster (default 15). cube is the CubeCobra id of a Cube (default Penny Dreadful Eternal Cube).")
    @inject_guild
    async def start(self, guild, ctx, packs=None, cards=None, cube=None):
        if guild.no_registered_players():
            await ctx.send("Can't start the draft, there are no registered players")
            return
        async with ctx.typing():
            packs, cards = validate_and_cast_start_input(packs, cards)                
            await guild.start(ctx, packs, cards, cube)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, author) -> None:
        if author == self.bot.user:
            return
        for guild in self.guilds_by_id.values():
            handled = await guild.try_pick_with_reaction(reaction, author)
            if handled:
                return

    @commands.command(name='pending', help='Show players who still haven\'t picked')
    async def pending(self, ctx, draft_id = None):
        draft = await self.find_draft_or_send_error(ctx, draft_id)
        if draft is not None:
            players = draft.get_pending_players()
            if players:
                list = ", ".join([player.display_name for player in players])
                await ctx.send(f"Pending players: {list}")
            else:
                await ctx.send("No pending players")

    @commands.dm_only()
    @commands.command(name='deck', help="Show your current deck as images")
    async def my_deck(self, ctx, draft_id = None):
        draft = await self.find_draft_or_send_error(ctx, draft_id)
        if draft is not None:
            await draft.picks(ctx, ctx.author.id)

    @commands.dm_only()
    @commands.command(name='pack', help="Resend your current pack")
    async def my_pack(self, ctx, draft_id = None):
        draft = await self.find_draft_or_send_error(ctx, draft_id)
        if draft is not None:
            await draft.send_packs_to_player("Your pack:", ctx, ctx.author.id)

    async def find_draft_or_send_error(self, ctx, draft_id=None):
        drafts = None
        if draft_id is None:
            drafts = self.find_drafts_by_player(ctx.author)
            if len(drafts) > 1:
                list = "\n".join([f"{x.guild.name}: **{x.id()}**" for x in drafts])
                await ctx.send("You are playing in several drafts. Please specify the draft id:")
                await ctx.send(f"{list}")            
                return None
            elif len(drafts) == 0:
                await ctx.send("You are not playing any draft")
                return None
            else:
                return drafts[0]
        else:
            draft = self.find_draft_by_id(draft_id)
            if draft is None:
                await ctx.send("You are not playing any draft")
            return draft

    def find_drafts_by_player(self, player):
        drafts = []
        [drafts.extend(guild.get_drafts_for_player(player)) for guild in self.guilds_by_id.values()]
        return drafts

    def find_draft_by_id(self, draft_id):
        for guild in self.guilds_by_id.values():
            draft = guild.get_draft_by_id(draft_id)
            if draft is not None:
                return draft
        return None


def validate_and_cast_start_input(packs, cards):
    if packs is None:
        packs = DEFAULT_PACK_NUMBER
    if cards is None:
        cards = DEFAULT_CARD_NUMBER

    packs_valid = utils.safe_cast(packs, int, 0)
    if packs_valid <= 0:
        raise UserFeedbackException("packs should be a number greater than 0")
    cards_valid = utils.safe_cast(cards, int, 0)
    if cards_valid <= 0:
        raise UserFeedbackException("cards should be a number greater than 0")
    return (packs_valid, cards_valid)