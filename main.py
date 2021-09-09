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
from http import client
from hexbytes import HexBytes
from eth_utils import decode_hex, to_canonical_address

from utils.settings import *
from utils.utils import request_debug_trace
from detection.insertion import *
from emulator import Emulator

# NOTE: I realized that geth only goups transactions from the same sender together if gas price and nonce provide a conflict. For example, if tx1 has nonce 1 and gas price 2 and tx2 has nonce 2 and gas price 4 then geth will first execute tx1 and then tx2 because of the nonce, although tx2 pays a higher gas price. The same applies if tx2 has the same gas price as tx1, then they are grouped together in the order and the nonce defines the order. However, if tx2 would has a lower gas price than tx1, then they are not grouped together, meaning that there can be other transaction in between from other senders.
def shuffle(transactions, seed):
    n = len(transactions)
    random.seed(a=seed, version=2)
    # We assume that the transactions are already sorted based on gas price and nonce.
    # Thus all we need to do is group the sorted transactions by sender.
    sorted_mapping = dict()
    for i in range(n):
        if not transactions[i]['from'] in sorted_mapping:
            sorted_mapping[transactions[i]['from']] = list()
        sorted_mapping[transactions[i]['from']].append(transactions[i])
    keys = list(sorted_mapping.keys())
    # Shuffle the keys in the sorted mapping using the Knuth-Fisher-Yates algorithm.
    m = len(keys)
    for i in range(m-1, 0, -1):
        j = random.randint(0, i+1)
        keys[i], keys[j] = keys[j], keys[i]
    # Finally, assemble new transaction order based on the shuffled keys.
    shuffled_transactions = list()
    for i in range(m):
        shuffled_transactions += sorted_mapping[keys[i]]
    return shuffled_transactions

def print_transactions(transactions):
    print("  \t Sender                                   \t Receiver                                   \t Nonce \t Gas Price \t Transaction Hash")
    print("-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------")
    for i in range(len(transactions)):
        transaction = transactions[i]
        if i > 0 and transaction['from'] == transactions[i-1]['from']:
            if transaction.gasPrice > 9999999999999:
                print(transaction.transactionIndex, '\t', " "+u'\u2514'+"> "+transaction['from'], '', transaction.to, '\t', transaction.nonce, '\t', transaction.gasPrice, '', transaction.hash.hex())
            else:
                print(transaction.transactionIndex, '\t', " "+u'\u2514'+"> "+transaction['from'], '', transaction.to, '\t', transaction.nonce, '\t', transaction.gasPrice, '\t', transaction.hash.hex())
        else:
            if transaction.gasPrice > 9999999999999:
                print(transaction.transactionIndex, '\t', transaction['from'], '\t', transaction.to, '\t', transaction.nonce, '\t', transaction.gasPrice, '', transaction.hash.hex())
            else:
                print(transaction.transactionIndex, '\t', transaction['from'], '\t', transaction.to, '\t', transaction.nonce, '\t', transaction.gasPrice, '\t', transaction.hash.hex())

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

def print_execution(result, execution_trace):
    print("Last 20 executed instructions:")
    for i in range(len(execution_trace)-20, len(execution_trace)):
        ins = execution_trace[i]
        print("\t", ins["opcode"])
    print("Number of executed instructions:", len(execution_trace))
    print("Success:",result.is_success)
    print("Error:", result.is_error)
    if result.is_error:
        print("Error message:", str(result.error))
    print("Logs:")
    for log in result.get_log_entries():
        print("\t", "Address:", "0x"+log[0].hex())
        print("\t", "Topics:")
        for topic in log[1]:
            print("\t \t", hex(topic))
        print("\t", "Data:", "0x"+log[2].hex())
        print()
    print("Return data:", "0x"+result.return_data.hex())
    print("Output:", "0x"+result.output.hex())

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
    shuffled_transactions = shuffle(copy.deepcopy(original_transactions), seed)
    execution_time = time.time() - start
    print("Seed generation and shuffling took:", execution_time, "second(s)")

    compare_transaction_orders(original_transactions, shuffled_transactions)
    # Apply the new transaction index
    for i in range(len(shuffled_transactions)):
        shuffled_transactions[i].__dict__["transactionIndex"] = i


    emu = Emulator(PROVIDER, block)
    token_transfer_events = list()
    uniswap_purchase_events = list()
    for transaction in original_transactions:
        print(transaction.transactionIndex, transaction.hash.hex())
        result, execution_trace = emu.execute_transaction(transaction)
        """print("Number of executed instructions:", len(execution_trace))
        connection = client.HTTPConnection(WEB3_HTTP_RPC_HOST, WEB3_HTTP_RPC_PORT)
        response = request_debug_trace(connection, transaction.hash.hex(), custom_tracer=False, disable_stack=False)
        if response and "result" in response:
            print(len(response["result"]["structLogs"]))
            if len(response["result"]["structLogs"]) != len(execution_trace):
                for i in range(len(execution_trace)):
                    print(i+1, execution_trace[i]["opcode"], response["result"]["structLogs"][i]["op"], response["result"]["structLogs"][i]["stack"])
                if result.is_error:
                    print("Error message:", str(result.error))
            assert(len(response["result"]["structLogs"]) == len(execution_trace))"""
        token_transfer_events += filter_logs_by_topic(transaction, result, TRANSFER)
        uniswap_purchase_events += filter_logs_by_topic(transaction, result, TOKEN_PURCHASE)
        uniswap_purchase_events += filter_logs_by_topic(transaction, result, ETH_PURCHASE)
    print(len(token_transfer_events))
    print(len(uniswap_purchase_events))

    insertion_results = analyze_block_for_insertion(w3, block, original_transactions, token_transfer_events, uniswap_purchase_events)

    emu = Emulator(PROVIDER, block)
    token_transfer_events = list()
    uniswap_purchase_events = list()
    for transaction in shuffled_transactions:
        print(transaction.transactionIndex, transaction.hash.hex())
        result, execution_trace = emu.execute_transaction(transaction)
        token_transfer_events += filter_logs_by_topic(transaction, result, TRANSFER)
        uniswap_purchase_events += filter_logs_by_topic(transaction, result, TOKEN_PURCHASE)
        uniswap_purchase_events += filter_logs_by_topic(transaction, result, ETH_PURCHASE)

    print(len(token_transfer_events))
    print(len(uniswap_purchase_events))

    analyze_block_for_insertion(w3, block, shuffled_transactions, token_transfer_events, uniswap_purchase_events)

    #print_transactions(original_transactions)
    #print_transactions(shuffled_transactions)
    compare_transaction_orders(original_transactions, shuffled_transactions, insertion_results)


if __name__ == '__main__':
    main()
