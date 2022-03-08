from typing import Union

from dis_snek.client.errors import CommandException, Forbidden
from dis_snek.models import Member, User


class UserFeedbackException(CommandException):
    pass

class DMsClosedException(Forbidden):
    user: Union[Member, User]

    def __init__(self, user: Union[Member, User], response, message):
        self.user = user
        super().__init__(response, message)

class NoPrivateMessage(CommandException):
    pass

class PrivateMessageOnly(CommandException):
    pass
