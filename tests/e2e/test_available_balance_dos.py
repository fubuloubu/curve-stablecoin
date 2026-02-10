"""
PoC: Direct transfers to controller can break `assert available_balance >= 0`

Attack flow:
- User deposits → net_deposits increases
- User borrows → lent increases, net_deposits unchanged
- Interest accrues → debt increases
- User repays more than borrowed → repaid > lent, outstanding becomes negative
- Attacker directly transfers to controller → controller balance increases, net_deposits unchanged
- Users withdraw → net_deposits decreases, but withdrawal succeeds due to direct transfer
- After withdrawal: net_deposits - outstanding < 0 → assertion breaks
"""

import boa
import pytest
from tests.utils.constants import MAX_UINT256, MIN_TICKS
from tests.utils import max_approve


@pytest.fixture(scope="module")
def market_type():
    return "lending"


@pytest.fixture(scope="module")
def borrowed_decimals():
    return 18


@pytest.fixture(scope="module")
def collateral_decimals():
    return 18


@pytest.fixture(scope="module")
def borrow_cap():
    return MAX_UINT256


@pytest.fixture(scope="module")
def seed_liquidity():
    return 0


def test_prove_direct_transfer_breaks_invariant(
        vault,
        controller,
        amm,
        borrowed_token,
        collateral_token,
        accounts,
):
    user = accounts[1]
    user2 = accounts[2]
    attacker = accounts[3]

    # Setup users
    boa.deal(borrowed_token, user, 500 * 10 ** 18)
    boa.deal(collateral_token, user, 1000 * 10 ** 18)
    boa.deal(borrowed_token, user2, 2000 * 10 ** 18)
    boa.deal(collateral_token, user2, 1000 * 10 ** 18)

    # Step 1: Users deposit
    with boa.env.prank(user):
        max_approve(borrowed_token, vault.address)
        max_approve(borrowed_token, controller.address)
        max_approve(collateral_token, controller.address)
        vault.deposit(100 * 10 ** 18)

    with boa.env.prank(user2):
        max_approve(borrowed_token, vault.address)
        vault.deposit(200 * 10 ** 18)

    print("\n=== Step 1: After deposits ===")
    print(f"  user shares: {vault.balanceOf(user)}")
    print(f"  user2 shares: {vault.balanceOf(user2)}")
    print(f"  lent: {controller.lent()}")
    print(f"  repaid: {controller.repaid()}")
    print(f"  debt: {controller.debt(user)}")

    # Step 2: User borrows
    with boa.env.prank(user):
        controller.create_loan(600 * 10 ** 18, 250 * 10 ** 18, MIN_TICKS)

    print("\n=== Step 2: After borrow ===")
    print(f"  user shares: {vault.balanceOf(user)}")
    print(f"  user2 shares: {vault.balanceOf(user2)}")
    print(f"  lent: {controller.lent()}")
    print(f"  repaid: {controller.repaid()}")
    print(f"  debt: {controller.debt(user)}")
    print(f"  rate: {amm.rate()}")
    # Step 3: Accrue interest
    # rate_per_second = 10**18 // (365 * 86400)  # 100% APR
    # amm.eval(f"self.rate = {rate_per_second}")
    # amm.eval("self.rate_time = block.timestamp")
    boa.env.time_travel(12 * 2)
    controller.save_rate()

    debt_after_interest = controller.debt(user)

    print("\n=== Step 3: After interest accrual ===")
    print(f"  user shares: {vault.balanceOf(user)}")
    print(f"  user2 shares: {vault.balanceOf(user2)}")
    print(f"  lent: {controller.lent()}")
    print(f"  repaid: {controller.repaid()}")
    print(f"  debt: {debt_after_interest}")

    # Step 4: User repays more than borrowed (making outstanding negative)
    remaining_debt_target = 10 * 10 ** 10
    repay_amount = debt_after_interest - remaining_debt_target

    with boa.env.prank(user):
        boa.deal(borrowed_token, user, repay_amount)
        max_approve(borrowed_token, controller.address)
        controller.repay(repay_amount)

    lent_3 = controller.lent()
    repaid_3 = controller.repaid()
    outstanding_3 = int(lent_3) - int(repaid_3)
    debt_after_repay = controller.debt(user)

    assert repaid_3 > lent_3  # Outstanding is negative
    assert outstanding_3 < 0

    print("\n=== Step 4: After repay ===")
    print(f"  user shares: {vault.balanceOf(user)}")
    print(f"  user2 shares: {vault.balanceOf(user2)}")
    print(f"  lent: {lent_3}")
    print(f"  repaid: {repaid_3}")
    print(f"  debt: {debt_after_repay}")
    print(f"  outstanding: {outstanding_3} (NEGATIVE)")

    # Step 5: Attacker directly transfers to controller
    direct_transfer_amount = 100 * 10 ** 18
    print(f"  direct_transfer_amount: {direct_transfer_amount}")
    boa.deal(borrowed_token, attacker, direct_transfer_amount)
    with boa.env.prank(attacker):
        borrowed_token.transfer(controller.address, direct_transfer_amount)

    print("\n=== Step 5: After direct transfer ===")
    print(f"  user shares: {vault.balanceOf(user)}")
    print(f"  user2 shares: {vault.balanceOf(user2)}")
    print(f"  lent: {controller.lent()}")
    print(f"  repaid: {controller.repaid()}")
    print(f"  debt: {controller.debt(user)}")

    # Step 6: Both users withdraw to reduce net_deposits
    user2_shares = vault.balanceOf(user2)
    if user2_shares > 0:
        with boa.env.prank(user2):
            vault.redeem(user2_shares)

    user_shares = vault.balanceOf(user)
    assert user_shares > 0

    print("\n=== Step 6: After user2 withdrawal ===")
    print(f"  user shares: {vault.balanceOf(user)}")
    print(f"  user2 shares: {vault.balanceOf(user2)}")
    print(f"  lent: {controller.lent()}")
    print(f"  repaid: {controller.repaid()}")
    print(f"  debt: {controller.debt(user)}")

    # available_balance should still pass before withdrawal
    controller.available_balance()

    # Calculate how much we need to withdraw to break the assertion
    # We need: net_deposits_after - outstanding < 0
    # net_deposits_after = net_deposits_before - withdraw_amount
    # So: net_deposits_before - withdraw_amount - outstanding < 0
    # withdraw_amount > net_deposits_before - outstanding
    min_assets_to_break = controller.available_balance() - outstanding_3 + 1

    # Convert assets to shares needed to break assertion
    min_shares_to_redeem = vault.convertToShares(min_assets_to_break) + 1

    assert vault.maxRedeem(attacker) < min_shares_to_redeem
    with boa.reverts():
        vault.redeem(min_shares_to_redeem, sender=user)

    # Step 7: Verify assertion breaks
    remaining_user_shares = vault.balanceOf(user)

    print("\n=== Step 7: After partial user withdrawal ===")
    print(f"  user shares: {remaining_user_shares} (REMAINING)")
    print(f"  user2 shares: {vault.balanceOf(user2)}")
    print(f"  lent: {controller.lent()}")
    print(f"  repaid: {controller.repaid()}")
    print(f"  debt: {controller.debt(user)}")
    print(f"  outstanding: {outstanding_3}")
    print(f"  available_balance: {controller.available_balance()}")

    assert remaining_user_shares > 0, "User should still have shares"
    assert controller.available_balance() > 0


