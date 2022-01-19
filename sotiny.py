import os
from dis_snek.models.listener import listen
from traceback_with_variables import activate_by_import  # noqa

import dotenv
from dis_snek import Snake

dotenv.load_dotenv()

if not os.path.exists('drafts'):
    os.mkdir('drafts')

PREFIX = os.getenv('BOT_PREFIX', default='>')
bot = Snake(default_prefix=PREFIX)
# bot.owner_ids = {154363842451734528, 323861986356232204, 411664250768195586}

@listen()
async def on_ready() -> None:
    print(f'{bot.user} has connected to Discord!')

bot.load_extension('dis_snek.debug_scale')
bot.load_extension('draft_cog')
bot.load_extension('updater')
bot.load_extension('botguild')

bot.start(os.getenv('DISCORD_TOKEN'))
