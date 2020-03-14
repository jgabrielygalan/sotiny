from copy import copy
import discord
from draft_guild import GuildDraft
from draft import PickReturn


class Guild:
    def __init__(self, guild) -> None:
        self.guild = guild
        self.id = guild.id
        self.name = guild.name
        self.role = get_cubedrafter_role(guild)
        self.drafts_in_progress = []
        self.players = {} # players registered for the next draft

    async def add_player(self, player):
        self.players[player.id] = player
        if self.role is not None:
            await player.add_roles(self.role)

    async def remove_player(self, player):
        if self.role is not None:
            await player.remove_roles(self.role)
        if player.id in self.players:
            del self.players[player.id]

    def is_player_registered(self, player):
        return player.id in self.players

    def is_player_playing(self, player):
        draft = next((x for x in self.drafts_in_progress if x.has_player(player.id)), None)
        return draft != None

    def no_registered_players(self):
        return len(self.players) == 0

    def get_registered_players(self):
        return self.players.values()

    def player_exists(self, player):
        return self.is_player_playing(player) or self.is_player_registered(player)

    def get_drafts_for_player(self, player):
        return [x for x in self.drafts_in_progress if x.has_player(player)]

    def get_draft_by_id(self, draft_id):
        for x in self.drafts_in_progress:
            if x.id() == draft_id:
                return x
        return None

    async def start(self, ctx, packs, cards, cube):
        players = copy(self.players)
        self.players = {}
        draft = GuildDraft(self, packs, cards, cube, players)
        self.drafts_in_progress.append(draft)
        await draft.start(ctx)

    async def try_pick_with_reaction(self, reaction, player):
        draft = next((x for x in self.drafts_in_progress if x.has_message(reaction.message.id)), None)
        if draft is None:
            return False
        else:
            pick_return = await draft.pick(player.id, message_id=reaction.message.id, emoji=reaction.emoji)
            if pick_return == PickReturn.finished:
                self.drafts_in_progress.remove(draft)
                await self.remove_role(draft)
            return True

    async def remove_role(self, draft):
        if self.role is None:
            return
        for player in draft.get_players():
            if not self.player_exists(player):        
                if discord.utils.find(lambda m: m.name == 'CubeDrafter', player.roles):
                    await player.remove_roles(self.role)


def get_cubedrafter_role(guild: discord.Guild):
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
    return role
