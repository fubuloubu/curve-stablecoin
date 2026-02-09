def test_default_behavior_vaults_index_returns_created(factory, vault):
    market_count = factory.market_count()
    # Sanity check: fixtures should have created at least one market
    assert market_count > 0, "Expected at least one market from fixture setup"

    assert factory.vaults_index(vault.address) == market_count - 1
