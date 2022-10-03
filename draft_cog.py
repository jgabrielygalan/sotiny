import os
from typing import Dict, List, Optional, cast

import aioredis
import naff
from naff import (ActionRow, Button, ButtonStyles, Client, Context, Extension,
                  InteractionContext, Member, Modal, ModalContext,
                  SendableContext, ShortText, Timestamp, slash_command)
from naff.client.errors import CommandException
from naff.models import IntervalTrigger, PrefixedContext, Task, check, listen
from naff.models.naff.checks import TYPE_CHECK_FUNCTION

from cog_exceptions import NoPrivateMessage, PrivateMessageOnly
from discord_draft import GuildDraft
from guild import GuildData

DEFAULT_PACK_NUMBER = 3
DEFAULT_CARD_NUMBER = 15

def dm_only() -> TYPE_CHECK_FUNCTION:
    """This command may only be ran in a DM."""

    async def check(ctx: Context) -> bool:
        if ctx.guild:
            raise PrivateMessageOnly("This command may only be ran in a DM.")
        return True

    return check

def guild_only() -> TYPE_CHECK_FUNCTION:
    """This command may only be ran in a guild."""

    async def check(ctx: Context) -> bool:
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
            self.redis = aioredis.from_url(os.getenv('REDIS_URL', default='redis://localhost'), password=os.getenv('REDIS_PASSWORD'))
        except ConnectionRefusedError:
            self.redis = None
            print('Could not connect to redis')

    async def get_guild(self, ctx: Context | SendableContext) -> GuildData:
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

    async def setup_guild(self, guild: naff.Guild) -> GuildData:
        if not guild.id in self.guilds_by_id:
            self.guilds_by_id[guild.id] = GuildData(guild, self.redis)
            await self.guilds_by_id[guild.id].load_state()
        return self.guilds_by_id[guild.id]

    @listen()
    async def on_guild_join(self, event: naff.events.GuildJoin) -> None:
        guild = event.guild
        print("Joined {n}".format(n=guild.name))
        if not guild.id in self.guilds_by_id:
            await self.setup_guild(guild)

    @listen()
    async def on_guild_left(self, event: naff.events.GuildLeft) -> None:
        guild = event.guild
        if guild:
            print("Removed from {n}".format(n=guild.name))
        if event.guild_id in self.guilds_by_id:
            del self.guilds_by_id[int(event.guild_id)]

    @naff.prefixed_command()  # type: ignore
    @check(guild_only())
    async def play(self, ctx: PrefixedContext) -> None:
        """
        Register to play a draft
        """
        await self.register_player(ctx, True)

    async def register_player(self, ctx: SendableContext, embed: bool) -> None:
        player = cast(naff.Member, ctx.author)  # Guild-only, so it will be a member
        guild = await self.get_guild(ctx)
        print(f"Registering {player.display_name} for the next draft")
        await guild.add_player(player)
        num_players = len(guild.players)
        if num_players == 1:
            msg = f"{player.mention}, I have registered you for a draft of "
            if embed:
                msg += f"https://cubecobra.com/cube/overview/{guild.pending_conf.cube_id}"
            else:
                msg += f"<https://cubecobra.com/cube/overview/{guild.pending_conf.cube_id}>"
        else:
            cubeinfo = await guild.pending_conf.cubedata()
            msg = f"{player.mention}, I have registered you for the next draft of {cubeinfo.name}"
        if guild.pending_conf.max_players:
            msg = msg + f'\nYou are player {num_players} of {guild.pending_conf.max_players}'
        await ctx.send(msg)
        if guild.pending_conf.max_players == num_players:
            await guild.start(ctx)
        await guild.save_state()

    join = naff.prefixed_command(name='join')(play.callback)

    @naff.prefixed_command(name='leave')  # type: ignore
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

    @naff.prefixed_command(name='players', help='List registered players for the next draft')   # type: ignore
    @check(guild_only())
    async def players(self, ctx):
        guild = await self.get_guild(ctx)

        if guild.no_registered_players():
            await ctx.send("No players registered for the next draft")
        else:
            await ctx.send("The following players are registered for the next draft: {p}".format(p=", ".join([p.nick or p.user.username for p in guild.get_registered_players()])))

    @naff.prefixed_command(name='start', help="Start the draft with the registered players. Packs is the number of packs to open per player (default 3). cards is the number of cards per booster (default 15). cube is the CubeCobra id of a Cube (default Penny Dreadful Eternal Cube).")  # type: ignore
    @check(guild_only())
    async def start(self, ctx: PrefixedContext) -> None:
        guild = await self.get_guild(ctx)
        if guild.no_registered_players():
            await ctx.send("Can't start the draft, there are no registered players")
            return
        await ctx.channel.trigger_typing()
        await guild.start(ctx)
        await guild.save_state()

    @naff.listen()
    async def on_component(self, event: naff.events.Component) -> None:
        ctx: naff.ComponentContext = event.context
        if ctx.custom_id == 'join_draft':
            await self.register_player(ctx, False)
            return
        await ctx.defer(edit_origin=True)
        for guild in self.guilds_by_id.values():
            handled = await guild.try_pick(ctx.message.id, ctx.author.id, ctx.custom_id, ctx)
            if handled:
                await guild.save_state()

    @naff.prefixed_command(name='pending')
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

    @naff.prefixed_command(name='deck', help="Show your current deck as images")  # type: ignore
    @check(dm_only())
    async def my_deck(self, ctx, draft_id = None):
        draft = await self.find_draft_or_send_error(ctx, draft_id)
        if draft is not None:
            await draft.picks(ctx, ctx.author.id)

    @naff.prefixed_command()
    async def abandon(self, ctx: PrefixedContext, draft_id = None):
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

    @naff.prefixed_command(name='pack', help="Resend your current pack")
    async def my_pack(self, ctx: PrefixedContext, draft_id: Optional[str] = None) -> None:
        draft = await self.find_draft_or_send_error(ctx, draft_id, True)
        if draft is None or draft.draft is None:
            return
        player = draft.draft.player_by_id(ctx.author.id)
        if player.current_pack is None:
            await ctx.send("You don't have a pack in front of you.")
            return

        await draft.send_current_pack_to_player("Your pack:", ctx.author.id)

    @naff.prefixed_command(name='drafts', help="Show your in progress drafts")
    async def my_drafts(self, ctx):
        drafts = await self.find_drafts_by_player(ctx)
        if len(drafts) == 0:
            await ctx.send("You are not playing any draft")
        else:
            divider = "\n"
            list = divider.join([f"[{x.guild.name}:{x.id()}] {x.draft.number_of_packs} packs ({x.draft.cards_per_booster} cards). {', '.join([p.display_name for p in x.get_players()])}" for x in drafts])
            await ctx.send(f"{list}")

    @naff.prefixed_command('setup')
    async def m_setup(self, ctx: PrefixedContext) -> None:
        await ctx.send('This command has been replace by `/setup-cube`')

    @slash_command('setup-cube')
    async def setup(self, ctx: InteractionContext) -> None:
        """Set up an upcoming draft"""
        guild = await self.get_guild(ctx)
        config = Modal(
            title="Setup Draft",
            custom_id='setup-cube',
            components=[
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
            ]
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
            await modal_ctx.send(f"Okay. I'll start a draft of {data.name} by {data.owner_name} (`{data.shortID}`) when we have {max_players} players",
            components=[Button(ButtonStyles.GREEN, "JOIN", custom_id='join_draft')])
        except Exception:
            await modal_ctx.send(f"Unable to load data for https://cubecobra.com/cube/overview/{cube_id}, please double-check the ID and try again.")
            raise
        await guild.save_state()

    async def find_draft_or_send_error(self, ctx, draft_id=None, only_active=False) -> GuildDraft:
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

    def find_draft_by_id(self, draft_id):
        for guild in self.guilds_by_id.values():
            draft = guild.get_draft_by_id(draft_id)
            if draft is not None:
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
                    mpp = draft.messages_by_player[player.id]
                    if not mpp:
                        print(f'WARNING: unable to time out {player} in {draft.uuid}, no messages.')
                        continue

                    draft_player = draft.draft.player_by_id(player.id)
                    msg = list(mpp.values())[0]
                    age = (Timestamp.utcnow() - msg['message'].timestamp).total_seconds()
                    if draft_player.skips == 0:
                        timeout = 60 * 60 * 24
                    elif draft_player.skips == 1:
                        timeout = 60 * 60 * 12
                    elif draft_player.skips == 2:
                        timeout = 60 * 60 * 6
                    else:
                        timeout = 60 * 60 * 1
                    if (timeout / 2) + 60 > age > (timeout / 2):
                        print(f"{player.display_name} has been holding a pack for {age / 60} minutes")
                        await player.send('You have been idle for 12 hours. After another 12 hours, a card will be picked automatically.', reply_to=msg['message'])
                    elif age > timeout:
                        print(f"{player.display_name} has been holding a pack for {age / 60} minutes")
                        await guild.try_pick(msg['message'].id, player.id, "1", None)

                        draft_player.skips += 1
                        print(f"{player.display_name} has been skipped {draft_player.skips} times")

                        if draft_player.skips > 3:
                            draft.abandon_votes.add(player.id)

def swap_seats_button(draft: GuildDraft, old_player: Member) -> ActionRow:
    button = Button(
        style=ButtonStyles.PRIMARY,
        label=f"Take {old_player.display_name}'s seat",
        custom_id=f"swap:{draft.id()[0:7]}:{old_player.id}",
    )
    return ActionRow(button)  # type: ignore

def setup(bot: Client) -> None:
    CubeDrafter(bot)
