from copy import copy
from typing import Dict, List, Optional

import aioredis
import attr
import discord

from discord_draft import DEFAULT_CUBE_CUBECOBRA_ID, GuildDraft
import cube

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



class Guild:
    """
    Maintains state about a Guild, and handles draft registration
    """
    def __init__(self, guild: discord.Guild, redis_client: aioredis.Redis) -> None:
        self.redis = redis_client
        self.guild = guild
        self.id = guild.id
        self.name = guild.name
        self.role = get_cubedrafter_role(guild)
        self.drafts_in_progress: List[GuildDraft] = []
        self.players: Dict[int, discord.Member] = {} # players registered for the next draft
        self.pending_conf: DraftSettings = DraftSettings(3, 15, 8, DEFAULT_CUBE_CUBECOBRA_ID)

    async def add_player(self, player: discord.Member) -> None:
        self.players[player.id] = player
        if self.role is not None:
            await player.add_roles(self.role)

    async def remove_player(self, player: discord.Member) -> None:
        if self.role is not None:
            await player.remove_roles(self.role)
        if player.id in self.players:
            del self.players[player.id]

    def is_player_registered(self, player: discord.Member) -> bool:
        return player.id in self.players

    def is_player_playing(self, player: discord.Member) -> bool:
        draft = next((x for x in self.drafts_in_progress if x.has_player(player.id)), None)
        return draft != None

    def no_registered_players(self) -> bool:
        return len(self.players) == 0

    def get_registered_players(self) -> List[discord.Member]:
        return list(self.players.values())

    def player_exists(self, player) -> bool:
        return self.is_player_playing(player) or self.is_player_registered(player)

    def get_drafts_for_player(self, player) -> List[GuildDraft]:
        return [x for x in self.drafts_in_progress if x.has_player(player)]

    def get_draft_by_id(self, draft_id) -> Optional[GuildDraft]:
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

    async def start(self, ctx):
        players = copy(self.players)
        draft = GuildDraft(self, players)
        await draft.start(ctx.channel, self.pending_conf.number_of_packs, self.pending_conf.cards_per_booster, self.pending_conf.cube_id)
        self.players = {}
        self.drafts_in_progress.append(draft)

    async def try_pick_with_reaction(self, message_id: int, emoji, player: int) -> bool:
        draft: Optional[GuildDraft] = next((x for x in self.drafts_in_progress if x.has_message(message_id)), None)
        if draft is None:
            return False
        else:
            await draft.pick(player, message_id=message_id, emoji=emoji)
            return True

    async def remove_role(self, draft):
        if self.role is None:
            return
        for player in draft.get_players():
            if not self.player_exists(player):
                if discord.utils.find(lambda m: m.name == 'CubeDrafter', player.roles):
                    await player.remove_roles(self.role)

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
        if self.redis is None:
            return
        self.players.clear()
        for uid in await self.redis.smembers(f'sotiny:{self.guild.id}:players'):
            snowflake = int(uid)
            member = self.guild.get_member(snowflake) or await self.guild.fetch_member(snowflake)
            if member is not None:
                self.players[snowflake] = member
        self.setup(
            await self.redis.get(f'sotiny:{self.guild.id}:number_of_packs'),
            await self.redis.get(f'sotiny:{self.guild.id}:cards_per_booster'),
            await self.redis.get(f'sotiny:{self.guild.id}:cube_id'),
            await self.redis.get(f'sotiny:{self.guild.id}:max_players')
            )

        for bdraft_id in await self.redis.smembers(f'sotiny:{self.guild.id}:active_drafts'):
            draft_id = bdraft_id.decode()
            await self.load_draft(draft_id)

    async def load_draft(self, draft_id: str) -> Optional[GuildDraft]:
            print(f'Loading {draft_id}')
            draft = GuildDraft(self)
            draft.uuid = draft_id
            await draft.load_state(self.redis)
            if draft.draft is None or draft.draft.is_draft_finished():
                # await self.redis.srem(f'sotiny:{self.guild.id}:active_drafts', bdraft_id)
                return None
            self.drafts_in_progress.append(draft)
            return draft


def get_cubedrafter_role(guild: discord.Guild) -> discord.Role:
    role = discord.utils.find(lambda m: m.name == 'CubeDrafter', guild.roles)
    if role is None:
        print("Guild {n} doesn't have the CubeDrafter role".format(n=guild.name))
        return None
    top_role = guild.me.top_role
    print(f"{role.name} at {role.position}. {top_role.name} at {top_role.position}")
    if role.position < top_role.position:
        print("Guild {n} has the CubeDrafter role with id: {i}".format(n=guild.name,i=role.id))
        return role
    else:
        print("Guild {n} has the CubeDrafter role with id: {i}, but with higher position than the bot, can't manage it".format(n=guild.name,i=role.id))
        return None
