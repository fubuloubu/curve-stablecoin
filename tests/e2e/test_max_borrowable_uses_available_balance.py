import pytest
import boa


@pytest.fixture(scope="module")
def collateral_decimals():
    return 18


@pytest.fixture(scope="module")
def borrowed_decimals():
    return 18


@pytest.fixture(scope="module")
def seed_liquidity():
    """Default liquidity amount used to seed markets at creation time.
    Override in tests to customize seeding.
    """
    return 0


def test_max_borrowable_uses_available_balance(
    controller, borrowed_token, collateral_decimals, market_type
):
    controller_balance = 10 ** borrowed_token.decimals()
    boa.deal(borrowed_token, controller, controller_balance)

    max_borrowable = controller.max_borrowable(10**collateral_decimals, 10)
    if market_type == "mint":
        assert max_borrowable == controller_balance
    else:
        assert max_borrowable == 0
