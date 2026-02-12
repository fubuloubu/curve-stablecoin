def test_default_behavior_markets_returns_struct(
    factory,
    vault,
    controller,
    amm,
    borrowed_token,
    collateral_token,
    price_oracle,
    monetary_policy,
):
    count = factory.market_count()
    # Sanity check: fixtures should have created at least one market
    assert count > 0, "Expected at least one market from fixture setup"

    market = factory.markets(count - 1)

    assert market.vault == vault.address
    assert market.controller == controller.address
    assert market.amm == amm.address
    assert market.borrowed_token == borrowed_token.address
    assert market.collateral_token == collateral_token.address
    assert market.price_oracle == price_oracle.address
    assert market.monetary_policy == monetary_policy.address
