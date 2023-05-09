from typing import TYPE_CHECKING, Union

import aiohttp
from interactions import Absent
from interactions.client.errors import CommandException, Forbidden
from interactions.models import Member, User

if TYPE_CHECKING:
    from discord_wrapper.discord_draftbot import BotMember


class UserFeedbackException(CommandException):
    pass

class DMsClosedException(Forbidden):
    user: "BotMember | Member | User"

    def __init__(self, user: Union["BotMember", Member, User], response: aiohttp.ClientResponse, message: Absent[str]) -> None:
        self.user = user
        super().__init__(response, message)

class NoPrivateMessage(CommandException):
    pass

class PrivateMessageOnly(CommandException):
    pass
