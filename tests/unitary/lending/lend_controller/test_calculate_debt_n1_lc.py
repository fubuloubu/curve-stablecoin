def test_default_behavior(controller, amm, collateral_token, borrowed_token):
    N = 10
    collateral = int(0.1 * 10 ** collateral_token.decimals())
    max_debt = controller.max_borrowable(collateral, N)
    n1 = controller.calculate_debt_n1(collateral, max_debt, N)

    assert n1 <= amm.active_band()
