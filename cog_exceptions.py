from typing import Union
import discord
from discord.errors import Forbidden
from discord.ext import commands


class UserFeedbackException(commands.CommandError):
    pass

class DMsClosedException(Forbidden):
    user: Union[discord.Member, discord.User]
    def __init__(self, user: Union[discord.Member, discord.User], response, message):
        self.user = user
        super().__init__(response, message)
