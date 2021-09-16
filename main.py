#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import time
import copy
from random import getrandbits, seed, shuffle
import hashlib
import argparse
import datetime
import logging
from time import sleep

from web3 import Web3
from hexbytes import HexBytes
from eth_utils import decode_hex, to_canonical_address

from utils.settings import *
from detection.insertion import *
from emulator import Emulator

log = logging.getLogger(__name__)


def _group_transactions(transactions):
    """Group transactions by sender and nonce."""
    log.debug("Grouping transactions by sender and nonce...")
    sorted_mapping = dict()
    for tx in transactions:
        if not tx["from"] in sorted_mapping:
            sorted_mapping[tx["from"]] = list()
        sorted_mapping[tx["from"]].append(tx)
    return (list(sorted_mapping.keys()), sorted_mapping)


# We don't need to use an actual VDF, since this is all done through simulation.
# Instead of modeling the delay indirectly through a computational difficulty
# parameter, we will model it directly with a delay parameter.
def vdf_sim(vdf_seed, delay_ms=10, num_bits=256):
    log.debug("Simulated VDF delay=%i", delay_ms)
    sleep(delay_ms / 1000.0)
    seed(int.from_bytes(vdf_seed, byteorder="big"))
    return getrandbits(num_bits)


# NOTE: I realized that geth only goups transactions from the same sender
# together if gas price and nonce provide a conflict. For example, if tx1
# has nonce 1 and gas price 2 and tx2 has nonce 2 and gas price 4 then geth
# will first execute tx1 and then tx2 because of the nonce, although tx2
# pays a higher gas price. The same applies if tx2 has the same gas price as
# tx1, then they are grouped together in the order and the nonce defines the
# order. However, if tx2 would has a lower gas price than tx1, then they are
# not grouped together, meaning that there can be other transaction in between
# from other senders.
def sort_and_shuffle(transactions, block, vdf_delay_ms):
    log.info("Initiating sort-and-shuffle...")
    # We assume that the transactions are already sorted based on gas price and nonce.
    keys, sorted_mapping = _group_transactions(transactions)

    # Sort buckets in ascending order by sender address
    # this is necessary because after grouping transactions
    # from the same sender, we need to make sure that the
    # groups are in a deterministic order.
    log.info("Sorting groups...")
    keys.sort()

    # Hash all transactions together, sequentially.
    log.info("Hashing transactions...")
    sha3_hash = hashlib.sha3_256()
    for key in keys:
        for tx in sorted_mapping[key]:
            sha3_hash.update(tx.hash)

    # Include the hash of the parent block
    sha3_hash.update(block.parentHash)
    seed_vdf = sha3_hash.digest()
    seed_shuffle = vdf_sim(seed_vdf, vdf_delay_ms)

    seed(seed_shuffle)

    log.info("Shuffling groups...")
    shuffle(keys)

    # Finally, assemble new transaction order based on the shuffled keys.
    shuffled_transactions = list()
    for key in keys:
        shuffled_transactions.extend(sorted_mapping[key])

    return shuffled_transactions


def compare_transaction_orders(
    original_transactions, shuffled_transactions, insertion_results=None
):
    assert len(original_transactions) == len(shuffled_transactions)
    print(
        "Original Transaction Order                                               \t| Shuffled Transaction Order"
    )
    print(
        "-----------------------------------------------------------------------------------------------------------------------------------------------------------"
    )
    for i in range(len(original_transactions)):
        original_transaction, shuffled_transaction = (
            original_transactions[i],
            shuffled_transactions[i],
        )

        original_transaction_output = (
            str(original_transaction.transactionIndex)
            + "\t"
            + original_transaction.hash.hex()
        )
        if insertion_results:
            if original_transaction.hash in [
                result["victim_tx"].hash for result in insertion_results
            ]:
                original_transaction_output = (
                    str(original_transaction.transactionIndex)
                    + "\t"
                    + colors.INFO
                    + original_transaction.hash.hex()
                    + colors.END
                )
            elif original_transaction.hash in [
                result["attacker_tx_1"].hash for result in insertion_results
            ]:
                original_transaction_output = (
                    str(original_transaction.transactionIndex)
                    + " 1.\t"
                    + colors.FAIL
                    + original_transaction.hash.hex()
                    + colors.END
                )
            elif original_transaction.hash in [
                result["attacker_tx_2"].hash for result in insertion_results
            ]:
                original_transaction_output = (
                    str(original_transaction.transactionIndex)
                    + " 2.\t"
                    + colors.FAIL
                    + original_transaction.hash.hex()
                    + colors.END
                )

        shuffled_transaction_output = (
            str(shuffled_transaction.transactionIndex)
            + "\t"
            + shuffled_transaction.hash.hex()
        )
        if insertion_results:
            if shuffled_transaction.hash in [
                result["victim_tx"].hash for result in insertion_results
            ]:
                shuffled_transaction_output = (
                    str(shuffled_transaction.transactionIndex)
                    + "\t"
                    + colors.INFO
                    + shuffled_transaction.hash.hex()
                    + colors.END
                )
            elif shuffled_transaction.hash in [
                result["attacker_tx_1"].hash for result in insertion_results
            ]:
                shuffled_transaction_output = (
                    str(shuffled_transaction.transactionIndex)
                    + " 1.\t"
                    + colors.FAIL
                    + shuffled_transaction.hash.hex()
                    + colors.END
                )
            elif shuffled_transaction.hash in [
                result["attacker_tx_2"].hash for result in insertion_results
            ]:
                shuffled_transaction_output = (
                    str(shuffled_transaction.transactionIndex)
                    + " 2.\t"
                    + colors.FAIL
                    + shuffled_transaction.hash.hex()
                    + colors.END
                )

        print(original_transaction_output + "\t|" + shuffled_transaction_output)


