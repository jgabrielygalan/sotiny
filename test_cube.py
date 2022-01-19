import pytest
import cube

@pytest.mark.vcr(record_mode='new_episodes')
@pytest.mark.asyncio
async def test_long_id():
    fun = await cube.load_cubecobra_cube("5d7488c28d85b07c66d22162")
    assert "Fun with Multiples" == fun.name


@pytest.mark.vcr(record_mode='new_episodes')
@pytest.mark.asyncio
async def test_a93():
    a93 = await cube.load_cubecobra_cube("a93")
    assert a93.cards
