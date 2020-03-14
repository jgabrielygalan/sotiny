import asyncio
import hashlib
import os
import re
import unicodedata
import urllib.request

import aiohttp
from PIL import Image

CARD_BACK=Image.open("./card_back.jpg")
STANDALONE="standalone"
COMPOSITE="composite"

class FetchException(Exception):
    pass

async def download_image_async(cards):
    filepath = determine_filepath(cards, COMPOSITE)
    if acceptable_file(filepath):
        return filepath
    if await download_scryfall_image(cards, filepath, version='border_crop'):
        return filepath
    return None


async def download_scryfall_image(cards, filepath: str, version: str = '') -> bool:
    card_names = ', '.join(cards)
    print(f'Trying to get scryfall images for {card_names}')
    image_filepaths = []
    for c in cards:
        card_filepath = determine_filepath([c], STANDALONE)
        if not acceptable_file(card_filepath):
            await download_scryfall_card_image(c, card_filepath, version)
        if acceptable_file(card_filepath):
            image_filepaths.append(card_filepath)
    save_composite_image(image_filepaths, filepath)
    return acceptable_file(filepath)

async def download_scryfall_card_image(c, filepath: str, version: str = '') -> bool:
    try:
        await store_async(scryfall_image(c, version=version), filepath)
    except FetchException as e:
        print('Error: {e}'.format(e=e))
    return acceptable_file(filepath)


def scryfall_image(card, version: str = '') -> str:
    u = 'https://api.scryfall.com/cards/named?exact={c}&format=image'.format(c=escape(card))
    if version:
        u += '&version={v}'.format(v=escape(version))
    return u


async def store_async(url: str, path: str) -> aiohttp.ClientResponse:
    print('Async storing {url} in {path}'.format(url=url, path=path))
    try:
        async with aiohttp.ClientSession() as aios:
            response = await aios.get(url)
            with open(path, 'wb') as fout:
                while True:
                    chunk = await response.content.read(1024)
                    if not chunk:
                        break
                    fout.write(chunk)
            return response
    # type: ignore # urllib isn't fully stubbed
    except (urllib.error.HTTPError, aiohttp.ClientError) as e:
        raise FetchException(e)


def determine_filepath(cards, type, prefix: str = '') -> str:
    imagename = basename(cards)
    # Hash the filename if it's otherwise going to be too large to use.
    if len(imagename) > 240:
        imagename = hashlib.md5(imagename.encode('utf-8')).hexdigest()
    filename = imagename + '.jpg'
    directory = f"./images/{type}"
    return f'{directory}/{prefix}{filename}'

def basename(cards) -> str:
    return '_'.join(re.sub('[^a-z-]', '-', canonicalize(c)) for c in cards)

def unaccent(s: str) -> str:
    return ''.join((c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn'))

def canonicalize(name: str) -> str:
    if name.find('/') >= 0 and name.find('//') == -1:
        name = name.replace('/', '//')
    if name.find('//') >= 0 and name.find(' // ') == -1:
        name = name.replace('//', ' // ')
    name = re.sub(r' \([ab]\)$', '', name)
    # Replace ligature and smart quotes.
    name = name.replace('Æ', 'Ae').replace('“', '"').replace('”', '"').replace("'", "'").replace("'", "'")
    return unaccent(name.strip().lower())

def acceptable_file(filepath: str) -> bool:
    return os.path.isfile(filepath) and os.path.getsize(filepath) > 1000

def save_composite_image(in_filepaths, out_filepath: str) -> None:
    # Scryfall images are 480x680, so we resize them to height 445, then force an image of 5 cards wide.
    images = list(map(Image.open, in_filepaths))
    for image in images:
        aspect_ratio = image.width / image.height       # (0.7059 for 480x680)
        image.thumbnail([aspect_ratio * 445, 445])      # (314.1255x445)
    widths, heights = zip(*(i.size for i in images))
    #total_width = sum(widths)
    max_height = max(heights)
    #new_image = Image.new('RGB', (total_width, max_height))
    new_image = Image.new('RGB', (1571, max_height)) # 5 cards wide: 314.1255*5
    x_offset = 0
    for image in images:
        new_image.paste(image, (x_offset, 0))
        x_offset += image.size[0]
    for _ in range(len(images), 5):
        new_image.paste(CARD_BACK, (x_offset, 0))
        x_offset += CARD_BACK.size[0]

    new_image.save(out_filepath)

def escape(str_input: str, skip_double_slash: bool = False) -> str:
    # Expand 'AE' into two characters. This matches the legal list and
    # WotC's naming scheme in Kaladesh, and is compatible with the
    # image server and scryfall.
    s = str_input
    if skip_double_slash:
        s = s.replace('//', '-split-')
    s = urllib.parse.quote_plus(s.replace(u'Æ', 'AE')).lower() # type: ignore # urllib isn't fully stubbed
    if skip_double_slash:
        s = s.replace('-split-', '//')
    return s

if not os.path.exists('./images'):
    os.mkdir('./images')
for dirname in [STANDALONE, COMPOSITE]:
    if not os.path.exists(f'./images/{dirname}'):
        os.mkdir(f'./images/{dirname}')
