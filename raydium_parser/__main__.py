from raydium_parser.rpc_utils import get_block
from raydium_parser.raydium_parser import parse_block

if __name__ == "__main__":
    # print("hi")
    block = get_block(316719543)

    for swap in parse_block(block, 316719543):
        print(swap)
        break