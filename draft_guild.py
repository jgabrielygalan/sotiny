import aiohttp
import asyncio
from io import BytesIO
import discord
from draft import Draft
from discord import File
import image_fetcher
import numpy
from draft import PickReturn
import urllib.request
from cog_exceptions import UserFeedbackException
import time
import uuid

EMOJIS_BY_NUMBER = {1 : '1⃣', 2 : '2⃣', 3 : '3⃣', 4 : '4⃣', 5 : '5⃣'}
NUMBERS_BY_EMOJI = {'1⃣' : 1, '2⃣' : 2, '3⃣' : 3, '4⃣' : 4, '5⃣' : 5}
DEFAULT_CUBE_CUBECOBRA_ID = "4rx"
 
class FetchException(Exception):
    pass


class GuildDraft:
    def __init__(self, guild, packs, cards, cube, players):
        self.guild = guild
        self.packs = packs
        self.cards = cards
        self.cube = cube
        self.players = players
        self.messages_by_player = {}
        self.uuid = str(uuid.uuid4()).replace('-', '')

    def id(self):
        return self.uuid
        
    def id_with_guild(self):
        return f"{self.guild.name}: {self.uuid}"

    def get_players(self):
        return self.players.values()

    def has_player(self, player):
        return player.id in self.players

    def has_message(self, message_id):
        for _, messages in self.messages_by_player.items():
            if message_id in messages:
                return True
        return False

    def get_pending_players(self):
        pending = self.draft.get_pending_players()
        players = [self.players[x] for x in pending]
        return players

    async def start(self, ctx):
        card_list = await get_card_list(self.cube)
        self.draft = Draft(list(self.players.keys()), card_list)
        for p in self.players.values():
            self.messages_by_player[p.id] = {}
        await ctx.send("Starting the draft with {p}".format(p=", ".join([p.display_name for p in self.get_players()])))
        state = self.draft.start(self.packs, self.cards, self.cube)
        if state != PickReturn.next_booster_autopick:
            intro = f"[{self.id_with_guild()}] The draft has started. Pack {self.draft.get_pick_number()}, Pick {self.draft.booster_number}:"
            await asyncio.gather(*[self.send_packs_to_player(intro, p, p.id) for p in self.get_players()])
        else:
            intro = f"[{self.id_with_guild()}] The draft has started"
            await asyncio.gather(*[self.send_packs_to_player(intro, p, p.id, False) for p in self.get_players()])
            state = self.draft.autopick()
            return await self.handle_pick_response(state, None)


    async def pick(self, player_id, card_name=None, message_id=None, emoji=None):
        if card_name is not None:
            state = self.draft.pick(player_id, card_name=card_name)
        elif message_id is not None and emoji is not None:
            page_number = self.messages_by_player[player_id][message_id]["row"]
            item_number = NUMBERS_BY_EMOJI[emoji]
            print("Player {u} reacted with {n} for row {i}".format(u=player_id, n=item_number, i=page_number))
            state = self.draft.pick(player_id, position=item_number+(5*(page_number-1)))
        else:
            print(f"Missing card_name ({card_name}) or message_id({message_id} + emoji({emoji})")
            return

        return await self.handle_pick_response(state, player_id)


    async def picks(self, messageable, player_id):
        cards = self.draft.deck_of(player_id)
        if len(cards) == 0:
            await messageable.send(f"[{self.id_with_guild()}] You haven't picked any card yet")
        else:
            await messageable.send(f"[{self.id_with_guild()}] Deck: ")
        for page in range(0,int(len(cards)/5)+1):
            l = cards[5*page:5*page+5]
            if l is not None and len(l)>0:
                image_file = await image_fetcher.download_image_async(l)
                await send_image_with_retry(messageable, image_file)

    async def send_packs_to_player(self, intro, messageable, player_id, reactions=True):
        self.messages_by_player[player_id].clear()
        async with messageable.typing():
            await messageable.send(f"[{self.id_with_guild()}] {intro}")
            cards = self.draft.pack_of(player_id).cards
            print(numpy.array(cards))
            list = numpy.array_split(numpy.array(cards),[5,10]) #split at positions 5 and 10, defaulting to empty arrays
            i = 1
            for l in list:
                if l is not None and len(l)>0:
                    image_file = await image_fetcher.download_image_async(l)
                    message = await send_image_with_retry(messageable, image_file)
                    if reactions: 
                        self.messages_by_player[player_id][message.id] = {"row": i, "message": message, "len": len(l)}
                    i += 1
            if reactions: 
                for message_info in self.messages_by_player[player_id].values():
                    for i in range(1,message_info["len"] + 1):
                        await message_info["message"].add_reaction(EMOJIS_BY_NUMBER[i])

    async def handle_pick_response(self, pick_return, player_id):
        if pick_return == PickReturn.pick_error:
            await self.players[player_id].send("That card is not in the booster")
        else:
            if player_id:
                self.messages_by_player[player_id].clear()
            if pick_return == PickReturn.in_progress:
                list = ", ".join([p.display_name for p in self.get_pending_players()])
                await self.players[player_id].send(f"[{self.id_with_guild()}] Waiting for other players to make their picks: {list}")
            elif pick_return == PickReturn.next_booster:
                await asyncio.gather(*[self.send_packs_to_player("[{guild}] Deck: {picks}\n[{guild}] Pack {pack_num}, Pick {pick_num}:\n".format(guild=self.id_with_guild(), pick_num=self.draft.get_pick_number(), pack_num=self.draft.booster_number, picks=", ".join(self.draft.deck_of(p.id))), p, p.id) for p in self.players.values()])
            elif pick_return == PickReturn.next_booster_autopick:
                await asyncio.gather(*[self.send_packs_to_player(f"[{self.id_with_guild()}] Last card of the pack:", p, p.id, False) for p in self.players.values()])
                pick_return = self.draft.autopick()
                return await self.handle_pick_response(pick_return, player_id)
            else: # end of draft
                for player in self.players.values():
                    await player.send(f"[{self.id_with_guild()}] The draft has finished")
                    content = generate_file_content(self.draft.deck_of(player.id))
                    file=BytesIO(bytes(content, 'utf-8'))
                    await player.send(content=f"[{self.id_with_guild()}] Your deck", file=File(fp=file, filename=f"{self.guild.name}_{time.strftime('%Y%m%d')}.txt"))
                self.players.clear()
                self.messages_by_player.clear()
                return pick_return

