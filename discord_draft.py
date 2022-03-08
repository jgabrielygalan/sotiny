import asyncio
import json
import os
import time
import traceback
import urllib.request
import uuid
from io import BytesIO
from typing import Dict, Iterable, List, Optional, Set, TYPE_CHECKING

import aiohttp
import attr
import cattr
import dis_snek
from dis_snek.client.errors import Forbidden, NotFound
from dis_snek.client.mixins.send import SendMixin
from dis_snek.models import ActionRow, Button, ButtonStyles, DMChannel, Message, File
import numpy
from aioredis import Redis


import image_fetcher
from cog_exceptions import DMsClosedException, UserFeedbackException
from draft import (CARDS_WITH_FUNCTION, Draft, DraftEffect,
                   player_card_drafteffect)
from draft_player import DraftPlayer

if TYPE_CHECKING:
    from guild import GuildData

EMOJIS_BY_NUMBER = {1: '1⃣', 2: '2⃣', 3: '3⃣', 4: '4⃣', 5: '5⃣'}
NUMBERS_BY_EMOJI = {
    '1⃣': 1, '2⃣': 2, '3⃣': 3, '4⃣': 4, '5⃣': 5,
    '1': 1, '2': 2, '3': 3, '4': 4, '5': 5,
}
DEFAULT_CUBE_CUBECOBRA_ID = "penny_dreadful"

class FetchException(Exception):
    pass

