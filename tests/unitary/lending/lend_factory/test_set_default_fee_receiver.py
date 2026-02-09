import boa
from tests.utils import filter_logs


def test_default_behavior(factory, admin):
    new_fee_receiver = boa.env.generate_address("new_fee_receiver")
    assert factory.default_fee_receiver() != new_fee_receiver

    with boa.env.prank(admin):
        factory.set_default_fee_receiver(new_fee_receiver)

    logs = filter_logs(factory, "SetFeeReceiver")

    assert factory.default_fee_receiver() == new_fee_receiver

    assert len(logs) == 1
    assert logs[0].fee_receiver == new_fee_receiver


def test_unauthorized(factory):
    non_owner = boa.env.generate_address("non_owner")
    new_fee_receiver = boa.env.generate_address("new_fee_receiver")
    with boa.reverts("ownable: caller is not the owner"):
        with boa.env.prank(non_owner):
            factory.set_default_fee_receiver(new_fee_receiver)
