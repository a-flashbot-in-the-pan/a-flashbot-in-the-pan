#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import json
import numpy
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

def analyze_block(block_number):
    start = time.time()

    print("Analyzing block number:", block_number)
    found = mongo_connection["flashbots"]["private_transactions"].find_one({"number": block_number})
    if found:
        print("Block "+str(block_number)+" already analyzed!")
        return time.time() - start
    block = w3.eth.getBlock(block_number, True)

    flashbots_block_retrieved = False
    flashbots_transactions = set()
    finding = None
    for i in range(len(block["transactions"])):
        tx = block["transactions"][i]
        found = mongo_connection["flashbots"]["observed_transactions"].find_one({"hash": tx["hash"].hex()})
        if not found:
            if not flashbots_block_retrieved:
                flashbots_block = mongo_connection["flashbots"]["all_blocks"].find_one({"block_number": block_number})
                flashbots_block_retrieved = True
                if flashbots_block:
                    for t in flashbots_block["transactions"]:
                        flashbots_transactions.add(t["transaction_hash"])
            if finding == None:
                finding = dict(block)
                del finding["difficulty"]
                del finding["transactions"]
                del finding["logsBloom"]
                del finding["mixHash"]
                del finding["parentHash"]
                del finding["receiptsRoot"]
                del finding["sha3Uncles"]
                del finding["stateRoot"]
                del finding["totalDifficulty"]
                del finding["transactionsRoot"]
                del finding["uncles"]
                del finding["nonce"]
                finding["baseFeePerGas"] = str(finding["baseFeePerGas"])
                finding["extraData"] = finding["extraData"].hex()
                finding["hash"] = finding["hash"].hex()
                try:
                    finding["extraDataDecoded"] = block["extraData"].decode('utf8').replace("\n", "")
                except:
                    finding["extraDataDecoded"] = ""
                finding["privateTransactions"] = list()
            private_transaction = dict(tx)
            del private_transaction["blockHash"]
            del private_transaction["blockNumber"]
            del private_transaction["v"]
            del private_transaction["r"]
            del private_transaction["s"]
            if "accessList" in private_transaction:
                del private_transaction["accessList"]
            if "chainId" in private_transaction:
                del private_transaction["chainId"]
            if "maxFeePerGas" in private_transaction:
                private_transaction["maxFeePerGas"] = str(private_transaction["maxFeePerGas"])
            if "maxPriorityFeePerGas" in private_transaction:
                private_transaction["maxPriorityFeePerGas"] = str(private_transaction["maxPriorityFeePerGas"])
            if "type" in private_transaction:
                private_transaction["type"] = int(private_transaction["type"], 16)
            private_transaction["gasPrice"] = str(private_transaction["gasPrice"])
            private_transaction["value"] = str(private_transaction["value"])
            private_transaction["hash"] = private_transaction["hash"].hex()

            miner = finding["miner"]
            if finding["extraDataDecoded"]:
                miner = finding["extraDataDecoded"]

            if tx["hash"].hex() in flashbots_transactions:
                private_transaction["flashbots_transaction"] = True
                if debug:
                    print(colors.INFO+str(tx["transactionIndex"])+' '+tx["hash"].hex()+' From: '+tx["from"]+' To: '+str(tx["to"])+' (F) Miner: '+miner+colors.END)
            else:
                private_transaction["flashbots_transaction"] = False
                if debug:
                    print(colors.FAIL+str(tx["transactionIndex"])+' '+tx["hash"].hex()+' From: '+tx["from"]+' To: '+str(tx["to"])+' (U) miner: '+miner+colors.END)
            finding["privateTransactions"].append(private_transaction)

    if finding:
        collection = mongo_connection["flashbots"]["private_transactions"]
        collection.insert_one(finding)
        # Indexing...
        if 'number' not in collection.index_information():
            collection.create_index('number')
            collection.create_index('hash')
            collection.create_index('miner')
            collection.create_index('timestamp')
            collection.create_index('extraDataDecoded')
            collection.create_index('privateTransactions.hash')
            collection.create_index('privateTransactions.from')
            collection.create_index('privateTransactions.to')

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
    debug = False
    mongo_connection = pymongo.MongoClient("mongodb://"+MONGO_HOST+":"+str(MONGO_PORT), maxPoolSize=None)

def main():
    # 13576340:13576350
    # 13720000:13910000 (01-12-2021 until 31-12-2021)
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
    print("Running detection of private transactions with "+str(multiprocessing.cpu_count())+" CPUs")
    print("Initializing workers...")
    with multiprocessing.Pool(processes=multiprocessing.cpu_count(), initializer=init_process) as pool:
        print(colors.INFO+"(F) = Flashbots Transaction"+colors.END)
        print(colors.FAIL+"(U) = Unknown Private Transaction"+colors.END)
        mongo_connection = pymongo.MongoClient("mongodb://"+MONGO_HOST+":"+str(MONGO_PORT), maxPoolSize=None)
        print("Flashbots min block number:", mongo_connection["flashbots"]["all_blocks"].find_one(sort=[("block_number", +1)])["block_number"])
        print("Flashbots max block number:", mongo_connection["flashbots"]["all_blocks"].find_one(sort=[("block_number", -1)])["block_number"])
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
