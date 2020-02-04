from discord.ext import commands
from draft_guild import DraftGuild
import inspect
from cog_exceptions import UserFeedbackException
import traceback
import utils
import logging


#logging.basicConfig(filename='log.txt', format='%(asctime)s-%(levelname)s: %(message)s', level=logging.INFO)

# create logger with 'spam_application'
logger = logging.getLogger('draft_cog')
logger.setLevel(logging.DEBUG)
# create file handler which logs even debug messages
fh = logging.FileHandler('test.log')
fh.setLevel(logging.DEBUG)
# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.ERROR)
# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)
# add the handlers to the logger
logger.addHandler(fh)
logger.addHandler(ch)


DEFAULT_PACK_NUMBER = 3
DEFAULT_CARD_NUMBER = 15


def inject_draft_guild(func):
    async def decorator(self, ctx, *args, **kwargs):
        if not ctx.guild:
            logger.warning("Context doesn't have a guild")
            return

        draft_guild = self.guilds_by_id[ctx.guild.id]
        logger.info(f"Found guild: {draft_guild}")
        await func(self, draft_guild, ctx, *args, **kwargs)

    decorator.__name__ = func.__name__
    sig = inspect.signature(func)
    decorator.__signature__ = sig.replace(parameters=tuple(sig.parameters.values())[1:])  # from ctx onward
    return decorator

class DraftCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.guilds_by_id = {}

    async def cog_command_error(self, ctx, error):
        logger.info(error)
        traceback.print_exception(type(error), error, error.__traceback__)
        if isinstance(error, UserFeedbackException):
            await ctx.send(f"{ctx.author.mention}: {error}")
        else:
            await ctx.send("There was an error processing your command")

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Bot is ready (from the Cog)")
        for guild in self.bot.guilds:
            logger.info("Ready on guild: {n}".format(n=guild.name))
            if not guild.id in self.guilds_by_id:
                self.guilds_by_id[guild.id] = DraftGuild(guild)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        logger.info("Joined {n}: {r}".format(n=guild.name, r=guild.roles))
        if not guild.id in self.guilds_by_id:
            self.guilds_by_id[guild.id] = DraftGuild(guild)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        logger.info("Removed from {n}: {r}".format(n=guild.name))
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
            logger.info(f"{player.display_name} is not playing, registering")
            await draft_guild.add_player(player)
            await ctx.send("{mention}, I have registered you for the next draft".format(mention=ctx.author.mention))
        else:
            logger.info(f"{player.display_name} is already playing, not registering")
            await ctx.send("{mention}, you are already registered for the next draft".format(mention=ctx.author.mention))

    @commands.command(name='players', help='List registered players for the next draft')
    @inject_draft_guild
    async def players(self, draft_guild, ctx):
        if draft_guild.is_started():
            await ctx.send("Draft in progress. Players: {p}".format(p=", ".join([p.display_name for p in draft_guild.get_players()])))
        else:
            players = draft_guild.get_players()
            if len(players) == 0:
                await ctx.send("No players registered for the next draft")
            else:
                await ctx.send("The following players are registered for the next draft: {p}".format(p=", ".join([p.display_name for p in players])))

    @commands.command(name='start', help="Start the draft with the registered players. Packs is the number of packs to open per player (default 3). cards is the number of cards per booster (default 15). cube is the CubeCobra id of a Cube (default Penny Dreadful Eternal Cube).")
    @inject_draft_guild
    async def start(self, draft_guild, ctx, packs=None, cards=None, cube=None):
        if draft_guild.is_started():
            await ctx.send("Draft already started. Players: {p}".format(p=[p.display_name for p in draft_guild.get_players()]))
            return
        if draft_guild.is_empty():
            await ctx.send("Can't start the draft, there are no registered players")
            return
        async with ctx.typing():
            packs, cards = validate_and_cast_start_input(packs, cards)                
            await draft_guild.start(ctx, packs, cards, cube)


    #@commands.command(name='pick', help='Pick a card from the booster')
    async def pick(self, ctx, *, card):
        draft = next((x for x in self.guilds_by_id.values() if x.has_player(ctx.author.id)), None)
        if draft is None:
            await ctx.send("You are not registered for a draft")
            return

        await draft.pick(ctx.author.id, card_name=card)

    @commands.command(name='picks', help="Show your current picks as a paginated image. Click the arrows for next or previous pages")
    async def my_picks(self, ctx):
        draft = next((x for x in self.guilds_by_id.values() if x.has_player(ctx.author.id)), None)
        if draft is None:
            await ctx.send("You are not playing any draft")
            return

        await draft.picks(ctx, ctx.author.id)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, author) -> None:
        if author == self.bot.user:
            return
        draft = next((x for x in self.guilds_by_id.values() if x.has_message(reaction.message.id)), None)
        if draft is None:
            logger.info("Discarded reaction: {m}".format(m=reaction.message))
            return 

        await draft.pick(author.id, message_id=reaction.message.id, emoji=reaction.emoji)


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