async def send_image_with_retry(user, image_file: str, text: str = '') -> None:
    message = await send(user, file=File(image_file), content=text)
    if message and message.attachments and message.attachments[0].size == 0:
        print('Message size is zero so resending')
        await message.delete()
        message = await send(user, file=File(image_file), content=text)
    return message

async def send(user, content: str, file = None) -> discord.Message:
    new_s = escape_underscores(content)
    return await user.send(file=file, content=new_s)

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

async def get_card_list(cube_name):
    if cube_name is None:
        try:
            return await load_cubecobra_cube(DEFAULT_CUBE_CUBECOBRA_ID)
        except Exception as e:
            print(e)
            return get_cards()
    else:
        return await load_cubecobra_cube(cube_name)


async def load_cubecobra_cube(cubecobra_id):
    url = f'https://cubecobra.com/cube/api/cubelist/{cubecobra_id}'
    print(f'Async fetching {url}')
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as aios:
            response = (await fetch(aios, url)).split("\n")
            print(response)
            print(f"{type(response)}")
            return response
    # type: ignore # urllib isn't fully stubbed
    except (urllib.error.HTTPError, aiohttp.ClientError):
        raise UserFeedbackException(f"Unable to load cube list from {url}")


def get_cards(file_name='EternalPennyDreadfulCube.txt'):
	with open(file_name) as f:
		read_cards = f.read().splitlines()

	return read_cards
