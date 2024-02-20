from typing import Iterable
from interactions.models import Button, ButtonStyle, ActionRow


PAIR_BUTTON = Button(style=ButtonStyle.GREEN, label="CREATE PAIRINGS", custom_id='pair')
PAIR_FORCE_BUTTON = Button(style=ButtonStyle.RED, label="CREATE PAIRINGS ANYWAY", custom_id='pair_force')

def card_buttons(cards: Iterable[str]) -> list[ActionRow]:
        return [ActionRow(
            *[  # type: ignore
                Button(style=ButtonStyle.BLUE,
                       label=c,
                       custom_id=f'{i + 1}',
                       )
                for i, c in enumerate(cards)
            ],
        )]
