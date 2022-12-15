from typing import TYPE_CHECKING, Any, Optional

from naff.models.discord import Message
from naff.models.discord.base import DiscordObject
from naff.models.naff.tasks import IntervalTrigger, Task

from core_draft.draftbot import DraftBot

if TYPE_CHECKING:
    from .discord_draft import GuildDraft

class BotMember(DiscordObject):
    bot: DraftBot
    draft: "GuildDraft"

    @property
    def display_name(self) -> str:
        return f'DraftBot #{self.id}'

    @property
    def mention(self) -> str:
        return f'DraftBot #{self.id}'

    @Task.create(IntervalTrigger(5))
    async def delayed_pick(self) -> None:
        if not self.draft.draft:
            return
        if not self.bot.player.current_pack:
            return

        card = await self.bot.pick()
        if card is None:
            card = ""
        i = self.bot.player.current_pack.cards.index(card) + 1  # picks are one-indexed
        self.draft.draft.pick(self.bot.player.id, i)

        if self.bot.player.current_pack is None:
            self.delayed_pick.stop()

    async def send(
        self,
        content: Optional[str] = None,
        **kwargs: Any,
    ) -> Message:
        if not self.delayed_pick.running:
            self.delayed_pick.start()
        return Message(self.draft.guild.guild._client, 0)
