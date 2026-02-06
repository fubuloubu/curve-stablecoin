import boa

from tests.utils.constants import DEAD_SHARES, MIN_SHARES_ALLOWED, MAX_UINT256


def test_min_shares(
    amm,
    collateral_token,
    admin,
    accounts
):
    user = accounts[0]
    collateral_precision = 10 ** (18 - collateral_token.decimals())
    collateral_per_band = MIN_SHARES_ALLOWED // (collateral_precision * DEAD_SHARES)
    if collateral_per_band == 0:
        collateral_per_band = 1

    boa.deal(collateral_token, user, collateral_per_band * 4)

    active_band = amm.active_band()
    with boa.env.prank(admin):
        amm.deposit_range(user, collateral_per_band * 4, active_band - 4, active_band - 1)


def test_min_shares_fails(
    amm,
    collateral_token,
    admin,
    accounts
):
    user = accounts[0]
    collateral_per_band = 1000
    boa.deal(collateral_token, user, collateral_per_band * 4)

    active_band = amm.active_band()
    collateral_precision = 10 ** (18 - collateral_token.decimals())
    with boa.env.prank(admin):
        if collateral_precision * DEAD_SHARES * collateral_per_band >= MIN_SHARES_ALLOWED:
            # doesn't fail for coins with low decimals
            amm.deposit_range(user, collateral_per_band * 4, active_band - 4, active_band - 1)
        else:
            with boa.reverts("Amount too low"):
                amm.deposit_range(user, collateral_per_band * 4, active_band - 4, active_band - 1)
