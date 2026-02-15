import boa


def test_default_behavior(controller, borrow_cap):
    """Test that _on_debt_increased works when called by the controller itself with valid debt amount."""
    debt_amount = borrow_cap // 2
    assert debt_amount > controller.total_debt()
    controller._on_debt_increased(debt_amount, sender=controller.address)


def test_unauthorized(controller, borrow_cap):
    """Test that _on_debt_increased reverts when called by unauthorized address."""
    debt_amount = borrow_cap // 2
    assert debt_amount > controller.total_debt()

    # Should revert when called by non-controller address
    with boa.reverts(dev="virtual method protection (controller only)"):
        controller._on_debt_increased(debt_amount)


def test_exceed_borrow_cap(controller, borrow_cap):
    """Test that _on_debt_increased reverts when debt exceeds borrow cap."""
    excessive_debt = borrow_cap + 1
    assert excessive_debt > controller.total_debt()

    with boa.reverts("Borrow cap exceeded"):
        controller._on_debt_increased(excessive_debt, sender=controller.address)
