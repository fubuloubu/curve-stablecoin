import pytest
import boa
from boa.contract import BoaError
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, run_state_machine_as_test, rule, invariant
from datetime import timedelta


class BigFuzz(RuleBasedStateMachine):
    collateral_amount = st.integers(min_value=0, max_value=10**18 * 10**6 // 3000)
    loan_amount = st.integers(min_value=0, max_value=10**18 * 10**6 // 3000)
    n = st.integers(min_value=5, max_value=50)
    ratio = st.floats(min_value=0, max_value=2)

    is_pump = st.booleans()
    rate = st.integers(min_value=0, max_value=int(1e18 * 0.2 / 365 / 86400))
    oracle_step = st.floats(min_value=-0.01, max_value=0.01)

    user_id = st.integers(min_value=0, max_value=9)
    time_shift = st.integers(min_value=1, max_value=30 * 86400)

    def __init__(self):
        super().__init__()
        self.anchor = boa.env.anchor()
        self.anchor.__enter__()
        self.A = self.market_amm.A()
        # Check debt ceiling?

    # Auxiliary methods #
    def get_stablecoins(self, user):
        with boa.env.prank(self.accounts[0]):
            self.market_controller.collect_fees()
            if user != self.accounts[0]:
                amount = self.stablecoin.balanceOf(self.accounts[0])
                if amount > 0:
                    self.stablecoin.transfer(user, amount)

    def remove_stablecoins(self, user):
        if user != self.accounts[0]:
            with boa.env.prank(user):
                amount = self.stablecoin.balanceOf(user)
                if amount > 0:
                    self.stablecoin.transfer(self.accounts[0], amount)

    # Borrowing and returning #
    @rule(y=collateral_amount, n=n, uid=user_id, ratio=ratio)
    def deposit(self, y, n, ratio, uid):
        user = self.accounts[uid]
        debt = int(ratio * 3000 * y)
        with boa.env.prank(user):
            self.collateral_token._mint_for_testing(user, y)
            max_debt = self.market_controller.max_borrowable(y, n)
            if (debt > max_debt or y // n <= 100 or debt == 0
                    or self.market_controller.loan_exists(user)):
                if debt < max_debt / 0.9999:
                    try:
                        self.market_controller.create_loan(y, debt, n)
                    except Exception:
                        pass
                else:
                    with pytest.raises(Exception):
                        self.market_controller.create_loan(y, debt, n)
                return
            else:
                self.market_controller.create_loan(y, debt, n)
            self.stablecoin.transfer(self.accounts[0], debt)

    @rule(ratio=ratio, uid=user_id)
    def repay(self, ratio, uid):
        user = self.accounts[uid]
        debt = self.market_controller.debt(user)
        amount = int(ratio * debt)
        self.get_stablecoins(user)
        with boa.env.prank(user):
            if debt == 0 and amount > 0:
                with pytest.raises(BoaError):
                    self.market_controller.repay(amount, user)
            else:
                self.market_controller.repay(amount, user)
        self.remove_stablecoins(user)

    @rule(y=collateral_amount, uid=user_id)
    def add_collateral(self, y, uid):
        user = self.accounts[uid]
        exists = self.market_controller.loan_exists(user)
        if exists:
            n1, n2 = self.market_amm.read_user_tick_numbers(user)
            n0 = self.market_amm.active_band()
        self.collateral_token._mint_for_testing(user, y)

        with boa.env.prank(user):
            if (exists and n1 > n0) or y == 0:
                self.market_controller.add_collateral(y, user)
            else:
                with pytest.raises(BoaError):
                    self.market_controller.add_collateral(y, user)

    @rule(y=collateral_amount, uid=user_id, ratio=ratio)
    def rule_borrow_more(self, y, ratio, uid):
        user = self.accounts[uid]
        self.collateral_token._mint_for_testing(user, y)

        with boa.env.prank(user):
            if not self.market_controller.loan_exists(user):
                with pytest.raises(BoaError):
                    self.market_controller.borrow_more(y, 1)

            else:
                sx, sy = self.market_amm.get_sum_xy(user)
                n1, n2 = self.market_amm.read_user_tick_numbers(user)
                n = n2 - n1 + 1
                amount = int(self.market_amm.price_oracle() * (sy + y) / 1e18 * ratio)
                final_debt = self.market_controller.debt(user) + amount

                if sx == 0 or amount == 0:
                    max_debt = self.market_controller.max_borrowable(sy + y, n)
                    if final_debt > max_debt and amount > 0:
                        if final_debt < max_debt / 0.9999:
                            try:
                                self.market_controller.borrow_more(y, amount)
                            except Exception:
                                pass
                        else:
                            with pytest.raises(BoaError):
                                self.market_controller.borrow_more(y, amount)
                    else:
                        self.market_controller.borrow_more(y, amount)

                else:
                    with pytest.raises(BoaError):
                        self.market_controller.borrow_more(y, amount)

    # Trading
    def trade_to_price(self, p):
        user = self.accounts[0]
        with boa.env.prank(user):
            self.market_controller.collect_fees()
            amount, is_pump = self.market_amm.get_amount_for_price(p)
            if amount > 0:
                if is_pump:
                    self.market_amm.exchange(0, 1, amount, 0)
                else:
                    self.collateral_token._mint_for_testing(user, amount)
                    self.market_amm.exchange(1, 0, amount, 0)

    @rule(r=ratio, is_pump=is_pump, uid=user_id)
    def trade(self, r, is_pump, uid):
        user = self.accounts[uid]
        self.get_stablecoins(user)
        with boa.env.prank(user):
            if is_pump:
                b = self.stablecoin.balanceOf(user)
                amount = int(r * b)
                if r <= 1:
                    amount = min(amount, b)  # For floating point errors
                    self.market_amm.exchange(0, 1, amount, 0)
                else:
                    try:
                        self.market_amm.exchange(0, 1, amount, 0)
                    except BoaError:
                        # We may have not enough coins, but no exception if
                        # we are maxed out with the swap size
                        pass
            else:
                amount = int(r * self.collateral_token.totalSupply())
                self.collateral_token._mint_for_testing(user, amount)
                self.market_amm.exchange(1, 0, amount, 0)
        self.remove_stablecoins(user)

    # Other
    @rule(dp=oracle_step)
    def shift_oracle(self, dp):
        # Oracle shift is done via adiabatic trading which shouldn't decrease health
        if dp != 0:
            p0 = self.price_oracle.price()
            self.trade_to_price(p0)
            p = int(p0 * (1 + dp))
            with boa.env.prank(self.admin):
                self.price_oracle.set_price(p)
            self.trade_to_price(p)

    @rule(rate=rate)
    def rule_change_rate(self, rate):
        with boa.env.prank(self.admin):
            self.monetary_policy.set_rate(rate)

    @rule(dt=time_shift)
    def time_travel(self, dt):
        boa.env.vm.patch.timestamp += dt
        boa.env.vm.patch.block_number += dt // 13 + 1

    @invariant()
    def debt_supply(self):
        self.market_controller.collect_fees()
        total_debt = self.market_controller.total_debt()
        assert total_debt == self.stablecoin.totalSupply()
        assert abs(sum(self.market_controller.debt(u) for u in self.accounts) - total_debt) <= 1

    # Should be used with liquidations enabled
    # @invariant()
    # def health(self):
    #     for acc in self.accounts:
    #         if self.market_controller.loan_exists(acc):
    #             assert self.market_controller.health(acc) > 0

    def teardown(self):
        self.anchor.__exit__(None, None, None)


def test_big_fuzz(
        market_amm, market_controller, monetary_policy, collateral_token, stablecoin, price_oracle, accounts, admin):
    BigFuzz.TestCase.settings = settings(max_examples=2500, stateful_step_count=20, deadline=timedelta(seconds=1000))
    for k, v in locals().items():
        setattr(BigFuzz, k, v)
    run_state_machine_as_test(BigFuzz)


def test_noraise(
        market_amm, market_controller, monetary_policy, collateral_token, stablecoin, price_oracle, accounts, admin):
    for k, v in locals().items():
        setattr(BigFuzz, k, v)
    state = BigFuzz()
    state.debt_supply()
    state.add_collateral(uid=0, y=0)
    state.debt_supply()
    state.shift_oracle(dp=0.0078125)
    state.debt_supply()
    state.deposit(n=5, ratio=1.0, uid=0, y=505)
    state.teardown()


def test_noraise_2(
        market_amm, market_controller, monetary_policy, collateral_token, stablecoin, price_oracle, accounts, admin):
    # This is due to evmdiv working not like floor div (fixed)
    for k, v in locals().items():
        setattr(BigFuzz, k, v)
    state = BigFuzz()
    state.shift_oracle(dp=2.3841130314394837e-09)
    state.deposit(n=5, ratio=0.9340958492675753, uid=0, y=4063)
    state.teardown()


def test_exchange_fails(
        market_amm, market_controller, monetary_policy, collateral_token, stablecoin, price_oracle, accounts, admin):
    # This is due to evmdiv working not like floor div (fixed)
    for k, v in locals().items():
        setattr(BigFuzz, k, v)
    state = BigFuzz()
    state.debt_supply()
    state.add_collateral(uid=0, y=0)
    state.debt_supply()
    state.shift_oracle(dp=0.0)
    state.debt_supply()
    state.time_travel(dt=6)
    state.debt_supply()
    state.deposit(n=5, ratio=6.103515625e-05, uid=1, y=14085)
    state.debt_supply()
    state.deposit(n=5, ratio=1.199379084937393e-07, uid=0, y=26373080523014146049)
    state.debt_supply()
    state.trade(is_pump=True, r=1.0, uid=0)
    state.teardown()