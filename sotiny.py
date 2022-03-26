import os
from typing import Any

import dotenv
from dis_snek.client.client import Snake
from dis_snek import Context, Intents
from dis_snek.client.errors import CommandCheckFailure, CommandException
from dis_snek.models import listen
from dis_taipan.protocols import SendableContext
from traceback_with_variables import activate_by_import  # noqa

from cog_exceptions import (NoPrivateMessage, PrivateMessageOnly,
                            UserFeedbackException)

dotenv.load_dotenv()

if not os.path.exists('drafts'):
    os.mkdir('drafts')

PREFIX = os.getenv('BOT_PREFIX', default='>')

class Bot(Snake):
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
                return
            elif isinstance(error, CommandException):
                await ctx.send(str(error))
            else:
                await ctx.send("There was an error processing your command")
        await super().on_command_error(ctx, error, *args, **kwargs)


bot = Bot(default_prefix=PREFIX, fetch_members=True, intents=Intents.DEFAULT | Intents.GUILD_MEMBERS)

@listen()
async def on_ready() -> None:
    print(f'{bot.user} has connected to Discord!')

bot.load_extension('dis_snek.ext.debug_scale')
bot.load_extension('draft_cog')
bot.load_extension('dis_taipan.updater')
bot.load_extension('dis_taipan.sentry')
bot.load_extension('botguild')

bot.start(os.getenv('DISCORD_TOKEN'))