"""
attack flow:
- attacker deposits → net_deposits increases
- attacker borrows close to net_deposits → lent increases, net_deposits unchanged
- attacker directly transfers to controller → controller balance increases, net_deposits unchanged
- attacker withdraws to reduce net_deposits
- after withdrawal: net_deposits - outstanding < 0 → assertion breaks
"""


def test_poc_direct_transfer_breaks_invariant(
        vault,
        controller,
        amm,
        borrowed_token,
        collateral_token,
        accounts,
):
    attacker = accounts[1]
    user2 = accounts[2]
    # attacker = accounts[3]

    # Setup users
    boa.deal(borrowed_token, attacker, 500 * 10 ** 18)
    boa.deal(collateral_token, attacker, 1000 * 10 ** 18)
    boa.deal(borrowed_token, user2, 2000 * 10 ** 18)
    boa.deal(collateral_token, user2, 1000 * 10 ** 18)

    # Step 1: Users deposit
    with boa.env.prank(user2):
        max_approve(borrowed_token, vault.address)
        vault.deposit(200 * 10 ** 18)

    with boa.env.prank(attacker):
        max_approve(borrowed_token, vault.address)
        max_approve(borrowed_token, controller.address)
        max_approve(collateral_token, controller.address)
        vault.deposit(100 * 10 ** 18)

    print("\n=== Step 1: After deposits ===")
    print(f"  attacker shares: {vault.balanceOf(attacker)}")
    print(f"  user2 shares: {vault.balanceOf(user2)}")
    print(f"  lent: {controller.lent()}")
    print(f"  repaid: {controller.repaid()}")
    print(f"  debt: {controller.debt(attacker)}")

    # Step 2: attacker borrows close to net_deposits
    with boa.env.prank(attacker):
        controller.create_loan(600 * 10 ** 18, 290 * 10 ** 18, MIN_TICKS)

    print("\n=== Step 2: After borrow ===")
    print(f"  attacker shares: {vault.balanceOf(attacker)}")
    print(f"  user2 shares: {vault.balanceOf(user2)}")
    print(f"  lent: {controller.lent()}")
    print(f"  repaid: {controller.repaid()}")
    print(f"  debt: {controller.debt(attacker)}")
    print(f"  rate: {amm.rate()}")
    # Step 3: Accrue interest

    boa.env.time_travel(12 * 2)
    controller.save_rate()

    debt_after_interest = controller.debt(attacker)

    print("\n=== Step 3: After interest accrual ===")
    print(f"  attacker shares: {vault.balanceOf(attacker)}")
    print(f"  user2 shares: {vault.balanceOf(user2)}")
    print(f"  lent: {controller.lent()}")
    print(f"  repaid: {controller.repaid()}")
    print(f"  debt: {debt_after_interest}")

    # Step 4: Attacker directly transfers to controller
    direct_transfer_amount = 100 * 10 ** 18
    print(f"  direct_transfer_amount: {direct_transfer_amount}")
    boa.deal(borrowed_token, attacker, direct_transfer_amount)
    with boa.env.prank(attacker):
        borrowed_token.transfer(controller.address, direct_transfer_amount)

    print("\n=== Step 4: After direct transfer ===")
    print(f"  attacker shares: {vault.balanceOf(attacker)}")
    print(f"  user2 shares: {vault.balanceOf(user2)}")
    print(f"  lent: {controller.lent()}")
    print(f"  repaid: {controller.repaid()}")
    print(f"  debt: {controller.debt(attacker)}")

    # Step 5: attacker withdraws to reduce net_deposits

    user_shares = vault.balanceOf(attacker)
    assert user_shares > 0

    print("\n=== Step 5: After user2 withdrawal ===")
    print(f"  attacker shares: {vault.balanceOf(attacker)}")
    print(f"  user2 shares: {vault.balanceOf(user2)}")
    print(f"  lent: {controller.lent()}")
    print(f"  repaid: {controller.repaid()}")
    print(f"  debt: {controller.debt(attacker)}")

    assert vault.maxRedeem(attacker) < vault.balanceOf(attacker)
    with boa.reverts():
        vault.redeem(vault.balanceOf(attacker), sender=attacker)

    print("\n=== Step 6: After partial attacker withdrawal ===")
    print(f"  attacker shares: {vault.balanceOf(attacker)} (REMAINING)")
    print(f"  user2 shares: {vault.balanceOf(user2)}")
    print(f"  lent: {controller.lent()}")
    print(f"  repaid: {controller.repaid()}")
    print(f"  debt: {controller.debt(attacker)}")
    print(f"  outstanding: {controller.lent() - controller.repaid()}")
    print(f"  available_balance: {controller.available_balance()}")

    assert controller.available_balance() > 0
