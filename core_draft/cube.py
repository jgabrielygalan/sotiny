from __future__ import annotations

import json
from typing import Any, List, Optional

import aiohttp
import attr
import cattr
from cattr.errors import ClassValidationError
import logging

from core_draft.cog_exceptions import UserFeedbackException

SF_NAMES: dict[str, str] = {}
SF_DATA: dict[str, dict] = {}
CARD_INFO: dict[str, Card] = {}

@attr.s(auto_attribs=True)
class CardDetails:
    name: str
    colors: list[str] = []

@attr.s(auto_attribs=True)
class Card(object):
    cardID: str
    details: CardDetails
    imgUrl: Optional[str] = None

    @property
    def name(self) -> str:
        return self.details.name

    @property
    def colors(self) -> list[str]:
        return self.details.colors


@attr.s(auto_attribs=True)
class CardList:
    id: str
    mainboard: List[Card]
    maybeboard: List[Card]

@attr.s(auto_attribs=True)
class Owner:
    username: str


@attr.s(auto_attribs=True)
class Cube(object):
    shortId: Optional[str]
    name: str
    owner: Owner
    description: str
    cards: CardList
    urlAlias: Optional[str] = None
    decks: Optional[list[str]] = None

    async def download_decks(self) -> None:
        if not self.decks:
            return
        for id in self.decks:
            await download_deck(id, 0)

    async def cardlist(self) -> list[str]:
        return [c.name for c in self.cards.mainboard]

async def fetch(session: aiohttp.ClientSession, url: str) -> str:
    async with session.get(url) as response:
        if response.status >= 400:
            raise UserFeedbackException(f"Unable to load {url}")
        return await response.text()

async def fetch_json(session: aiohttp.ClientSession, url: str) -> str:
    async with session.get(url) as response:
        if response.status >= 400:
            raise UserFeedbackException(f"Unable to load {url}")
        return await response.json()

async def load_cubecobra_cube(cubecobra_id: str) -> Cube:
    url = f'https://cubecobra.com/cube/api/cubejson/{cubecobra_id}'
    print(f'Async fetching {url}')
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as aios:
            response = await fetch(aios, url)
            cube: Cube = cattr.structure(json.loads(response), Cube)
            return cube
    except (aiohttp.ClientError, json.JSONDecodeError) as e:
        raise UserFeedbackException(f"Unable to load cube list from {url}") from e
    except ClassValidationError as e:
        raise UserFeedbackException(f"Unable to parse cube data from {url}:  {e}") from e


async def download_deck(id: str, seat: int) -> None:
    url = f'https://cubecobra.com/cube/deck/download/txt/{id}/{seat}'
    filename = f'decks/cc_{id}_{seat}.txt'
    print(f'Async fetching {url}')
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as aios:
            response = await fetch(aios, url)
            with open(filename, 'w') as f:
                f.write(response)
    except ClassValidationError as e:
        logging.exception(e)

async def fetch_data(id: str) -> dict[str, Any]:
    if id in SF_DATA:
        return SF_DATA[id]
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as aios:

            response = await fetch(aios, f'https://api.scryfall.com/cards/{id}')
            sf = json.loads(response)
            SF_DATA[id] = sf
            return sf
    except aiohttp.ClientError as e:
        raise UserFeedbackException(f"Unable to load card name from {id}") from e


async def fetch_name(id: str) -> str:
    sf = await fetch_data(id)
    return sf['name']

async def fetch_names(ids: List[str]) -> None:
    cat = {'identifiers': [{'id': i} for i in ids]}
    print(cat)
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as aios:
            async with aios.post('https://api.scryfall.com/cards/collection', json=cat) as response:
                if response.status >= 400:
                    print(await response.text())
                    return
            data: List[dict] = json.loads(await response.text())['data']
            SF_NAMES.update({d['id']: d['name'] for d in data})
            SF_DATA.update({d['id']: d for d in data})
    except aiohttp.ClientError as e:
        raise UserFeedbackException(f"Unable to load card name from {ids}") from e

def chunks(lst: list, n: int):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

async def fetch_card(name: str) -> Card:
    if name in CARD_INFO:
        return CARD_INFO[name]
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as aios:
            async with aios.get(f"https://api.scryfall.com/cards/named?exact={name}") as response:
                if response.status >= 400:
                    print(await response.text())
                    raise UserFeedbackException(f"Unable to load card name: {name}")
                data: dict[str, Any] = json.loads(await response.text())
                card = Card(data['id'], details=CardDetails(name=data['name'], colors=data.get('colors', [])))
                CARD_INFO[card.name] = card
                return card
    except aiohttp.ClientError as e:
        raise UserFeedbackException(f"Unable to load card name: {name}") from e