@attr.s(auto_attribs=True)
class GuildDraft:
    """
    Discord-aware wrapper for a Draft.
    """
    guild: 'GuildData'
    players: Dict[int, dis_snek.Member] = attr.ib(factory=dict)
    uuid: str = ''
    messages_by_player: Dict[int, dict] = attr.ib(factory=dict)
    draft: Optional[Draft] = None
    abandon_votes: Set[int] = attr.ib(factory=set)

    @property
    def start_channel_id(self) -> Optional[int]:
        if self.draft:
            return self.draft.metadata.get('start_channel_id', None)
        return None

    @start_channel_id.setter
    def start_channel_id(self, value: int) -> None:
        if self.draft:
            self.draft.metadata['start_channel_id'] = value
        else:
            raise RuntimeError("Can't set start_channel_id before draft is initialized")

    def id(self) -> str:
        return self.uuid

    def id_with_guild(self) -> str:
        return f"{self.guild.name}: {self.uuid}"

    def get_players(self) -> Iterable[dis_snek.Member]:
        return self.players.values()

    def has_player(self, player) -> bool:
        return player.id in self.players

    def has_message(self, message_id: int) -> bool:
        for _, messages in self.messages_by_player.items():
            if message_id in messages:
                return True
        return False

    def get_pending_players(self):
        pending = self.draft.get_pending_players()
        return [self.players[x.id] for x in pending]

    async def start(self, channel: dis_snek.GuildText, packs: int, cards: int, cube: str):
        if not self.uuid:
            self.uuid = str(uuid.uuid4()).replace('-', '')
        card_list = await get_card_list(cube)
        self.draft = Draft(list(self.players.keys()), card_list)
        self.start_channel_id = channel.id
        for p in self.players.values():
            self.messages_by_player[p.id] = {}
        await channel.send("Starting the draft of https://cubecobra.com/cube/overview/{cube_id} with {p}".format(p=", ".join([p.display_name for p in self.get_players()]), cube_id=cube))
        players_to_update = self.draft.start(packs, cards)
        intro = "The draft has started. Pack 1, Pick 1:"
        await asyncio.gather(*[self.send_pack_to_player(intro, p) for p in players_to_update])

    async def pick(self, player_id, message_id=None, emoji: str = None) -> None:
        if message_id is not None and emoji is not None and self.draft is not None:
            page_number = self.messages_by_player[player_id][message_id]["row"]
            item_number = NUMBERS_BY_EMOJI[emoji]
            print("Player {u} reacted with {n} for row {i}".format(u=player_id, n=item_number, i=page_number))
            info = self.draft.pick(player_id, item_number + (5 * (page_number - 1)))
        else:
            print(f"Missing message_id({message_id} + emoji({emoji})")
            return

        await self.handle_pick_response(info.updates, player_id, info.draft_effect)

    async def picks(self, messageable, player_id):
        cards = self.draft.deck_of(player_id)
        if len(cards) == 0:
            await messageable.send(f"[{self.id_with_guild()}] You haven't picked any card yet")
            return
        else:
            await messageable.send(f"[{self.id_with_guild()}] Deck: ")
        for page in range(0, int(len(cards) / 5) + 1):
            row = cards[5 * page: 5 * page + 5]
            if row is not None and len(row) > 0:
                cardlist = list(row)
                image_file = await image_fetcher.download_image_async(cardlist)
                await send_image_with_retry(messageable, image_file)
        await self.send_deckfile_to_player(messageable, player_id)

    async def send_current_pack_to_player(self, intro: str, player_id: int):
        if self.draft is None:
            return
        player = self.draft.player_by_id(player_id)
        await self.send_pack_to_player(intro, player)

    async def send_pack_to_player(self, intro: str, player: DraftPlayer, reactions=False):
        if self.draft is None:
            return
        player_id = player.id
        messageable: DMChannel = self.players[player_id]
        self.messages_by_player[player_id].clear()
        try:
            await messageable.send(f"[{self.id_with_guild()}] {intro}")
        except Forbidden as e:
            raise DMsClosedException(messageable, e.response, e.text) from e
        pack = self.draft.pack_of(player_id)
        if pack is None:
            return
        cards = pack.cards
        print(numpy.array(cards))
        rows = numpy.array_split(numpy.array(cards), [5, 10])  # split at positions 5 and 10, defaulting to empty arrays
        i = 1
        for row in rows:
            if row is not None and len(row) > 0:
                image_file = await image_fetcher.download_image_async(row)
                cardrow: list[str] = list(row)
                components: list[ActionRow] = self.buttons(cardrow)
                message = await send_image_with_retry(messageable, image_file, components=components)
                self.messages_by_player[player_id][message.id] = {"row": i, "message": message, "len": len(row)}
                i += 1
        if reactions:
            messages = list(self.messages_by_player[player_id].values())
            for message_info in messages:
                for i in range(1, message_info["len"] + 1):
                    await message_info["message"].add_reaction(EMOJIS_BY_NUMBER[i])

        if actions := [a for a in player.face_up if a in CARDS_WITH_FUNCTION]:
            emoji_cog = self.guild.guild.bot.get_cog('SelfGuild')
            text = ''.join([f'{emoji_cog.get_emoji(a)} {a}' for a in actions])
            message = await messageable.send(f'Optionally activate: {text}')
            for a in actions:
                await message.add_reaction(emoji_cog.get_emoji(a))

    def buttons(self, cards: Iterable[str]) -> List[ActionRow]:
        return [ActionRow(
            *[
                Button(style=ButtonStyles.BLUE,
                       label=c,
                       custom_id=f'{i + 1}',
                       )
                for i, c in enumerate(cards)
            ],
        )]

    async def handle_pick_response(self, updates: Dict[DraftPlayer, List[str]], player_id: int, effects: List[player_card_drafteffect]) -> None:
        if self.draft is None:
            return
        if player_id:
            self.messages_by_player[player_id].clear()

        current_player_has_next_booster = False
        coroutines = []
        for effect in effects:
            player_name = self.players[effect[0].id].display_name
            text = f'{player_name} drafts {effect[1]} face up'
            if effect[1] == DraftEffect.add_booster_to_draft:
                text += ' and adds a new booster to the draft.'
            for player in self.players.values():
                coroutines.append(player.send(text))
            await self.guild.guild.fetch_channel(self.start_channel_id).send(text, file=File(await image_fetcher.download_image_async([effect[1]])))

        for player, autopicks in updates.items():
            deck = ''
            current_pack = ''

            messageable: SendMixin = self.players[player.id]
            if autopicks:
                autopick_str = ', '.join(autopicks)
                coroutines.append(messageable.send(f'[{self.id_with_guild()}] Autopicks: {autopick_str}', file=File(await image_fetcher.download_image_async(autopicks))))

            if player.has_current_pack():
                if player.id == player_id:
                    current_player_has_next_booster = True
                deck = f'Deck: {", ".join(player.deck)}\n'
                current_pack = f'Pack {player.current_pack.number}, Pick {player.current_pack.pick_number}:\n'
                intro = f"{deck}{current_pack}"
                coroutines.append(self.send_pack_to_player(intro, player))

        if not current_player_has_next_booster and not self.draft.is_draft_finished():
            list = ", ".join([p.display_name for p in self.get_pending_players()])
            coroutines.append(self.players[player_id].send(f"[{self.id_with_guild()}] Waiting for other players to make their picks: {list}"))

        await asyncio.gather(*coroutines)

        if self.draft.is_draft_finished():
            await (await self.guild.guild.fetch_channel(self.start_channel_id)).send("Finished the draft with {p}".format(p=", ".join([p.display_name for p in self.get_players()])))
            for player in self.players.values():
                await player.send(f"[{self.id_with_guild()}] The draft has finished")
                await self.send_deckfile_to_player(player, player.id)
            self.players.clear()
            self.messages_by_player.clear()

    async def send_deckfile_to_player(self, messagable: SendMixin, player_id: int) -> None:
        if self.draft is None:
            return
        content = generate_file_content(self.draft.deck_of(player_id))
        file = BytesIO(bytes(content, 'utf-8'))
        await messagable.send(content=f"[{self.id_with_guild()}] Your deck", file=File(file=file, file_name=f"{self.guild.name}_{time.strftime('%Y%m%d')}.txt"))

    async def save_state(self, redis: Redis) -> None:
        state = json.dumps(cattr.unstructure(self.draft))
        with open(os.path.join('drafts', f'{self.uuid}.json'), 'w') as f:
            f.write(state)
        await redis.set(f'draft:{self.uuid}', state, ex=2419200)

    async def load_state(self, redis: Redis) -> None:
        state = await redis.get(f'draft:{self.uuid}')
        if state is None:
            print(f'{self.uuid} could not be found')
            path = os.path.join('drafts', f'{self.uuid}.json')
            if os.path.exists(path):
                with open(path) as f:
                    state = f.read()
            else:
                return
        try:
            if isinstance(state, bytes):
                state = state.decode()
            self.draft = cattr.structure(json.loads(state), Draft)
        except Exception as e:
            print(f'{self.uuid} failed to reload\n{e}')
            traceback.print_exc()
            return

        if self.draft is None:
            print(f'{self.uuid} failed to reload?')
            return
        # await self.guild.guild.query_members(user_ids=self.draft.players)
        for player in self.draft.players:
            try:
                self.players[player] = await self.guild.guild.fetch_member(player)
                self.messages_by_player[player] = dict()
                if self.draft.player_by_id(player).current_pack is not None:
                    await self.send_current_pack_to_player("Bump: ", player)
            except NotFound:
                print(f'{self.uuid} failed to reload, {player} not found')
                return


