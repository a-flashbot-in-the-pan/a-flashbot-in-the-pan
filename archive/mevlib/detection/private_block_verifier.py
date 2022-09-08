#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import json
import enum
import numpy
import pandas
import pymongo
import multiprocessing

from web3 import Web3

WEB3_HTTP_RPC_HOST = "pf.uni.lux"
WEB3_HTTP_RPC_PORT = 8545

MONGO_HOST = "pf.uni.lux"
MONGO_PORT = 27017

class colors:
    INFO = '\033[94m'
    OK = '\033[92m'
    FAIL = '\033[91m'
    END = '\033[0m'

class OrderingStrategy(enum.IntEnum):
    UNCONVENTIONAL = 0
    EMPTY = 1
    GAS_PRICE = 2

def is_sorted_by_gas_price(gas_price_list):
    return sorted(gas_price_list, reverse=True) == gas_price_list

def is_parity_ordering(gas_price_list):
    total_prioritised_transactions = 0
    local_multiplier = 2 ** 15
    retracted_multiplier = 2 ** 10
    priority_list = []
    current_multiplier = 1
    for current_gas_price in gas_price_list:
        if len(priority_list) == 0:
            priority_list.append(current_gas_price)
        else:
            if current_gas_price * current_multiplier >= priority_list[-1]:
                priority_list.append(current_gas_price * current_multiplier)
            elif (
                current_multiplier < retracted_multiplier
                and current_gas_price * retracted_multiplier >= priority_list[-1]
            ):
                current_multiplier = retracted_multiplier
                priority_list.append(current_gas_price * current_multiplier)
                total_prioritised_transactions += 1
            elif (
                current_multiplier < local_multiplier
                and current_gas_price * local_multiplier >= priority_list[-1]
            ):
                current_multiplier = local_multiplier
                priority_list.append(current_gas_price * current_multiplier)
                total_prioritised_transactions += 1
            else:
                return False
    return True

def remove_txs_from_same_sender(dataframe):
    dataframe_copy = dataframe.copy()
    transaction_counts = dataframe_copy["from"].value_counts()
    multi_transaction_accounts = transaction_counts[transaction_counts > 1].keys()
    for account in multi_transaction_accounts:
        indexes = dataframe_copy[dataframe_copy["from"] == account].index
        for index in indexes[1:]:
            dataframe_copy = dataframe_copy.drop(index)
    return dataframe_copy

def analyze_block(block_number):
    start = time.time()

    print("Analyzing block number:", block_number)
    found = mongo_connection["flashbots"]["valid_private_blocks"].find_one({"number": block_number})
    if found:
        print("Block "+str(block_number)+" already analyzed!")
        return time.time() - start

    block = w3.eth.getBlock(block_number, True)

    transaction_hashes = []
    transactions = []
    gas_price_list = []
    senders = []

    flashbots_block = mongo_connection["flashbots"]["flashbots_blocks"].find_one({"block_number": block_number})
    flashbots_transactions = set()
    for transaction in flashbots_block["transactions"]:
        flashbots_transactions.add(transaction["transaction_hash"])

    finding = None
    for i in range(len(block["transactions"])):
        transaction = block["transactions"][i]
        if transaction["hash"].hex() in flashbots_transactions:
            print(colors.FAIL+str(transaction["transactionIndex"]), "\t", transaction["hash"].hex(), "\t", transaction["gasPrice"], "(Flashbots)", colors.END)
            continue
        print(transaction["transactionIndex"], "\t", transaction["hash"].hex(), "\t", transaction["gasPrice"])
        if transaction["hash"].hex() not in transaction_hashes:
            if transaction["from"] not in senders:
                transactions.append(transaction)
                gas_price_list.append(transaction["gasPrice"])
                senders.append(transaction["from"])
            transaction_hashes.append(transaction["hash"].hex())

    if len(gas_price_list) == 0:
        strategy = OrderingStrategy.EMPTY
    elif is_sorted_by_gas_price(gas_price_list):
        strategy = OrderingStrategy.GAS_PRICE
    #else:
    #    transactions_df = pandas.DataFrame(transactions)
    #    transactions_single_from_df = remove_txs_from_same_sender(transactions_df)
    #    gas_price_list = transactions_single_from_df.gasPrice.tolist()[::-1]
    #    if is_parity_ordering(gas_price_list):
    #        strategy = OrderingStrategy.PARITY_DEFAULT
    else:
        strategy = OrderingStrategy.UNCONVENTIONAL

    print()
    if strategy == OrderingStrategy.GAS_PRICE:
        print(colors.OK+"Strategy:", strategy, colors.END)
    elif strategy == OrderingStrategy.UNCONVENTIONAL:
        print(colors.FAIL+"Strategy:", strategy, colors.END)
    else:
        print(colors.INFO+"Strategy:", strategy, colors.END)
    print()

    return time.time() - start

def init_process():
    global w3
    global debug
    global mongo_connection

    w3 = Web3(Web3.HTTPProvider("http://"+WEB3_HTTP_RPC_HOST+":"+str(WEB3_HTTP_RPC_PORT)))
    if w3.isConnected():
        print("Connected worker to "+w3.clientVersion)
    else:
        print(colors.FAIL+"Error: Could not connect to "+WEB3_HTTP_RPC_HOST+":"+str(WEB3_HTTP_RPC_PORT)+colors.END)
    debug = True
    mongo_connection = pymongo.MongoClient("mongodb://"+MONGO_HOST+":"+str(MONGO_PORT), maxPoolSize=None)

def main():
    if len(sys.argv) != 2:
        print(colors.FAIL+"Error: Please provide a block range to be analyzed: 'python3 "+sys.argv[0]+" <BLOCK_RANGE_START>:<BLOCK_RANGE_END>'"+colors.END)
        sys.exit(-1)
    if not ":" in sys.argv[1]:
        print(colors.FAIL+"Error: Please provide a valid block range: 'python3 "+sys.argv[0]+" <BLOCK_RANGE_START>:<BLOCK_RANGE_END>'"+colors.END)
        sys.exit(-2)
    block_range_start, block_range_end = sys.argv[1].split(":")[0], sys.argv[1].split(":")[1]
    if not block_range_start.isnumeric() or not block_range_end.isnumeric():
        print(colors.FAIL+"Error: Please provide integers as block range: 'python3 "+sys.argv[0]+" <BLOCK_RANGE_START>:<BLOCK_RANGE_END>'"+colors.END)
        sys.exit(-3)
    block_range_start, block_range_end = int(block_range_start), int(block_range_end)

    execution_times = []
    multiprocessing.set_start_method('fork')
    #print("Running detection of private transactions with "+str(multiprocessing.cpu_count())+" CPUs")
    print("Initializing workers...")
    with multiprocessing.Pool(processes=multiprocessing.cpu_count(), initializer=init_process) as pool:
        start_total = time.time()
        execution_times += pool.map(analyze_block, range(block_range_start, block_range_end+1))
        end_total = time.time()
        print("Total execution time: "+str(end_total - start_total))
        if execution_times:
            print("Max execution time: "+str(numpy.max(execution_times)))
            print("Mean execution time: "+str(numpy.mean(execution_times)))
            print("Median execution time: "+str(numpy.median(execution_times)))
            print("Min execution time: "+str(numpy.min(execution_times)))

if __name__ == "__main__":
    main()
