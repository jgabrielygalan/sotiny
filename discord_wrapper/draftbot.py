class BotMember(DiscordObject):
    bot: DraftBot
    @Task.create(IntervalTrigger(5))
    async def delayed_pick(self) -> None:
        pick = await self.pick()
        if self.player.current_pack is None:
            self.delayed_pick.stop()

    def send(
        self,
        content: Optional[str] = None,
        *,
        components: Optional[
            Union[
                Iterable[Iterable[Union["BaseComponent", dict]]],
                Iterable[Union["BaseComponent", dict]],
                "BaseComponent",
                dict,
            ]
        ] = None,
    ):
        if not self.bot.delayed_pick.running:
            self.bot.delayed_pick.start()
