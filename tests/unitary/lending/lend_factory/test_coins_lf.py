def test_default_behavior_coins_returns_tokens(
    factory,
    vault,
    borrowed_token,
    collateral_token,
):
    market_index = factory.vaults_index(vault.address)
    borrowed, collateral = factory.coins(market_index)

    assert borrowed == borrowed_token.address
    assert collateral == collateral_token.address
