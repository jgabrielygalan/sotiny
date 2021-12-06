import os
import traceback
from typing import Dict, Optional, List

import aioredis
import discord
import discord.utils
from discord.ext import commands, flags, tasks
from discord.ext.commands import Bot, Context
from discord.ext.commands.context import Context
from discord.ext.commands.errors import CheckFailure

import utils
from cog_exceptions import UserFeedbackException
from discord_draft import GuildDraft
from guild import Guild

DEFAULT_PACK_NUMBER = 3
DEFAULT_CARD_NUMBER = 15


class CubeDrafter(commands.Cog):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.guilds_by_id: Dict[int, Guild] = {}
        self.redis = None
        self.readied = False

    async def get_guild(self, ctx: commands.Context) -> Guild:
        if not ctx.guild:
            raise commands.NoPrivateMessage()
        guild = self.guilds_by_id.get(ctx.guild.id)
        if guild is None:

            guild = await self.setup_guild(ctx.guild)
        return guild

    async def cog_command_error(self, ctx: Context, error) -> None:
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
            await ctx.send(f"Error executing command `{ctx.command.name}`: {str(error)}")
        else:
            await ctx.send("There was an error processing your command")

    @commands.Cog.listener()
    async def on_ready(self):
        if self.readied:
            return
        try:
            self.redis = await aioredis.create_redis_pool(os.getenv('REDIS_URL', default='redis://localhost'), password=os.getenv('REDIS_PASSWORD'))
        except ConnectionRefusedError:
            self.redis = None
            print('Could not connect to redis')

        print("Bot is ready (from the Cog)")
        for guild in self.bot.guilds:
            print("Ready on guild: {n}".format(n=guild.name))
            await self.setup_guild(guild)
        self.status.start()
        self.readied = True

    async def setup_guild(self, guild: discord.Guild) -> Guild:
        if not guild.id in self.guilds_by_id:
            self.guilds_by_id[guild.id] = Guild(guild, self.redis)
            if self.guilds_by_id[guild.id].role is None and guild.me.guild_permissions.manage_roles:
                print(f'Creating CubeDrafter Role for {guild.name}')
                role = await guild.create_role(name='CubeDrafter', reason='A role assigned to anyone currently drafting a cube')
                self.guilds_by_id[guild.id].role = role
            await self.guilds_by_id[guild.id].load_state()
        return self.guilds_by_id[guild.id]

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        print("Joined {n}: {r}".format(n=guild.name, r=guild.roles))
        if not guild.id in self.guilds_by_id:
            await self.setup_guild(guild)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        print("Removed from {n}".format(n=guild.name))
        if guild.id in self.guilds_by_id:
            del self.guilds_by_id[guild.id]

    @commands.guild_only()
    @commands.command(help='Register to play a draft', aliases=['play'])
    async def join(self, ctx: Context):
        player = ctx.author
        guild = await self.get_guild(ctx)
        print(f"Registering {player.display_name} for the next draft")
        await guild.add_player(player)
        num_players = len(guild.players)
        if num_players == 1:
            msg = f"{ctx.author.mention}, I have registered you for a draft of https://cubecobra.com/cube/overview/{guild.pending_conf.cube_id}"
        else:
            cubeinfo = await guild.pending_conf.cubedata()
            msg = f"{ctx.author.mention}, I have registered you for the next draft of {cubeinfo.name}"
        if guild.pending_conf.max_players:
            msg = msg + f'\nYou are player {num_players} of {guild.pending_conf.max_players}'
        await ctx.send(msg)
        if guild.pending_conf.max_players == num_players:
            await guild.start(ctx)
        await guild.save_state()

    @commands.guild_only()
    @commands.command(name='cancel', aliases=['leave'])
    async def cancel(self, ctx):
        """Cancel your registration for an upcoming draft."""
        player = ctx.author
        guild = await self.get_guild(ctx)
        if guild.is_player_registered(player):
            print(f"{player.display_name} cancels registration")
            await guild.remove_player(player)
            await ctx.send("{mention}, you are no longer registered for the next draft".format(mention=ctx.author.mention))
        else:
            print(f"{player.display_name} is not registered, can't cancel")
            await ctx.send("{mention}, you are not registered for the draft, I can't cancel".format(mention=ctx.author.mention))

    @commands.guild_only()
    @commands.command(name='players', help='List registered players for the next draft')
    async def players(self, ctx):
        guild = await self.get_guild(ctx)

        if guild.no_registered_players():
            await ctx.send("No players registered for the next draft")
        else:
            await ctx.send("The following players are registered for the next draft: {p}".format(p=", ".join([p.display_name for p in guild.get_registered_players()])))

    @commands.guild_only()
    @commands.command(name='start', help="Start the draft with the registered players. Packs is the number of packs to open per player (default 3). cards is the number of cards per booster (default 15). cube is the CubeCobra id of a Cube (default Penny Dreadful Eternal Cube).")
    async def start(self, ctx):
        guild = await self.get_guild(ctx)
        if guild.no_registered_players():
            await ctx.send("Can't start the draft, there are no registered players")
            return
        async with ctx.typing():
            await guild.start(ctx)
        await guild.save_state()

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if payload.user_id == self.bot.user.id:
            return
        for guild in self.guilds_by_id.values():
            handled = await guild.try_pick_with_reaction(payload.message_id, payload.emoji.name, payload.user_id)
            if handled:
                await guild.save_state()

    @commands.command(name='pending')
    async def pending(self, ctx):
        """
        Show players who still haven't picked
        """
        prefix = ''
        drafts = await self.find_drafts_by_player(ctx)
        for draft in drafts:
            if len(drafts) > 1:
                prefix = f"{draft.guild.name}: **{draft.id()}**: "
            players = draft.get_pending_players()
            if players:
                list = ", ".join([player.display_name for player in players])
                await ctx.send(prefix + f"Pending players: {list}")
            else:
                await ctx.send(prefix + "No pending players")

    @commands.dm_only()
    @commands.command(name='deck', help="Show your current deck as images")
    async def my_deck(self, ctx, draft_id = None):
        draft = await self.find_draft_or_send_error(ctx, draft_id)
        if draft is not None:
            await draft.picks(ctx, ctx.author.id)

    @commands.command()
    async def abandon(self, ctx, draft_id = None):
        """Vote to cancel an in-progress draft"""
        draft = await self.find_draft_or_send_error(ctx, draft_id)
        if draft is not None:
            draft.abandon_votes.add(ctx.author.id)
            needed = min(3, len(draft.players))
            if len(draft.abandon_votes) >= needed:
                draft.guild.drafts_in_progress.remove(draft)
                chan = self.bot.get_channel(draft.start_channel_id)
                await chan.send(f'{draft.id()} abandoned')
            else:
                await ctx.send(f'{draft.id()} needs {needed - len(draft.abandon_votes)} more votes to abandon.')



    @commands.command(name='pack', help="Resend your current pack")
    async def my_pack(self, ctx: Context, draft_id = None):
        draft = await self.find_draft_or_send_error(ctx, draft_id, True)
        if draft is None or draft.draft is None:
            return
        player = draft.draft.player_by_id(ctx.author.id)
        if player.current_pack is None:
            await ctx.send("You don't have a pack in front of you.")
            return

        await draft.send_current_pack_to_player("Your pack:", ctx.author.id)

    @commands.command(name='drafts', help="Show your in progress drafts")
    async def my_drafts(self, ctx):
        drafts = await self.find_drafts_by_player(ctx)
        if len(drafts) == 0:
            await ctx.send("You are not playing any draft")
        else:
            divider = "\n"
            list = divider.join([f"[{x.guild.name}:{x.id()}] {x.draft.number_of_packs} packs ({x.draft.cards_per_booster} cards). {', '.join([p.display_name for p in x.get_players()])}" for x in drafts])
            await ctx.send(f"{list}")

    @commands.guild_only()
    @flags.add_flag('--packs', type=int, default=3)
    @flags.add_flag('--cards-per-pack', type=int, default=15)
    @flags.add_flag('--players', type=int, default=8)
    @flags.command(name='setup')
    async def setup(self, ctx, cube: Optional[str], **flags) -> None:
        """Set up an upcoming draft"""
        guild = await self.get_guild(ctx)
        packs, cards = validate_and_cast_start_input(flags['packs'], flags['cards_per_pack'])
        guild.setup(packs, cards, cube, flags['players'])
        if cube:
            try:
                data = await guild.pending_conf.cubedata()
                await ctx.send(f"Okay. I'll start a draft of {data.name} by {data.owner_name} (`{data.shortID}`) when we have {flags['players']} players")
            except Exception:
                await ctx.send(f"Unable to load data for https://cubecobra.com/cube/overview/{cube}, please double-check the ID and try again.")
                raise
        else:
            await ctx.send(f"Okay. I'll start a draft when we have {flags['players']} players")
        await guild.save_state()


    async def find_draft_or_send_error(self, ctx, draft_id=None, only_active=False) -> GuildDraft:
        drafts = None
        if draft_id is None:
            drafts = await self.find_drafts_by_player(ctx)
            if not drafts:
                raise CheckFailure("You are not currently in a draft")
            if only_active:
                drafts = [d for d in drafts if d.draft and d.draft.player_by_id(ctx.author.id).current_pack]
            if not drafts:
                raise CheckFailure("You have no packs in front of you")
            if len(drafts) > 1:
                ids = "\n".join([f"{x.guild.name}: **{x.id()}**" for x in drafts])
                raise CheckFailure("You are playing in several drafts. Please specify the draft id:\n" + ids)
            else:
                return drafts[0]
        else:
            draft = self.find_draft_by_id(draft_id)
            if draft is None:
                raise CheckFailure("You are not playing any draft")
            return draft

    async def find_drafts_by_player(self, ctx: commands.Context) -> List[GuildDraft]:
        player = ctx.author
        if ctx.guild: # Don't leak other guilds if invoked in a guild context.
            return (await self.get_guild(ctx)).get_drafts_for_player(player)
        drafts = []
        for guild in self.guilds_by_id.values():
            drafts.extend(guild.get_drafts_for_player(player))
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
            game = discord.Game(f'{len(drafts)} drafts across {len(self.guilds_by_id)} guilds.')
        await self.bot.change_presence(activity=game)


def validate_and_cast_start_input(packs: int, cards: int):
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

def setup(bot: commands.Bot):
    bot.add_cog(CubeDrafter(bot))
