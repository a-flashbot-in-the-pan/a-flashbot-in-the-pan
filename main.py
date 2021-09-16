#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import time
import copy
import random
import hashlib
import argparse
import datetime

from web3 import Web3
from hexbytes import HexBytes
from eth_utils import decode_hex, to_canonical_address

from utils.settings import *
from detection.insertion import *
from emulator import Emulator

def _group_transactions(transactions):
    sorted_mapping = dict()
    for tx in transactions:
        if not tx['from'] in sorted_mapping:
            sorted_mapping[tx['from']] = list()
        sorted_mapping[tx['from']].append(tx)
    return (list(sorted_mapping.keys()), sorted_mapping)

# NOTE: I realized that geth only goups transactions from the same sender together if gas price and nonce provide a conflict. For example, if tx1 has nonce 1 and gas price 2 and tx2 has nonce 2 and gas price 4 then geth will first execute tx1 and then tx2 because of the nonce, although tx2 pays a higher gas price. The same applies if tx2 has the same gas price as tx1, then they are grouped together in the order and the nonce defines the order. However, if tx2 would has a lower gas price than tx1, then they are not grouped together, meaning that there can be other transaction in between from other senders.
def sort_and_shuffle(transactions, seed):
    #import pdb; pdb.set_trace()
    random.seed(a=seed, version=2)
    # We assume that the transactions are already sorted based on gas price and nonce.
    # Thus all we need to do is group the sorted transactions by sender.
    keys, sorted_mapping = _group_transactions(transactions)
    random.shuffle(keys)

    # Finally, assemble new transaction order based on the shuffled keys.
    shuffled_transactions = list()
    for key in keys:
        shuffled_transactions.extend(sorted_mapping[key])

    return shuffled_transactions

def compare_transaction_orders(original_transactions, shuffled_transactions, insertion_results=None):
    assert(len(original_transactions) == len(shuffled_transactions))
    print("Original Transaction Order                                               \t| Shuffled Transaction Order")
    print("-----------------------------------------------------------------------------------------------------------------------------------------------------------")
    for i in range(len(original_transactions)):
        original_transaction, shuffled_transaction = original_transactions[i], shuffled_transactions[i]

        original_transaction_output = str(original_transaction.transactionIndex)+'\t'+original_transaction.hash.hex()
        if insertion_results:
            if   original_transaction.hash in [result["victim_tx"].hash for result in insertion_results]:
                original_transaction_output = str(original_transaction.transactionIndex)+'\t'+colors.INFO+original_transaction.hash.hex()+colors.END
            elif original_transaction.hash in [result["attacker_tx_1"].hash for result in insertion_results]:
                original_transaction_output = str(original_transaction.transactionIndex)+' 1.\t'+colors.FAIL+original_transaction.hash.hex()+colors.END
            elif original_transaction.hash in [result["attacker_tx_2"].hash for result in insertion_results]:
                original_transaction_output = str(original_transaction.transactionIndex)+' 2.\t'+colors.FAIL+original_transaction.hash.hex()+colors.END

        shuffled_transaction_output = str(shuffled_transaction.transactionIndex)+'\t'+shuffled_transaction.hash.hex()
        if insertion_results:
            if   shuffled_transaction.hash in [result["victim_tx"].hash for result in insertion_results]:
                shuffled_transaction_output = str(shuffled_transaction.transactionIndex)+'\t'+colors.INFO+shuffled_transaction.hash.hex()+colors.END
            elif shuffled_transaction.hash in [result["attacker_tx_1"].hash for result in insertion_results]:
                shuffled_transaction_output = str(shuffled_transaction.transactionIndex)+' 1.\t'+colors.FAIL+shuffled_transaction.hash.hex()+colors.END
            elif shuffled_transaction.hash in [result["attacker_tx_2"].hash for result in insertion_results]:
                shuffled_transaction_output = str(shuffled_transaction.transactionIndex)+' 2.\t'+colors.FAIL+shuffled_transaction.hash.hex()+colors.END

        print(original_transaction_output+'\t|'+shuffled_transaction_output)

def filter_logs_by_topic(transaction, result, topic):
    logs = list()
    for log_entry in result.get_log_entries():
        for log_entry_topic in log_entry[1]:
            if hex(log_entry_topic) == topic:
                log = {
                    "address": Web3.toChecksumAddress("0x"+log_entry[0].hex()),
                    "data": "0x"+log_entry[2].hex(),
                    "topics": [HexBytes(hex(t)[2:].zfill(64)) for t in log_entry[1]],
                    "transactionHash": HexBytes(transaction.hash),
                    "transactionIndex": int(transaction.transactionIndex)
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
        uniswap_purchase_events += filter_logs_by_topic(transaction, result, TOKEN_PURCHASE)
        uniswap_purchase_events += filter_logs_by_topic(transaction, result, ETH_PURCHASE)
    print(len(token_transfer_events))
    print(len(uniswap_purchase_events))
    print(time.time() - execution_start, "seconds")
    emu.dump_archive_state()
    return analyze_block_for_insertion(w3, block, transactions, token_transfer_events, uniswap_purchase_events)

def main():
    global args

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-b", "--block", type=str, help="Ethereum mainnet block number to test sort&shuffle")

    parser.add_argument(
        "-v", "--version", action="version", version="0.0.1")
    args = parser.parse_args()

    if not args.block:
        print("Error: Block number not provided!")
        sys.exit(-1)

    w3 = Web3(PROVIDER)
    print('\033[1mWeb3 version: '+w3.api+'\033[0m')

    latestBlock = w3.eth.getBlock('latest')
    print('\033[1mConnected to the Ethereum blockchain.\033[0m')
    if w3.eth.syncing == False:
        print('\033[1mEthereum blockchain is synced.\033[0m')
        print('\033[1mLatest block: '+str(latestBlock.number)+' ('+datetime.datetime.fromtimestamp(int(latestBlock.timestamp)).strftime('%d-%m-%Y %H:%M:%S')+')\n\033[0m')
    else:
        print('\033[1mEthereum blockchain is currently syncing...\033[0m')
        print('\033[1mLatest block: '+str(latestBlock.number)+' ('+datetime.datetime.fromtimestamp(int(latestBlock.timestamp)).strftime('%d-%m-%Y %H:%M:%S')+')\n\033[0m')

    print('\033[1mRetrieving original transactions for block number: '+args.block+'...\033[0m')
    block = w3.eth.getBlock(int(args.block), True)
    print('\033[1mBlock has been minded by: '+block.extraData.decode("utf-8")+'\n\033[0m')

    original_transactions = block.transactions
    # Compute seed for shuffling: Concatenate previous block hash with hash of all current transactions in sorted order
    start = time.time()
    sha3_hash = hashlib.sha3_256()
    for transaction in block.transactions:
        sha3_hash.update(transaction.hash)
    transactions_hash = sha3_hash.digest()
    seed = block.parentHash + transactions_hash
    print("Seed", seed.hex())
    shuffled_transactions = sort_and_shuffle(copy.deepcopy(original_transactions), seed)
    execution_time = time.time() - start
    print("Seed generation and shuffling took:", execution_time, "second(s)")

    compare_transaction_orders(original_transactions, shuffled_transactions)
    # Apply the new transaction index
    for i in range(len(shuffled_transactions)):
        shuffled_transactions[i].__dict__["transactionIndex"] = i

    insertion_results = _analyze_tx_set(w3, block, original_transactions)
    _analyze_tx_set(w3, block, shuffled_transactions)

    compare_transaction_orders(original_transactions, shuffled_transactions, insertion_results)

if __name__ == '__main__':
    main()
