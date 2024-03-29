from datetime import datetime
import json
import logging
import os
import aiohttp
# import challonge
from interactions import ComponentContext, Member
from redis.asyncio import Redis
from core_draft.cog_exceptions import UserFeedbackException
from core_draft.fetch import fetch, fetch_json, post, post_json
from discord_wrapper.components import PAIR_FORCE_BUTTON

from discord_wrapper.discord_draft import GuildDraft

USER_CACHE = {}
headers = {
    'user-agent': 'sotiny/1.0',
    'X-USERNAME': os.getenv('GATHERLING_USERNAME'),
    'X-APIKEY': os.getenv('GATHERLING_APIKEY'),
}
cookie_jar = aiohttp.CookieJar(unsafe=True)
def aios_factory() -> aiohttp.ClientSession:
    timeout = aiohttp.ClientTimeout(total=10)
    auth = aiohttp.BasicAuth(os.getenv('GATHERLING_USERNAME'), os.getenv('GATHERLING_APIKEY'))
    return aiohttp.ClientSession(timeout=timeout, headers=headers, cookie_jar=cookie_jar)

# async def create_challonge_pairings(ctx: ComponentContext, draft: GuildDraft, redis: Redis) -> None:
#     """
#     Create tournament and pairings on Challonge.
#     """
#     if draft.challonge_id is not None:
#         await ctx.send("https://challonge.com/" + draft.uuid, ephemeral=True)
#         return

#     if not draft.draft.is_draft_finished():
#         # How did we get here?
#         await ctx.send("Wait for the draft to finish.", ephemeral=True)
#         return

#     api_user = os.getenv("CHALLONGE_USER")
#     api_key = os.getenv("CHALLONGE_API_KEY")

#     challonge.set_credentials(api_user, api_key)

#     tournament = challonge.tournaments.create('Cube Draft' + draft.uuid, draft.uuid, "double elimination", )
#     draft.challonge_id = tournament["id"]
#     await draft.save_state(redis)
#     await ctx.send("https://challonge.com/" + draft.uuid)
    # TODO: Add players to tournament
    # This would require email addresses, which I don't particularly want to ask for

async def create_gatherling_pairings(ctx: ComponentContext, draft: GuildDraft, redis: Redis, force: bool) -> None:
    """
    Create tournament and pairings on Gatherling.
    """
    if draft.gatherling_id is not None and draft.gatherling_id != '0':
        await ctx.send("http://gatherling.com/eventreport.php?event=" + draft.gatherling_id, ephemeral=True)
        event = await find_event(draft)
        if not event['players']:
            draft.gatherling_id = None
            await draft.save_state(redis)
        return

    await ctx.defer()
    async with aios_factory() as aios:
        whoami = await fetch_json(aios, 'https://gatherling.com/api.php?action=whoami')
    if whoami.get('error'):
        logging.error(repr(whoami))
        await ctx.send("Gatherling has not been configured correctly", ephemeral=True)
        return

    bad_ids = []
    users = []
    for p in draft.get_players():
        if p.bot:
            continue
        u = await get_gatherling_user(p)
        if u:
            users.append(u)
        else:
            bad_ids.append(p)

    if bad_ids and not force:
        await ctx.send("Unable to create pairings, the following users do not have a [Gatherling](https://gatherling.com/) account, or have not [linked](https://gatherling.com/auth.php) their discord to Gatherling:\n" + '\n'.join(p.mention for p in bad_ids), components=[PAIR_FORCE_BUTTON])
        return

    if not draft.draft.is_draft_finished():
        # How did we get here?
        await ctx.send("Wait for the draft to finish.", ephemeral=True)
        return
    event = await find_event(draft)
    if not event:
        event = await create_event(draft)
        if not event.get('id'):
            event = await find_event(draft)
    if not event.get('id'):
        await ctx.send("Error: event not created.")
        return
    draft.gatherling_id = event.get('id')
    await draft.save_state(redis)
    for p in users:
        success = await addplayer(draft.gatherling_id, p['name'], draft.draft.deck_of(int(p['discord_id'])))
        if not success:
            await ctx.send("Unable to add " + p['name'] + " to the event")
            draft.gatherling_id = None
            return
    await start_event(draft.gatherling_id)
    await ctx.send("http://gatherling.com/eventreport.php?event=" + draft.gatherling_id)


async def get_gatherling_user(p: Member) -> dict:
    if p.id in USER_CACHE:
        return USER_CACHE[p.id]
    try:
        async with aios_factory() as aios:

            response = await fetch(aios, f'https://gatherling.com/api.php?action=whois&discordid={p.id}')
            user = json.loads(response)
            if user.get('error'):
                logging.warning(user['error'])
                return {}
            USER_CACHE[p.id] = user
            return user
    except aiohttp.ClientError as e:
        raise UserFeedbackException("Unable to connect to gatherling") from e

async def find_event(draft: GuildDraft) -> dict:
    try:
        async with aios_factory() as aios:
            response = await fetch(aios, f'https://gatherling.com/api.php?action=event_info&event=Cube Draft {draft.uuid}')
            event = json.loads(response)
            if event.get('error'):
                logging.info(event['error'])
                return {}
            return event
    except aiohttp.ClientError as e:
        raise UserFeedbackException("Unable to connect to gatherling") from e

async def create_event(draft: GuildDraft) -> dict:
    try:
        async with aios_factory() as aios:
            now = datetime.now()
            data = {
                'name': 'Cube Draft ' + draft.uuid,
                'year': now.year,
                'month': now.month,
                'day': now.day,
                'hour': now.hour,
                'format': 'Cube',
                'host': os.getenv('GATHERLING_USERNAME'),
                'kvalue': '8',
                'series': 'CubeBot Drafts',
                'season': '',
                'number': '',
                'threadurl': '',
                'metaurl': '',
                'reporturl': '',
                'prereg_allowed': '0',
                'player_reportable': '1',
                'late_entry_limit': '0',
                'private': '1',
                'mainrounds': '3',
                'mainstruct': 'Swiss',
                'finalrounds': '0',
                'finalstruct': 'Single Elimination',
                'client': '3',
            }

            response = await post(aios, 'https://gatherling.com/api.php?action=create_event', data=data)
            try:
                event = json.loads(response)
                if event.get('error'):
                    logging.error(event['error'])
                    return {}
            except json.decoder.JSONDecodeError:
                logging.error("Invalid JSON:" + response)
                return {}
            return event
    except aiohttp.ClientError as e:
        raise UserFeedbackException("Unable to connect to gatherling") from e

async def addplayer(event: int, player: str, decklist: list[str]) -> bool:
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aios_factory() as aios:
            data = {
                'event': event,
                'addplayer': player,
                'decklist': '|'.join(decklist),
            }

            response = await post(aios, 'https://gatherling.com/api.php?action=addplayer', data=data)
            result = json.loads(response)
            if result.get('error'):
                logging.error(result['error'])
                return False

            return True
    except aiohttp.ClientError as e:
        raise UserFeedbackException("Unable to connect to gatherling") from e

async def start_event(event: int) -> bool:
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aios_factory() as aios:
            data = {
                'event': event,
            }

            response = await post(aios, 'https://gatherling.com/api.php?action=start_event', data=data)
            result = json.loads(response)
            if result.get('error'):
                logging.error(result['error'])
                return False

            return True
    except aiohttp.ClientError as e:
        raise UserFeedbackException("Unable to connect to gatherling") from e
