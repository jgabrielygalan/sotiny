import os
import subprocess
import sys

from discord.ext import commands, tasks


class Updater(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.commit_id = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip()
        self.branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).strip().decode()
        try:
            upstream = subprocess.check_output(['git', 'rev-parse', f'origin/{self.branch}']).decode().strip()
            if upstream == self.commit_id:
                print(f'Currently running {self.commit_id} on {self.branch}')
                self.update.start()  # pylint: disable=no-member
        except subprocess.CalledProcessError as e:
            print(e)
            pass


    @tasks.loop(minutes=5.0)
    async def update(self) -> None:
        draft_cog = self.bot.get_cog('CubeDrafter')
        for guild in draft_cog.guilds_by_id.values():
            if [d for d in guild.drafts_in_progress if d.players]:
                return
        subprocess.check_output(['git', 'fetch']).decode()
        commit_id = subprocess.check_output(['git', 'rev-parse', f'origin/{self.branch}']).decode().strip()
        if commit_id != self.commit_id:
            print(f'origin/{self.branch} at {commit_id}')
            print('Update found, shutting down')
            subprocess.check_output(['git', 'pull']).decode()
            try:
                subprocess.check_output([sys.executable, '-m', 'pipenv', 'sync']).decode()
            except Exception as c:
                print(c)
            await self.bot.close()

def setup(bot: commands.Bot) -> None:
    bot.add_cog(Updater(bot))
