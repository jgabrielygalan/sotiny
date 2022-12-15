from copy import copy
from typing import Dict, List, Optional

import aioredis
import attr
import attrs
import naff
from naff import (ActionRow, Button, ButtonStyles, ComponentContext,
                  SendableContext)

import core_draft.cube as cube
from core_draft.cog_exceptions import DMsClosedException
from discord_wrapper.discord_draft import DEFAULT_CUBE_CUBECOBRA_ID, GuildDraft
from discord_wrapper.discord_draftbot import BotMember


@attr.s(auto_attribs=True)
class DraftSettings:
    number_of_packs: int
    cards_per_booster: int
    max_players: int
    cube_id: str

    _cubedata: Optional[cube.Cube] = None

    async def cubedata(self) -> cube.Cube:
        if self._cubedata:
            return self._cubedata
        self._cubedata = await cube.load_cubecobra_cube(self.cube_id)
        return self._cubedata

@attrs.define(init=False, auto_attribs=True)
class GuildData:
    """
    Maintains state about a Guild, and handles draft registration
    """
    guild: naff.Guild
    redis: aioredis.Redis

    id: int
    name: str
    drafts_in_progress: List[GuildDraft] = attr.ib(default=attr.Factory(list), repr=lambda drafts: '[' + ', '.join(f'Draft({d.uuid},...)' for d in drafts) + ']')
    players: Dict[int, naff.Member | BotMember] = attr.ib(default=attr.Factory(dict))
    pending_conf: DraftSettings = attr.ib(default=attr.Factory(DraftSettings))  # type: ignore

    def __init__(self, guild: naff.Guild, redis_client: aioredis.Redis) -> None:
        self.redis = redis_client
        self.guild = guild
        self.id = guild.id
        self.name = guild.name
        self.drafts_in_progress: List[GuildDraft] = []
        self.players: Dict[int, naff.Member | BotMember] = {}  # players registered for the next draft
        self.pending_conf: DraftSettings = DraftSettings(3, 15, 8, DEFAULT_CUBE_CUBECOBRA_ID)

    async def add_player(self, player: naff.Member) -> None:
        self.players[player.id] = player

    async def remove_player(self, player: naff.Member | naff.User) -> None:
        if player.id in self.players:
            del self.players[player.id]

    def is_player_registered(self, player: naff.Member) -> bool:
        return player.id in self.players

    def is_player_playing(self, player: naff.Member) -> bool:
        draft = next((x for x in self.drafts_in_progress if x.has_player(player)), None)
        return draft is not None

    def no_registered_players(self) -> bool:
        return len(self.players) == 0

    def get_registered_players(self) -> List[naff.Member | BotMember]:
        return list(self.players.values())

    def player_exists(self, player: naff.Member) -> bool:
        return self.is_player_playing(player) or self.is_player_registered(player)

    def get_drafts_for_player(self, player: naff.Member | naff.User) -> List[GuildDraft]:
        return [x for x in self.drafts_in_progress if x.has_player(player)]

    def get_draft_by_id(self, draft_id: str) -> Optional[GuildDraft]:
        for x in self.drafts_in_progress:
            if x.id() == draft_id:
                return x
        return None

    def setup(self, packs: int, cards: int, cube: Optional[str], players: int) -> None:
        if cube is None:
            cube = self.pending_conf.cube_id
        if packs is None:
            packs = self.pending_conf.number_of_packs
        if cards is None:
            cards = self.pending_conf.cards_per_booster
        if players is None:
            players = self.pending_conf.max_players
        if isinstance(packs, bytes):
            packs = int(packs.decode())
        if isinstance(cards, bytes):
            cards = int(cards.decode())
        if isinstance(cube, bytes):
            cube = cube.decode()
        if isinstance(players, bytes):
            players = int(players.decode())
        self.pending_conf = DraftSettings(packs, cards, players, cube)

    async def start(self, ctx: SendableContext) -> None:
        players = copy(self.players)
        draft = GuildDraft(self, players)
        draft.fill_bots(self.pending_conf.max_players)
        try:
            await draft.start(ctx.channel, self.pending_conf.number_of_packs, self.pending_conf.cards_per_booster, self.pending_conf.cube_id)
        except DMsClosedException as e:
            await self.remove_player(e.user)
            error = f'Could not start draft because {e.user.mention} has disabled DMs from this server. {len(self.players)} of {self.pending_conf.max_players} are now registered.'
            await ctx.channel.send(error)
            for p in self.players.values():
                await p.send(error)
            return
        self.players = {}
        self.drafts_in_progress.append(draft)

    async def try_pick(self, message_id: int, player: int, emoji: Optional[str], context: Optional[ComponentContext]) -> bool:
        if emoji is None:
            return False

        draft: Optional[GuildDraft] = next((x for x in self.drafts_in_progress if x.has_message(message_id)), None)
        if draft is None or draft.draft is None:
            return False
        else:
            messages = draft.messages_by_player[player].copy()
            await draft.pick(player, message_id=message_id, emoji=emoji)
            picked = draft.draft.deck_of(player)[-1]
            for mid, data in messages.items():
                if mid == message_id and context is not None:
                    await context.edit_origin(components=recolour_buttons(data['message'].components, picked))
                else:
                    await data['message'].edit(components=recolour_buttons(data['message'].components, picked))
            if context is not None:
                draft.draft.player_by_id(player).skips = 0
            return True

    async def save_state(self) -> None:
        if self.redis is None:
            return
        await self.redis.delete(f'sotiny:{self.guild.id}:players')
        if self.players:
            await self.redis.sadd(f'sotiny:{self.guild.id}:players', *self.players)
        if self.pending_conf.cube_id:
            await self.redis.set(f'sotiny:{self.guild.id}:cube_id', self.pending_conf.cube_id)
        await self.redis.set(f'sotiny:{self.guild.id}:number_of_packs', self.pending_conf.number_of_packs)
        await self.redis.set(f'sotiny:{self.guild.id}:cards_per_booster', self.pending_conf.cards_per_booster)
        await self.redis.set(f'sotiny:{self.guild.id}:max_players', self.pending_conf.max_players)
        if self.drafts_in_progress:
            await self.redis.sadd(f'sotiny:{self.guild.id}:active_drafts', *[d.uuid for d in self.drafts_in_progress])
        for draft in self.drafts_in_progress:
            await draft.save_state(self.redis)

    async def load_state(self) -> None:
        """
        Loads the state of the guild from redis.
        """
        if self.redis is None:
            return
        self.players.clear()
        for uid in await self.redis.smembers(f'sotiny:{self.guild.id}:players'):
            snowflake = int(uid)
            member = await self.guild.fetch_member(snowflake)
            if member is not None:
                self.players[snowflake] = member
        self.setup(
            await self.redis.get(f'sotiny:{self.guild.id}:number_of_packs'),
            await self.redis.get(f'sotiny:{self.guild.id}:cards_per_booster'),
            await self.redis.get(f'sotiny:{self.guild.id}:cube_id'),
            await self.redis.get(f'sotiny:{self.guild.id}:max_players'),
        )

        for bdraft_id in await self.redis.smembers(f'sotiny:{self.guild.id}:active_drafts'):
            draft_id = bdraft_id.decode()
            await self.load_draft(draft_id)

    async def load_draft(self, draft_id: str) -> Optional[GuildDraft]:
        """
        Loads a draft from redis.
        """
        print(f'Loading {draft_id}')
        draft = GuildDraft(self)
        draft.uuid = draft_id
        await draft.load_state(self.redis)
        if draft.draft is None or draft.draft.is_draft_finished():
            # await self.redis.srem(f'sotiny:{self.guild.id}:active_drafts', bdraft_id)
            return None
        self.drafts_in_progress.append(draft)
        return draft


def recolour_buttons(components: Optional[List[ActionRow]], green_name: Optional[str]) -> ActionRow:
    buttons = []
    if not components:
        return ActionRow()
    for c in components[0].components:
        if isinstance(c, Button):
            if c.label == green_name:
                buttons.append(Button(ButtonStyles.GREEN, c.label, c.emoji, disabled=True))
            else:
                buttons.append(Button(ButtonStyles.GREY, c.label, c.emoji, disabled=True))
    return ActionRow(*buttons)  # type: ignore
