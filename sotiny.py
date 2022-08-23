import os
from typing import Any

import dotenv
from naff import Context, Intents
from naff.client.client import Client
from naff.client.errors import CommandCheckFailure, CommandException
from naff.ext.prefixed_help import PrefixedHelpCommand
from naff.models import SendableContext, listen
from traceback_with_variables import activate_by_import  # noqa

from cog_exceptions import (NoPrivateMessage, PrivateMessageOnly,
                            UserFeedbackException)

dotenv.load_dotenv()

if not os.path.exists('drafts'):
    os.mkdir('drafts')

PREFIX = os.getenv('BOT_PREFIX', default='>')

class Bot(Client):
    sentry_token = 'https://ade432a5a1474198b8e1955544429250@o233010.ingest.sentry.io/6272266'

    async def on_command_error(self, ctx: Context, error: Exception, *args: Any, **kwargs: Any) -> None:
        if isinstance(ctx, SendableContext):
            if isinstance(error, UserFeedbackException):
                await ctx.send(f"{ctx.author.mention}: {error}")
                return
            elif isinstance(error, PrivateMessageOnly):
                await ctx.send("That command can only be used in Private Message with the bot")
                return
            elif isinstance(error, NoPrivateMessage):
                await ctx.send("You can't use this command in a private message")
                return
            elif isinstance(error, CommandCheckFailure):
                await ctx.send('You cannot use that command in this channel')
                # return
            elif isinstance(error, CommandException):
                await ctx.send(str(error))
                return
            else:
                await ctx.send("There was an error processing your command")
        await super().on_command_error(ctx, error, *args, **kwargs)


bot = Bot(default_prefix=PREFIX, fetch_members=True, intents=Intents.DEFAULT | Intents.GUILD_MEMBERS | Intents.GUILD_MESSAGE_CONTENT)

@listen()
async def on_ready() -> None:
    print(f'{bot.user} has connected to Discord!')

bot.load_extension('naff.ext.debug_extension')
bot.load_extension('naff.ext.sentry')
bot.load_extension('draft_cog')
# bot.load_extension('dis_taipan.updater')
# bot.load_extension('botguild')

help_cmd = PrefixedHelpCommand(bot)
help_cmd.register()

bot.start(os.getenv('DISCORD_TOKEN'))