async def send_image_with_retry(user: SendMixin, image_file: str, text: str = '', **kwargs) -> Message:
    text = escape_underscores(text)
    message = await user.send(file=image_file, content=text, **kwargs)
    if message and message.attachments and message.attachments[0].size == 0:
        print('Message size is zero so resending')
        await message.delete()
        return await user.send(file=image_file, content=text, **kwargs)
    return message


def escape_underscores(s: str) -> str:
    new_s = ''
    in_url, in_emoji = False, False
    for char in s:
        if char == ':':
            in_emoji = True
        elif char not in 'abcdefghijklmnopqrstuvwxyz_':
            in_emoji = False
        if char == '<':
            in_url = True
        elif char == '>':
            in_url = False
        if char == '_' and not in_url and not in_emoji:
            new_s += '\\_'
        else:
            new_s += char
    return new_s


def generate_file_content(cards):
    return "\n".join(["1 {c}".format(c=card) for card in cards])

async def fetch(session, url):
    async with session.get(url) as response:
        if response.status >= 400:
            raise UserFeedbackException(f"Unable to load cube list from {url}")
        return await response.text()

async def get_card_list(cube_name: str) -> List[str]:
    if cube_name == '$':
        return get_cards()
    if cube_name is None:
        try:
            return await load_cubecobra_cube(DEFAULT_CUBE_CUBECOBRA_ID)
        except Exception as e:
            print(e)
            return get_cards()
    else:
        return await load_cubecobra_cube(cube_name)


async def load_cubecobra_cube(cubecobra_id: str) -> List[str]:
    url = f'https://cubecobra.com/cube/api/cubelist/{cubecobra_id}'
    print(f'Async fetching {url}')
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as aios:
            response = (await fetch(aios, url)).split("\n")
            print(response)
            print(f"{type(response)}")
            return response
    except (urllib.error.HTTPError, aiohttp.ClientError) as e:
        raise UserFeedbackException(f"Unable to load cube list from {url}") from e


def get_cards(file_name: str = 'EternalPennyDreadfulCube.txt') -> List[str]:
    with open(file_name) as f:
        return f.read().splitlines()
