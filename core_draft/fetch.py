import logging
from core_draft.cog_exceptions import UserFeedbackException

import aiohttp


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

async def post(session: aiohttp.ClientSession, url: str, data: dict[str, str], headers: dict[str, str]) -> str:
    async with session.post(url, data=data) as response:
        if response.status >= 400:
            raise UserFeedbackException(f"Unable to load {url}")
        logging.info("Logged in as: " + response.headers.get('HTTP_X_USERNAME'))
        return await response.text()

async def post_json(session: aiohttp.ClientSession, url: str, data: dict[str, str], headers: dict[str, str]) -> str:
    async with session.post(url, data=data) as response:
        if response.status >= 400:
            raise UserFeedbackException(f"Unable to load {url}")
        return await response.json()
