from raydium_parser.raydium_parser import parse_block
from raydium_parser.rpc_utils import get_block


def test_raydium_parser():
    block = get_block(316719543)

    swaps = parse_block(block, 316719543)

    first_swap = next(swaps)

    assert first_swap.slot == 316719543
    assert first_swap.index_in_slot == 29
    assert first_swap.index_in_tx == 5
    assert first_swap.signature == "2T82ho5ma4pa1KYnBmUcQH2FangihgZY5rkoa2BsUFFFAarN3Y377aYf2T7SFdE7gKXf7rMM5c57ZjU7qMu7Kw8i"
    assert first_swap.was_successful
    assert first_swap.mint_in == "93ofca3Yx3eXXvLmg6kjhvtB2WJKCyYDK1RWDiTRpump"
    assert first_swap.mint_out == "So11111111111111111111111111111111111111112"
    assert first_swap.amount_in == 634809.8231379986
    assert first_swap.amount_out == 0.24750000000000227
    assert first_swap.limit_amount == 634809.823138
    assert first_swap.limit_side == "mint_in"
    assert first_swap.post_pool_balance_mint_in == 205121330.280631
    assert first_swap.post_pool_balance_mint_out == 80.02038406
