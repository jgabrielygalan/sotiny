import json
from typing import Dict, List, Optional

import aiohttp
import attr
import cattr

from cog_exceptions import UserFeedbackException

SF_NAMES: Dict[str, str] = {}

@attr.s(auto_attribs=True)
class Card(object):
    cardID: str
    imgUrl: Optional[str] = None
    name: str = ''

    async def ensure_data(self) -> None:
        if not self.name:
            _name = SF_NAMES.get(self.cardID)
            if _name is None:
                _name = await fetch_name(self.cardID)
            self.name = _name

@attr.s(auto_attribs=True)
class Cube(object):
    shortID: str
    name: str
    owner_name: str
    description: str
    cards: List[Card]
    urlAlias: Optional[str] = None

    async def ensure_data(self) -> None:
        for ids in chunks(list({c.cardID for c in self.cards}), 75):
            await fetch_names(ids)
        for c in self.cards:
            await c.ensure_data()


async def fetch(session, url) -> str:
    async with session.get(url) as response:
        if response.status >= 400:
            raise UserFeedbackException(f"Unable to load {url}")
        return await response.text()

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

async def fetch_name(id: str) -> str:
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as aios:
            response = await fetch(aios, f'https://api.scryfall.com/cards/{id}')
            return json.loads(response).get('name')
    except aiohttp.ClientError as e:
        raise UserFeedbackException(f"Unable to load card name from {id}") from e

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
    except aiohttp.ClientError as e:
        raise UserFeedbackException(f"Unable to load card name from {ids}") from e

def chunks(lst: list, n: int):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]
