# Test that no losses are experienced when price oracle is adjusted

import boa
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from datetime import timedelta


@pytest.fixture(scope="module")
def borrowed_token(get_borrowed_token):
    return get_borrowed_token(18)


@pytest.fixture(scope="module")
def amm(collateral_token, borrowed_token, get_amm):
    return get_amm(collateral_token, borrowed_token)


@given(
    n1=st.integers(min_value=1, max_value=40),
    dn=st.integers(min_value=0, max_value=20),
    amount=st.integers(min_value=10**10, max_value=10**20),
    price_shift=st.floats(min_value=0.1, max_value=10)
)
@settings(deadline=timedelta(seconds=1000), max_examples=1000)
def test_buy_with_shift(amm, collateral_token, borrowed_token, price_oracle, accounts, admin,
                        n1, dn, amount, price_shift):
    user = accounts[1]
    collateral_amount = 10**18

    # Deposit
    with boa.env.prank(admin):
        amm.deposit_range(user, collateral_amount, n1, n1 + dn)
        collateral_token._mint_for_testing(amm.address, collateral_amount)

    # Swap stablecoin for collateral
    borrowed_token._mint_for_testing(user, amount)
    with boa.env.prank(user):
        amm.exchange(0, 1, amount, 0)
    b = borrowed_token.balanceOf(user)
    if b < amount:
        collateral_amount = collateral_token.balanceOf(user)
        assert collateral_amount != 0
    else:
        return  # No real swap

    # Shift oracle
    with boa.env.prank(admin):
        price_oracle.set_price(int(price_oracle.price() * price_shift))

    # Trade back
    collateral_token._mint_for_testing(user, 10**24)  # BIG
    with boa.env.prank(user):
        amm.exchange(1, 0, 10**24, 0)
    # Check that we cleaned up the last band
    new_b = borrowed_token.balanceOf(user)
    assert new_b > b

    # Measure profit
    profit = new_b - amount
    assert profit <= 0
