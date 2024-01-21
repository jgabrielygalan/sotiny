from datetime import datetime
import json
import logging
import os
import aiohttp
# import challonge
from interactions import ComponentContext, Member
from redis.asyncio import Redis
from core_draft.cog_exceptions import UserFeedbackException
from core_draft.fetch import fetch, post

from discord_wrapper.discord_draft import GuildDraft

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

async def create_gatherling_pairings(ctx: ComponentContext, draft: GuildDraft, redis: Redis) -> None:
    """
    Create tournament and pairings on Gatherling.
    """
    if draft.gatherling_id is not None:
        await ctx.send("http://gatherling.com/eventreport.php?event=" + draft.gatherling_id, ephemeral=True)
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

    if bad_ids:
        await ctx.send("Unable to create pairings, the following users do not have a (Gatherling)[https://gatherling.com/] account, or have not [linked](https://gatherling.com/auth.php) their discord to Gatherling:\n" + '\n'.join(p.mention for p in bad_ids))
        return

    if not draft.draft.is_draft_finished():
        # How did we get here?
        await ctx.send("Wait for the draft to finish.", ephemeral=True)
        return

    event = await create_event(draft)
    draft.gatherling_id = event['event']
    await draft.save_state(redis)
    for p in users:
        await addplayer(draft.gatherling_id, p['name'], draft.draft.deck_of(int(p['discord_id'])))
    await start_event(draft.gatherling_id)
    await ctx.send("http://gatherling.com/eventreport.php?event=" + draft.gatherling_id)


async def get_gatherling_user(p: Member) -> dict:
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as aios:

            response = await fetch(aios, f'https://gatherling.com/api.php?action=whois&discordid={p.id}')
            user = json.loads(response)
            if user.get('error'):
                logging.warning(user['error'])
                return {}

            return user
    except aiohttp.ClientError as e:
        raise UserFeedbackException("Unable to connect to gatherling") from e

async def create_event(draft: GuildDraft) -> None:
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as aios:
            headers = {
                'HTTP_X_USERNAME': os.getenv('gatherling_username'),
                'HTTP_X_APIKEY': os.getenv('gatherling_apikey'),
            }

            now = datetime.now()
            data = {
                'name': 'Cube Draft ' + draft.uuid,
                'year': now.year,
                'month': now.month,
                'day': now.day,
                'hour': now.hour,
                'format': 'Cube',
                'host': 'silasary',
                'kvalue': 'Casual',
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

            response = await post(aios, 'https://gatherling.com/api.php?action=create_event', data=data, headers=headers)
            event = json.loads(response)
            if event.get('error'):
                logging.log(event['error'])
                return {}

            return event
    except aiohttp.ClientError as e:
        raise UserFeedbackException("Unable to connect to gatherling") from e

async def addplayer(event: int, player: str, decklist: list[str]) -> bool:
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as aios:
            headers = {
                'HTTP_X_USERNAME': os.getenv('gatherling_username'),
                'HTTP_X_APIKEY': os.getenv('gatherling_apikey'),
            }

            data = {
                'event': event,
                'addplayer': player,
                'decklist': '|'.join(decklist),
            }

            response = await post(aios, 'https://gatherling.com/api.php?action=addplayer', data=data, headers=headers)
            result = json.loads(response)
            if result.get('error'):
                logging.log(result['error'])
                return False

            return True
    except aiohttp.ClientError as e:
        raise UserFeedbackException("Unable to connect to gatherling") from e

async def start_event(event: int) -> bool:
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as aios:
            headers = {
                'HTTP_X_USERNAME': os.getenv('gatherling_username'),
                'HTTP_X_APIKEY': os.getenv('gatherling_apikey'),
            }

            data = {
                'event': event,
            }

            response = await post(aios, 'https://gatherling.com/api.php?action=start_event', data=data, headers=headers)
            result = json.loads(response)
            if result.get('error'):
                logging.log(result['error'])
                return False

            return True
    except aiohttp.ClientError as e:
        raise UserFeedbackException("Unable to connect to gatherling") from e
