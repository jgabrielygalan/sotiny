from typing import Union

import aiohttp
from naff import Absent
from naff.client.errors import CommandException, Forbidden
from naff.models import Member, User


class UserFeedbackException(CommandException):
    pass

class DMsClosedException(Forbidden):
    user: Union[Member, User]

    def __init__(self, user: Union[Member, User], response: aiohttp.ClientResponse, message: Absent[str]) -> None:
        self.user = user
        super().__init__(response, message)

class NoPrivateMessage(CommandException):
    pass

class PrivateMessageOnly(CommandException):
    pass
