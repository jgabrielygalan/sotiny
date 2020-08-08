import inspect
import traceback
from typing import Callable, Dict, Optional

import discord
from discord.ext.commands.errors import CheckFailure
import discord.utils
from discord.ext import commands, flags, tasks
from discord.ext.commands import Bot, Context

import utils
from cog_exceptions import UserFeedbackException
from draft_guild import GuildDraft
from guild import Guild

DEFAULT_PACK_NUMBER = 3
DEFAULT_CARD_NUMBER = 15


class DraftCog(commands.Cog, name="CubeDrafter"):
    def __init__(self, bot: Bot, cfg: Dict[str, str]) -> None:
        self.bot = bot
        self.cfg = cfg
        self.guilds_by_id: Dict[int, Guild] = {}

    def get_guild(self, ctx: commands.Context) -> Guild:
        if not ctx.guild:
            raise commands.NoPrivateMessage()
        return self.guilds_by_id[ctx.guild.id]

    async def cog_command_error(self, ctx, error):
        print(error)
        traceback.print_exception(type(error), error, error.__traceback__)
        if isinstance(error, UserFeedbackException):
            await ctx.send(f"{ctx.author.mention}: {error}")
        elif isinstance(error, commands.PrivateMessageOnly):
            await ctx.send("That command can only be used in Private Message with the bot")
        elif isinstance(error, commands.NoPrivateMessage):
            await ctx.send("You can't use this command in a private message")
        elif isinstance(error, commands.CheckFailure):
            await ctx.send(error)
        elif isinstance(error, commands.CommandError):
            return await ctx.send(f"Error executing command `{ctx.command.name}`: {str(error)}")
        else:
            await ctx.send("There was an error processing your command")

    @commands.Cog.listener()
    async def on_ready(self):
        print("Bot is ready (from the Cog)")
        for guild in self.bot.guilds:
            print("Ready on guild: {n}".format(n=guild.name))
            if not guild.id in self.guilds_by_id:
                self.guilds_by_id[guild.id] = Guild(guild)
                if self.guilds_by_id[guild.id].role is None and guild.me.guild_permissions.manage_roles:
                    print(f'Creating CubeDrafter Role for {guild.name}')
                    role = await guild.create_role(name='CubeDrafter', reason='A role assigned to anyone currently drafting a cube')
                    self.guilds_by_id[guild.id].role = role
        self.status.start()

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
    async def play(self, ctx):
        player = ctx.author
        guild = self.get_guild(ctx)
        print(f"Registering {player.display_name} for the next draft")
        await guild.add_player(player)
        msg = f"{ctx.author.mention}, I have registered you for the next draft"
        if guild.pending_conf.max_players:
            msg = msg + f'.  You are player {len(guild.players)} of {guild.pending_conf.max_players}'
        await ctx.send(msg)
        if guild.pending_conf.max_players == len(guild.players):
            await guild.start(ctx)

    @commands.command(name='cancel', help='Cancel your registration for the draft. Only allowed before it starts')
    async def cancel(self, ctx):
        player = ctx.author
        guild = self.get_guild(ctx)
        if guild.is_player_registered(player):
            print(f"{player.display_name} cancels registration")
            await guild.remove_player(player)
            await ctx.send("{mention}, you are no longer registered for the next draft".format(mention=ctx.author.mention))
        else:
            print(f"{player.display_name} is not registered, can't cancel")
            await ctx.send("{mention}, you are not registered for the draft, I can't cancel".format(mention=ctx.author.mention))

    @commands.command(name='players', help='List registered players for the next draft')
    async def players(self, ctx):
        guild = self.get_guild(ctx)

        if guild.no_registered_players():
            await ctx.send("No players registered for the next draft")
        else:
            await ctx.send("The following players are registered for the next draft: {p}".format(p=", ".join([p.display_name for p in guild.get_registered_players()])))

    @commands.command(name='start', help="Start the draft with the registered players. Packs is the number of packs to open per player (default 3). cards is the number of cards per booster (default 15). cube is the CubeCobra id of a Cube (default Penny Dreadful Eternal Cube).")
    async def start(self, ctx):
        guild = self.get_guild(ctx)
        if guild.no_registered_players():
            await ctx.send("Can't start the draft, there are no registered players")
            return
        async with ctx.typing():
            await guild.start(ctx)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if payload.user_id == self.bot.user.id:
            return
        for guild in self.guilds_by_id.values():
            handled = await guild.try_pick_with_reaction(payload.message_id, payload.emoji.name, payload.user_id)
            if handled:
                return

    @commands.command(name='pending')
    async def pending(self, ctx, draft_id = None):
        """
        Show players who still haven't picked
        """
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
    async def my_pack(self, ctx: Context, draft_id = None):
        draft = await self.find_draft_or_send_error(ctx, draft_id)
        if draft is None:
            return
        player = draft.draft.player_by_id(ctx.author.id)
        if player.current_pack is None:
            await ctx.send("You don't have a pack in front of you.")
            return

        await draft.send_current_pack_to_player("Your pack:", ctx.author.id)

    @commands.dm_only()
    @commands.command(name='drafts', help="Show your in progress drafts")
    async def my_drafts(self, ctx):
        drafts = self.find_drafts_by_player(ctx.author)
        if len(drafts) == 0:
            await ctx.send("You are not playing any draft")
        else:
            divider = "\n"
            list = divider.join([f"[{x.guild.name}:{x.id()}] {x.packs} packs ({x.cards} cards). {', '.join([p.display_name for p in x.get_players()])}" for x in drafts])
            await ctx.send(f"{list}")

    @flags.add_flag('--packs', type=int, default=3)
    @flags.add_flag('--cards-per-pack', type=int, default=15)
    @flags.add_flag('--players', type=int, default=8)
    @flags.command(name='setup')
    async def setup(self, ctx, cube: Optional[str], **flags) -> None:
        """Set up an upcoming draft"""
        guild = self.get_guild(ctx)
        packs, cards = validate_and_cast_start_input(flags['packs'], flags['cards_per_pack'])
        guild.setup(packs, cards, cube, flags['players'])
        if cube:
            await ctx.send(f"Okay. I'll start a draft of {cube} when we have {flags['players']} players")
        else:
            await ctx.send(f"Okay. I'll start a draft when we have {flags['players']} players")


    async def find_draft_or_send_error(self, ctx, draft_id=None) -> GuildDraft:
        drafts = None
        if draft_id is None:
            drafts = self.find_drafts_by_player(ctx.author)
            if len(drafts) > 1:
                list = "\n".join([f"{x.guild.name}: **{x.id()}**" for x in drafts])
                await ctx.send("You are playing in several drafts. Please specify the draft id:")
                await ctx.send(f"{list}")
                return None
            elif len(drafts) == 0:
                raise CheckFailure("You are not playing any draft")
            else:
                return drafts[0]
        else:
            draft = self.find_draft_by_id(draft_id)
            if draft is None:
                raise CheckFailure("You are not playing any draft")
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

    @tasks.loop(seconds=60.0)
    async def status(self) -> None:
        drafts = []
        count = 0
        for guild in self.guilds_by_id.values():
            if guild.drafts_in_progress:
                drafts.extend(guild.drafts_in_progress)
                count = count + 1
        if count == 0:
            game = discord.Game('>play to start drafting')
        else:
            game = discord.Game(f'{len(drafts)} drafts across {count} guilds.')
        await self.bot.change_presence(activity=game)


def validate_and_cast_start_input(packs, cards):
    if packs is None:
        packs = DEFAULT_PACK_NUMBER
    if cards is None:
        cards = DEFAULT_CARD_NUMBER

    packs_valid = utils.safe_cast(packs, int, 0)
    if packs_valid <= 0:
        raise UserFeedbackException("packs should be a number greater than 0")
    cards_valid = utils.safe_cast(cards, int, 0)
    if cards_valid <= 1:
        raise UserFeedbackException("cards should be a number greater than 1")
    return (packs_valid, cards_valid)
