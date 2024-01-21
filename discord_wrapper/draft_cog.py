import logging
import os
from typing import Dict, List, Optional, cast

import redis.asyncio as aioredis
import interactions
from interactions import (BaseContext, ButtonStyle, Extension, InteractionContext, SlashContext, Member, Modal, ModalContext, Timestamp, slash_command)
from interactions.client.client import Client
from interactions.client.errors import CommandException, Forbidden
from interactions.models import (ActionRow, Button, IntervalTrigger, MessageFlags, ShortText, Task, check, listen)
from interactions.models.internal.checks import TYPE_CHECK_FUNCTION
from interactions.ext.prefixed_commands import PrefixedContext, prefixed_command
from interactions.ext.hybrid_commands import hybrid_slash_command

from core_draft.cog_exceptions import DMsClosedException, NoPrivateMessage, PrivateMessageOnly
from core_draft.draft_player import DraftPlayer
from core_draft.draftbot import DraftBot
from discord_wrapper import export
from discord_wrapper.discord_draft import GuildDraft
from discord_wrapper.discord_draftbot import BotMember
from discord_wrapper.guild import GuildData

SendableContext = InteractionContext | PrefixedContext

DEFAULT_PACK_NUMBER = 3
DEFAULT_CARD_NUMBER = 15

JOIN_BUTTON = Button(style=ButtonStyle.GREEN, label="JOIN", custom_id='join_draft')

def dm_only() -> TYPE_CHECK_FUNCTION:
    """This command may only be ran in a DM."""

    async def check(ctx: BaseContext) -> bool:
        if ctx.guild:
            raise PrivateMessageOnly("This command may only be ran in a DM.")
        return True

    return check

def guild_only() -> TYPE_CHECK_FUNCTION:
    """This command may only be ran in a guild."""

    async def check(ctx: BaseContext) -> bool:
        if not ctx.guild:
            raise NoPrivateMessage("This command may only be ran in a guild.")
        return True

    return check

