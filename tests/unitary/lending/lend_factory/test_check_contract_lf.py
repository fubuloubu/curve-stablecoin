import boa


VAULT_TYPE = 1
CONTROLLER_TYPE = 2
AMM_TYPE = 4


def test_default_behavior_check_contract_returns_info(factory, vault, controller, amm):
    market_index = factory.vaults_index(vault.address)

    vault_info = factory.check_contract(vault.address)
    controller_info = factory.check_contract(controller.address)
    amm_info = factory.check_contract(amm.address)

    assert vault_info.market_index == market_index
    assert vault_info.contract_type == VAULT_TYPE

    assert controller_info.market_index == market_index
    assert controller_info.contract_type == CONTROLLER_TYPE

    assert amm_info.market_index == market_index
    assert amm_info.contract_type == AMM_TYPE


def test_default_behavior_check_contract_returns_empty(factory):
    unknown_address = boa.env.generate_address()
    info = factory.check_contract(unknown_address)

    assert info.market_index == 0
    assert info.contract_type == 0
