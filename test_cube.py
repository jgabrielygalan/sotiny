import pytest

import core_draft.cube as cube


@pytest.mark.vcr(record_mode='new_episodes')
@pytest.mark.asyncio
async def test_long_id() -> None:
    fun = await cube.load_cubecobra_cube("5d7488c28d85b07c66d22162")
    await fun.ensure_data()
    assert "Fun with Multiples" == fun.name

@pytest.mark.vcr(record_mode='new_episodes')
@pytest.mark.asyncio
async def test_decks() -> None:
    pd = await cube.load_cubecobra_cube("penny_dreadful")
    await pd.download_decks()

@pytest.mark.vcr(record_mode='new_episodes')
@pytest.mark.asyncio
async def test_penny_dreadful() -> None:
    pd = await cube.load_cubecobra_cube("penny_dreadful")
    assert pd.cards
    assert pd.cards.mainboard

@pytest.mark.vcr(record_mode='new_episodes')
@pytest.mark.asyncio
async def test_a93() -> None:
    a93 = await cube.load_cubecobra_cube("a93")
    assert a93.cards

@pytest.mark.vcr(record_mode='new_episodes')
@pytest.mark.asyncio
async def test_mdfc_colors() -> None:
    await cube.fetch_card('Jwari Disruption // Jwari Ruins')

@pytest.mark.vcr(record_mode='new_episodes')
@pytest.mark.asyncio
async def test_ancienttimes() -> None:
    await cube.load_cubecobra_cube('ancienttimes')