def filter_logs_by_topic(transaction, result, topic):
    logs = list()
    for log_entry in result.get_log_entries():
        for log_entry_topic in log_entry[1]:
            if hex(log_entry_topic) == topic:
                log = {
                    "address": Web3.toChecksumAddress("0x" + log_entry[0].hex()),
                    "data": "0x" + log_entry[2].hex(),
                    "topics": [HexBytes(hex(t)[2:].zfill(64)) for t in log_entry[1]],
                    "transactionHash": HexBytes(transaction.hash),
                    "transactionIndex": int(transaction.transactionIndex),
                }
                if log not in logs:
                    logs.append(log)
    return logs


def _analyze_tx_set(w3, block, transactions):
    emu = Emulator(PROVIDER, block)
    emu.load_archive_state()
    token_transfer_events = list()
    uniswap_purchase_events = list()
    execution_start = time.time()
    for transaction in transactions:
        print(transaction.transactionIndex, transaction.hash.hex())
        result, execution_trace = emu.execute_transaction(transaction)
        token_transfer_events += filter_logs_by_topic(transaction, result, TRANSFER)
        uniswap_purchase_events += filter_logs_by_topic(
            transaction, result, TOKEN_PURCHASE
        )
        uniswap_purchase_events += filter_logs_by_topic(
            transaction, result, ETH_PURCHASE
        )
    print(len(token_transfer_events))
    print(len(uniswap_purchase_events))
    print(time.time() - execution_start, "seconds")
    emu.dump_archive_state()
    return analyze_block_for_insertion(
        w3, block, transactions, token_transfer_events, uniswap_purchase_events
    )


def main():
    global args

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-b",
        "--block",
        type=str,
        help="Ethereum mainnet block number to test sort-and-shuffle",
        required=True,
    )

    parser.add_argument("-v", "--version", action="version", version="0.0.1")

    parser.add_argument(
        "-s",
        "--seed",
        type=int,
        default=0,
        help="A seed to run deterministic experiments",
    )

    parser.add_argument(
        "-d", "--vdf-delay-ms", type=int, default=0, help="The simulated VDF delay"
    )

    args = parser.parse_args()

    w3 = Web3(PROVIDER)
    log.info("Web3 version: " + w3.api)

    # Experiments should be deterministic and reproducable.
    seed(args.seed)

    latestBlock = w3.eth.getBlock("latest")
    log.info("Connected to the Ethereum blockchain.")
    if w3.eth.syncing == False:
        log.info("Ethereum blockchain is synced.")
    else:
        log.warning("Ethereum blockchain is currently syncing...")

    log.info(
        "Latest block: "
        + str(latestBlock.number)
        + " ("
        + datetime.datetime.fromtimestamp(int(latestBlock.timestamp)).strftime(
            "%d-%m-%Y %H:%M:%S"
        )
        + ")\n"
    )

    log.info("Retrieving original transactions for block number: " + args.block + "...")
    block = w3.eth.getBlock(int(args.block), True)
    log.info("Block has been mined by: " + block.extraData.decode("utf-8") + "\n")

    original_transactions = block.transactions
    # Compute seed for shuffling: Concatenate previous block hash with hash of all current transactions in sorted order
    start = time.time()
    shuffled_transactions = sort_and_shuffle(
        copy.deepcopy(original_transactions), block, args.vdf_delay_ms
    )
    log.info("Seed generation and shuffling took: %i second(s)", time.time() - start)

    compare_transaction_orders(original_transactions, shuffled_transactions)
    # Apply the new transaction index
    for i in range(len(shuffled_transactions)):
        shuffled_transactions[i].__dict__["transactionIndex"] = i

    insertion_results = _analyze_tx_set(w3, block, original_transactions)
    _analyze_tx_set(w3, block, shuffled_transactions)

    compare_transaction_orders(
        original_transactions, shuffled_transactions, insertion_results
    )


if __name__ == "__main__":
    main()
