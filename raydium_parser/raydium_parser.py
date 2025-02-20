from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal
from solders.transaction_status import UiConfirmedBlock, UiTransactionStatusMeta, UiCompiledInstruction 
import base64
import struct
from solders.pubkey import Pubkey

# The Raydium AMM program ID (Replace with the correct one)
RAYDIUM_AMM_PROGRAM_ID = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"



@dataclass
class RaydiumSwap:
    slot: int
    index_in_slot: int
    index_in_tx: int

    signature: str

    was_successful: bool

    mint_in: int
    mint_out: int
    amount_in: int
    amount_out: int

    limit_amount: int
    limit_side: Literal["mint_in", "mint_out"]

    post_pool_balance_mint_in: int
    post_pool_balance_mint_out: int


def parse_block(block: UiConfirmedBlock, slot: int) -> Iterator[RaydiumSwap]:
    """Parses a UiConfirmedBlock and extracts Raydium swap events."""
    
    for tx_index, tx_with_meta in enumerate(block.transactions):
        tx: UiTransactionStatusMeta = tx_with_meta.transaction
        meta = tx_with_meta.meta  # Contains balances, logs, etc.

        if not meta or not tx.message:
            continue  # Skip if no metadata (likely an invalid tx)
        
        # Ensure inner instructions exist
        if not meta.inner_instructions:  # Fix: No .value needed
            continue

        # print(f"Transaction {tx_index}: {tx_with_meta}")
        # print(f"Meta: {meta}")

        # Check if any instruction uses Raydium AMM program
        raydium_instruction_found = False
        for instruction in tx.message.instructions:
            # print(f"Instruction: {instruction}")
            # print(f"Program ID Index: {instruction.program_id_index}")
            # print(f"Account Keys Length: {len(tx.message.account_keys)}")
            
            # if isinstance(instruction, UiCompiledInstruction):
            #     print(f"Instruction Data: {instruction.data}")
            
            if instruction.program_id_index < len(tx.message.account_keys):
                program_id = tx.message.account_keys[instruction.program_id_index]
                # print(f"Resolved Program ID: {program_id}")
                program_id_str = str(program_id)  # Convert Pubkey to string
                # print(f"Resolved Program ID: {program_id_str}")


                if program_id_str == RAYDIUM_AMM_PROGRAM_ID:
                    print("✅ Found Raydium instruction!")
                    raydium_instruction_found = True
                    break
        # return

        
        if not raydium_instruction_found:
            continue  # Skip non-Raydium transactions

        print(f"Raydium transaction found: {tx.signatures[0]}")


        # Extract transaction signature
        signature = tx.signatures[0] if tx.signatures else "unknown"

        # Search for Raydium instructions
        for ix_index, instruction in enumerate(tx.message.instructions):
            # Check if this instruction is a Raydium swap
            if instruction.program_id_index >= len(tx.message.account_keys):
                continue  # Skip invalid program index

            program_id = tx.message.account_keys[instruction.program_id_index]

            if str(program_id) == RAYDIUM_AMM_PROGRAM_ID:
                # We found a Raydium swap transaction!
                
                # Extract success/failure status
                was_successful = meta.err is None

                # Extract mint_in, mint_out, amounts from accounts or logs
                mint_in, mint_out, amount_in, amount_out = extract_swap_data(meta, instruction)

                # Extract post-swap balances (if available)
                post_pool_balance_mint_in, post_pool_balance_mint_out = extract_post_balances(meta, mint_in, mint_out)

                # Yield the parsed swap event
                yield RaydiumSwap(
                    slot=slot,
                    index_in_slot=tx_index,
                    index_in_tx=ix_index,
                    signature=str(signature),
                    was_successful=was_successful,
                    mint_in=str(mint_in),
                    mint_out=str(mint_out),
                    amount_in=amount_in,
                    amount_out=amount_out,
                    limit_amount=extract_limit_amount(meta, mint_in),
                    limit_side="mint_in",
                    post_pool_balance_mint_in=post_pool_balance_mint_in,
                    post_pool_balance_mint_out=post_pool_balance_mint_out,
                )



def extract_swap_data(meta, instruction):
    """Extract mint and amount details from a Raydium swap instruction."""

    mint_in, mint_out = None, None
    amount_in, amount_out = 0, 0

    # Extract swapped tokens by comparing balances
    # print(f"🔍 Debug: Looking for token balances in meta: {meta}")
    for pre in meta.pre_token_balances:
        for post in meta.post_token_balances:
            if pre.account_index == post.account_index:
                # Handle None values safely
                pre_balance = pre.ui_token_amount.ui_amount if pre.ui_token_amount.ui_amount is not None else 0
                post_balance = post.ui_token_amount.ui_amount if post.ui_token_amount.ui_amount is not None else 0
                
                delta = post_balance - pre_balance
                # print(f"🔄 Comparing: {pre.mint} -> {post.mint} | Delta: {delta}")

                if delta < 0:  # Token spent
                    mint_in = pre.mint
                    amount_in = abs(delta)
                elif delta > 0:  # Token received
                    mint_out = post.mint
                    amount_out = delta
    return mint_in, mint_out, amount_in, amount_out



def extract_post_balances(meta, mint_in, mint_out):
    """Extract post-swap token balances from transaction metadata."""

    post_pool_balance_mint_in = None
    post_pool_balance_mint_out = None

    # print(f"🔍 Debug: Looking for mint_in={mint_in}, mint_out={mint_out} in post-token balances.")

    for balance in meta.post_token_balances:
        mint = balance.mint
        ui_amount = balance.ui_token_amount.ui_amount

        # print(f"  📝 Found balance - Mint: {mint}, Amount: {ui_amount}")

        if mint == mint_in and ui_amount is not None:
            # print(f"✅ Matched mint_in: {mint}, Balance: {ui_amount}")
            post_pool_balance_mint_in = ui_amount

        elif mint == mint_out and ui_amount is not None:
            # print(f"✅ Matched mint_out: {mint}, Balance: {ui_amount}")
            post_pool_balance_mint_out = ui_amount

    # print(f"📊 Final extracted balances: Mint In = {post_pool_balance_mint_in}, Mint Out = {post_pool_balance_mint_out}")

    return post_pool_balance_mint_in, post_pool_balance_mint_out


def extract_limit_amount(meta, token_mint, decimals=6):
    """Extracts the limit amount from transaction metadata for the specified token mint."""

    if not meta:
        # print("⚠️ No transaction metadata available!")
        return 0

    pre_balances = meta.pre_token_balances if meta.pre_token_balances else []
    post_balances = meta.post_token_balances if meta.post_token_balances else []

    # Print all pre and post balances
    # print(f"🔍 Debug: Extracting limit amount for mint {token_mint}")
    # print("Pre-Balances:")
    # for b in pre_balances:
        # print(f"  - Mint: {b.mint}, Amount: {b.ui_token_amount.amount}")

    # print("Post-Balances:")
    # for b in post_balances:
        # print(f"  - Mint: {b.mint}, Amount: {b.ui_token_amount.amount}")

    # Get pre and post transaction balances for the specified token mint
    pre_amount = next((int(b.ui_token_amount.amount) for b in pre_balances if b.mint == token_mint), 0)
    post_amount = next((int(b.ui_token_amount.amount) for b in post_balances if b.mint == token_mint), 0)

    # Print extracted values
    # print(f"✅ Pre-Amount: {pre_amount}, Post-Amount: {post_amount}")

    # Calculate the difference and convert using decimal places
    limit_amount = (post_amount - pre_amount) / (10 ** decimals)

    # print(f"📊 Calculated Limit Amount: {limit_amount}")

    return limit_amount

