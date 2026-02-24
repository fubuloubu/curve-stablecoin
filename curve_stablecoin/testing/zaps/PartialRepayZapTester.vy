# pragma version 0.4.3

from curve_std.interfaces import IERC20
from curve_std import token as tkn
from curve_stablecoin import constants as c


CALLDATA_MAX_SIZE: constant(uint256) = c.CALLDATA_MAX_SIZE


@external
def callback_liquidate_partial(
    collateral: address,
    borrowed: address,
    borrowed_from_sender: uint256,
):
    collateral_token: IERC20 = IERC20(collateral)
    borrowed_token: IERC20 = IERC20(borrowed)
    collateral_balance: uint256 = staticcall collateral_token.balanceOf(msg.sender)
    tkn.transfer_from(collateral_token, msg.sender, self, collateral_balance)
    tkn.transfer(borrowed_token, msg.sender, borrowed_from_sender)
