import os

import dotenv
from interactions import Intents, InteractionContext
from interactions.api.events import CommandError
from interactions.client.client import Client
from interactions.client.errors import CommandCheckFailure, CommandException
from interactions.ext.prefixed_commands import PrefixedHelpCommand, PrefixedContext, setup as setup_prefixed_commands
from interactions.models import listen
from interactions.client.mixins.send import SendMixin
from traceback_with_variables import activate_by_import  # noqa

from core_draft.cog_exceptions import (NoPrivateMessage, PrivateMessageOnly,
                                       UserFeedbackException)

SendableContext = InteractionContext | PrefixedContext

dotenv.load_dotenv()

if not os.path.exists('drafts'):
    os.mkdir('drafts')

if not os.path.exists('decks'):
    os.mkdir('decks')

PREFIX = os.getenv('BOT_PREFIX', default='>')

class Bot(Client):
    @listen(disable_default_listeners=True)
    async def on_command_error(self, event: CommandError) -> None:
        ctx = event.ctx
        error = event.error
        if isinstance(ctx, SendMixin):
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
                return
            else:
                await ctx.send("There was an error processing your command")
        await super().on_command_error(self, event=event)


bot = Bot(default_prefix=PREFIX, fetch_members=True, intents=Intents.DEFAULT | Intents.GUILD_MEMBERS | Intents.MESSAGE_CONTENT)
setup_prefixed_commands(bot)

@listen()
async def on_ready() -> None:
    print(f'{bot.user} has connected to Discord!')

bot.load_extension('interactions.ext.sentry', token='https://0a929451f9db4b00ac7bfbee77c3fd4e@sentry.redpoint.games/11')
bot.load_extension('interactions.ext.debug_extension')
bot.load_extension('interactions.ext.jurigged')
bot.load_extension('interactions.ext.console')
bot.load_extension('discord_wrapper.draft_cog')
bot.load_extension('dis_taipan.updater')
bot.load_extension('botguild')

help_cmd = PrefixedHelpCommand(bot)
help_cmd.register()

TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    print('Please set DISCORD_TOKEN')
else:
    bot.start(TOKEN)
