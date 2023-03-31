from typing import TYPE_CHECKING, Any, Optional
import attrs

from naff.models.discord import Message
from naff.models.discord.base import DiscordObject
from naff.models.naff.tasks import IntervalTrigger, Task

from core_draft.draftbot import DraftBot

if TYPE_CHECKING:
    from .discord_draft import GuildDraft


RUNNING_BOTS: list["BotMember"] = []
@Task.create(IntervalTrigger(5))
async def delayed_pick() -> None:
    if not RUNNING_BOTS:
        delayed_pick.stop()
        return

    db = RUNNING_BOTS[0]
    db.delayed_pick()


@attrs.define()
class BotMember(DiscordObject):
    draft: "GuildDraft"
    bot: DraftBot | None = attrs.field(init=False)

    @property
    def display_name(self) -> str:
        return f'DraftBot #{self.id}'

    @property
    def mention(self) -> str:
        return f'DraftBot #{self.id}'

    @property
    def nick(self) -> str:
        return self.display_name

    async def send(
        self,
        content: Optional[str] = None,
        **kwargs: Any,
    ) -> Message:
        RUNNING_BOTS.append(self)
        if not delayed_pick.running:
            delayed_pick.start()
        return None

    async def delayed_pick(self) -> None:
        if not self.draft.draft:
            RUNNING_BOTS.remove(self)
            return

        if self.bot is None:
            self.bot = DraftBot(self.draft.draft.player_by_id(self.id))

        if not self.bot.player.current_pack:
            RUNNING_BOTS.remove(self)
            return

        card = await self.bot.pick()
        if card is None:
            card = ""
        i = self.bot.player.current_pack.cards.index(card) + 1  # picks are one-indexed
        self.draft.draft.pick(self.bot.player.id, i)
