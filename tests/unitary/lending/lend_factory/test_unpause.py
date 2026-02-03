import boa
import pytest


@pytest.fixture(scope="module")
def paused_factory(factory, admin):
    with boa.env.prank(admin):
        factory.pause()
    assert factory.paused()
    return factory


def test_default_behavior(paused_factory, admin):
    assert paused_factory.paused()

    with boa.env.prank(admin):
        paused_factory.unpause()

    assert not paused_factory.paused()


def test_unauthorized(paused_factory):
    non_owner = boa.env.generate_address("non_owner")
    with boa.reverts("ownable: caller is not the owner"):
        with boa.env.prank(non_owner):
            paused_factory.unpause()
