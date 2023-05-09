import os

from dis_taipan.botguild import SelfGuild
from interactions.client.client import Client

import core_draft.image_fetcher as image_fetcher


class EmojiGuild(SelfGuild):
    async def _fetch_emoji_image(self, name: str, path: str) -> None:
        await image_fetcher.download_scryfall_card_image(name, path, 'art_crop')

def setup(bot: Client) -> None:
    if not os.path.exists('emoji_images'):
        os.mkdir('emoji_images')
    EmojiGuild(bot)