class CubeDrafter(Extension):
    def __init__(self, bot: Client) -> None:
        self.bot = bot
        self.guilds_by_id: Dict[int, GuildData] = {}
        self.readied = False
        try:
            self.redis = aioredis.from_url(os.getenv('REDIS_URL', default='redis://localhost'), password=os.getenv('REDIS_PASSWORD'))  # type: ignore
        except ConnectionRefusedError:
            self.redis = None
            print('Could not connect to redis')

    async def get_guild(self, ctx: SendableContext) -> GuildData:
        if not ctx.guild:
            raise NoPrivateMessage
        guild = self.guilds_by_id.get(ctx.guild.id)
        if guild is None:
            return await self.setup_guild(ctx.guild)
        return guild

    @listen()
    async def on_ready(self) -> None:
        print("Bot is ready (from the Cog)")
        for guild in self.bot.guilds:
            print("Ready on guild: {n}".format(n=guild.name))
            await self.setup_guild(guild)
        self.readied = True

    @listen()
    async def on_startup(self) -> None:
        self.status.start()
        self.timeout.start()

    async def setup_guild(self, guild: interactions.Guild) -> GuildData:
        if guild.id not in self.guilds_by_id:
            self.guilds_by_id[guild.id] = GuildData(guild, self.redis)
            await self.guilds_by_id[guild.id].load_state()
        return self.guilds_by_id[guild.id]

    @listen()
    async def on_guild_join(self, event: interactions.events.GuildJoin) -> None:
        guild = event.guild
        print("Joined {n}".format(n=guild.name))
        if guild.id not in self.guilds_by_id:
            await self.setup_guild(guild)

    @listen()
    async def on_guild_left(self, event: interactions.events.GuildLeft) -> None:
        guild = event.guild
        if guild:
            print("Removed from {n}".format(n=guild.name))
            if event.guild.id in self.guilds_by_id:
                del self.guilds_by_id[int(event.guild.id)]

    @hybrid_slash_command()  # type: ignore
    @check(guild_only())
    async def play(self, ctx: PrefixedContext) -> None:
        """
        Register to play a draft
        """
        await self.register_player(ctx, True)

    async def register_player(self, ctx: SendableContext, embed: bool) -> None:
        player = cast(interactions.Member, ctx.author)  # Guild-only, so it will be a member
        guild = await self.get_guild(ctx)
        if isinstance(ctx, InteractionContext):
            flags = MessageFlags.EPHEMERAL
        else:
            flags = MessageFlags.NONE
        if player.id in guild.players:
            await ctx.send(f'You are already registered, waiting for {guild.pending_conf.max_players - len(guild.players)} more players.', flags=flags)
            return

        print(f"Registering {player.display_name} for the next draft")
        try:
            await player.fetch_dm()  # Make sure we can send DMs to this player
        except Forbidden:
            ctx.send("I can't send you DMs, please enable them so I can send you your packs.", flags=flags)

        await guild.add_player(player)
        num_players = len(guild.players)
        components = []
        if num_players == 1:
            msg = f"{player.mention}, I have registered you for a draft of "
            if embed:
                msg += f"https://cubecobra.com/cube/overview/{guild.pending_conf.cube_id}"
                components = [JOIN_BUTTON]
            else:
                msg += f"<https://cubecobra.com/cube/overview/{guild.pending_conf.cube_id}>"
        else:
            if isinstance(ctx, InteractionContext):
                await ctx.defer()
            cubeinfo = await guild.pending_conf.cubedata()
            msg = f"{player.mention}, I have registered you for the next draft of {cubeinfo.name}"
        if guild.pending_conf.max_players:
            msg = msg + f'\nYou are player {num_players} of {guild.pending_conf.max_players}'
        await ctx.send(msg, components=components)
        if guild.pending_conf.max_players == num_players:
            await guild.start(ctx)
        await guild.save_state()

    join = prefixed_command(name='join')(play.callback)

    @prefixed_command(name='leave')  # type: ignore
    @check(guild_only())
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

    @prefixed_command(name='players')   # type: ignore
    @check(guild_only())
    async def players(self, ctx: PrefixedContext):
        """List registered players for the next draft"""
        guild = await self.get_guild(ctx)

        if guild.no_registered_players():
            await ctx.send("No players registered for the next draft")
        else:
            p = ", ".join([p.nick or p.user.username for p in guild.get_registered_players()])
            msg = f"The following players are registered for the next draft: {p}\nWaiting for {guild.pending_conf.max_players - len(guild.players)} more players."
            await ctx.send(msg, components=[JOIN_BUTTON])

    @prefixed_command(name='start')  # type: ignore
    @check(guild_only())
    async def start(self, ctx: PrefixedContext) -> None:
        """"Start the draft with the registered players."""
        guild = await self.get_guild(ctx)
        if guild.no_registered_players():
            await ctx.send("Can't start the draft, there are no registered players")
            return
        await ctx.channel.trigger_typing()
        await guild.start(ctx)
        await guild.save_state()

    @interactions.listen()
    async def on_component(self, event: interactions.events.internal.Component) -> None:
        ctx = event.ctx
        if ctx.custom_id == 'join_draft':
            await self.register_player(ctx, False)
            return
        if ctx.custom_id == "pair":
            draft = await self.find_draft_by_thread(ctx)
            if draft is None:
                guild = await self.get_guild(ctx)
                draft = guild.load_draft(ctx.channel.name, True)
            await export.create_gatherling_pairings(ctx, draft, self.redis)
            return
        await ctx.defer(edit_origin=True)
        for guild in self.guilds_by_id.values():
            handled = await guild.try_pick(ctx.message_id, ctx.author.id, ctx.custom_id, ctx)
            if handled:
                await guild.save_state()

    @hybrid_slash_command(name='pending')
    async def pending(self, ctx: SendableContext) -> None:
        """
        Show players who still haven't picked
        """
        def display(player: Member | BotMember, draft: GuildDraft) -> str:
            if draft.draft is None:
                return player.display_name
            draft_player = draft.draft.player_by_id(player.id)
            if draft_player.skips > 0:
                return f'{player.display_name} ({draft_player.skips} skips)'
            return player.display_name

        prefix = ''
        drafts = await self.find_drafts_by_player(ctx)
        for draft in drafts:
            if len(drafts) > 1:
                prefix = f"{draft.guild.name}: **{draft.id()}**: "
            players = draft.get_pending_players()
            if players:
                list = ", ".join([display(player, draft) for player in players])
                await ctx.send(prefix + f"Pending players: {list}")
            else:
                await ctx.send(prefix + "No pending players")

    @hybrid_slash_command(name='deck')  # type: ignore
    @check(dm_only())
    async def my_deck(self, ctx, draft_id = None):
        """Show your current deck as images"""
        draft = await self.find_draft_or_send_error(ctx, draft_id)
        if draft is not None:
            await draft.picks(ctx, ctx.author.id)

    @hybrid_slash_command()
    async def abandon(self, ctx: PrefixedContext, draft_id: Optional[str] = None) -> None:
        """Vote to cancel an in-progress draft"""
        draft = await self.find_draft_or_send_error(ctx, draft_id)
        if draft is not None:
            if draft.start_channel_id is None:
                draft.start_channel_id = ctx.channel.id
            abandoned = await draft.abandon(ctx.author.id)

            chan = self.bot.get_channel(draft.start_channel_id) or ctx
            if abandoned:
                await chan.send(f'{draft.id()} abandoned')
            else:
                needed = min(3, len(draft.players))
                await chan.send(f'{draft.id()} needs {needed - len(draft.abandon_votes)} more votes to abandon.')
                # Alternatively, someone can take over your seat:', components=swap_seats_button(draft, ctx.author)

    @hybrid_slash_command(name='pack')
    async def my_pack(self, ctx: PrefixedContext, draft_id: Optional[str] = None) -> None:
        "Resend your current pack"
        draft = await self.find_draft_or_send_error(ctx, draft_id, True)
        if draft is None or draft.draft is None:
            return
        player = draft.draft.player_by_id(ctx.author.id)
        if player.current_pack is None:
            await ctx.send("You don't have a pack in front of you.")
            return

        await draft.send_current_pack_to_player("Your pack:", ctx.author.id)

    @hybrid_slash_command(name='drafts')
    async def my_drafts(self, ctx: PrefixedContext) -> None:
        "Show your in progress drafts"
        drafts = await self.find_drafts_by_player(ctx)
        if len(drafts) == 0:
            await ctx.send("You are not playing any draft")
        else:
            divider = "\n"
            list = divider.join([f"[{x.guild.name}:{x.id()}] {x.draft.number_of_packs} packs ({x.draft.cards_per_booster} cards). {', '.join([p.display_name for p in x.get_players()])}" for x in drafts if x.draft is not None])
            await ctx.send(f"{list}")

    @slash_command('setup-cube')
    async def setup(self, ctx: SlashContext) -> None:
        """Set up an upcoming draft"""
        guild = await self.get_guild(ctx)
        config = Modal(
            ShortText(
                label="Cube ID",
                custom_id="cube_id",
                value=guild.pending_conf.cube_id,
                required=True,
            ),
            ShortText(
                label="Number of players",
                custom_id="max_players",
                value=str(guild.pending_conf.max_players),
                required=True,
            ),
            ShortText(
                label="Number of Packs",
                custom_id="number_of_packs",
                value=str(guild.pending_conf.number_of_packs),
                required=True,
            ),
            ShortText(
                label="Cards per booster",
                custom_id="cards_per_booster",
                value=str(guild.pending_conf.cards_per_booster),
                required=True,
            ),
            # StringSelectMenu(
            #     options=['Allow Draft Bots', 'No Draft Bots'],
            # ),
            title="Setup Draft",
            custom_id='setup-cube',
        )
        print('sending modal')
        await ctx.send_modal(config)
        modal_ctx: ModalContext = await ctx.bot.wait_for_modal(config)
        print('got modal')
        print(repr(modal_ctx))

        guild = await self.get_guild(modal_ctx)
        cube_id = modal_ctx.responses['cube_id']
        max_players = int(modal_ctx.responses['max_players'])
        number_of_packs = int(modal_ctx.responses['number_of_packs'])
        cards_per_booster = int(modal_ctx.responses['cards_per_booster'])
        guild.setup(number_of_packs, cards_per_booster, cube_id, max_players)
        try:
            data = await guild.pending_conf.cubedata()
            await modal_ctx.send(f"Okay. I'll start a draft of {data.name} by {data.owner.username} (`{data.shortId}`) when we have {max_players} players",
                                 components=[JOIN_BUTTON])
        except Exception:
            await modal_ctx.send(f"Unable to load data for https://cubecobra.com/cube/overview/{cube_id}, please double-check the ID and try again.")
            raise
        await guild.save_state()

    async def find_draft_or_send_error(self, ctx: SendableContext, draft_id: Optional[str] = None, only_active: bool = False) -> GuildDraft:
        drafts = None
        if draft_id is None:
            drafts = await self.find_drafts_by_player(ctx)
            if not drafts:
                raise CommandException("You are not currently in a draft")
            if only_active:
                drafts = [d for d in drafts if d.draft and d.draft.player_by_id(ctx.author.id).current_pack]
            if not drafts:
                raise CommandException("You have no packs in front of you")
            if len(drafts) > 1:
                ids = "\n".join([f"{x.guild.name}: **{x.id()}**" for x in drafts])
                raise CommandException("You are playing in several drafts. Please specify the draft id:\n" + ids)
            else:
                return drafts[0]
        else:
            draft = self.find_draft_by_id(draft_id)
            if draft is None:
                raise CommandException("You are not playing any draft")
            return draft

    async def find_drafts_by_player(self, ctx: SendableContext) -> List[GuildDraft]:
        player = ctx.author
        if ctx.guild:  # Don't leak other guilds if invoked in a guild context.
            return (await self.get_guild(ctx)).get_drafts_for_player(player)
        drafts = []
        for guild in self.guilds_by_id.values():
            drafts.extend(guild.get_drafts_for_player(player))
        return drafts

    def find_draft_by_id(self, draft_id: str) -> Optional[GuildDraft]:
        for guild in self.guilds_by_id.values():
            draft = guild.get_draft_by_id(draft_id)
            if draft is not None:
                return draft
        return None

    async def find_draft_by_thread(self, ctx: SendableContext) -> Optional[GuildDraft]:
        for guild in self.guilds_by_id.values():
            for draft in guild.drafts_in_progress:
                if (await draft.get_thread()) == ctx.channel:
                    return draft
        return None

    @Task.create(IntervalTrigger(minutes=1))
    async def status(self) -> None:
        drafts = []
        count = 0
        for guild in self.guilds_by_id.values():
            if guild.drafts_in_progress:
                drafts.extend(guild.drafts_in_progress)
                count = count + 1
        if count == 0:
            game = '>play to start drafting'
        else:
            game = f'{len(drafts)} drafts across {len(self.guilds_by_id)} guilds.'
        await self.bot.change_presence(activity=game)

    @Task.create(IntervalTrigger(minutes=1))
    async def timeout(self) -> None:
        for guild in self.guilds_by_id.values():
            for draft in guild.drafts_in_progress:
                if not draft.draft:
                    continue  # Typeguard
                for player in draft.get_pending_players():
                    draft_player = draft.draft.player_by_id(player.id)
                    if draft_player.draftbot:
                        i = await self.draftbot_choice(draft_player)
                        await draft.pick_by_index(player.id, i)
                        continue

                    mpp = draft.messages_by_player.get(player.id)
                    if not mpp:
                        logging.warning(f'WARNING: unable to time out {player} in {draft.uuid}, no messages.')
                        continue

                    msg = list(mpp.values())[0]
                    age = (Timestamp.utcnow() - msg['message'].timestamp).total_seconds()
                    if draft_player.current_pack is None:
                        continue  # typeguard
                    elif draft_player.skips == 0:
                        timeout = 60 * 60 * 24
                    elif draft_player.skips == 1:
                        timeout = 60 * 60 * 12
                    elif draft_player.skips == 2:
                        timeout = 60 * 60 * 6
                    else:
                        timeout = 60 * 60 * 1
                    if (timeout / 2) + 60 > age > (timeout / 2):
                        print(f"{player.display_name} has been holding a pack for {age / 60} minutes")
                        await player.send(f'You have been idle for {timeout / 2 / 60 / 60} hours. After another {timeout / 2 / 60 / 60} hours, a card will be picked automatically.', reply_to=msg['message'])
                    elif age > timeout:
                        print(f"{player.display_name} has been holding a pack for {age / 60} minutes")
                        pick = str(await self.draftbot_choice(draft_player))
                        await guild.try_pick(msg['message'].id, player.id, pick, None)

                        draft_player.skips += 1
                        if draft.draft.metadata.get('total_skips') is None:
                            draft.draft.metadata['total_skips'] = {}
                        if draft.draft.metadata['total_skips'].get(player.id) is None:
                            draft.draft.metadata['total_skips'][player.id] = 0
                        draft.draft.metadata['total_skips'][player.id] += 1
                        print(f"{player.display_name} has been skipped {draft_player.skips} times")

                        if draft_player.skips > 3:
                            draft.abandon_votes.add(player.id)

    async def draftbot_choice(self, draft_player: DraftPlayer) -> int:
        if draft_player.current_pack is None:
            raise Exception("No pack to pick from")
        bot = DraftBot(draft_player)
        c = await bot.pick()
        if c is None:
            c = ""
        try:
            i = draft_player.current_pack.cards.index(c) + 1
        except ValueError:
            i = 1
        return i

def swap_seats_button(draft: GuildDraft, old_player: Member) -> ActionRow:
    button = Button(
        style=ButtonStyle.PRIMARY,
        label=f"Take {old_player.display_name}'s seat",
        custom_id=f"swap:{draft.id()[0:7]}:{old_player.id}",
    )
    return ActionRow(button)

def setup(bot: Client) -> None:
    CubeDrafter(bot)
