#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import json
import numpy
import decimal
import pymongo
import requests
import multiprocessing

from web3 import Web3

WEB3_HTTP_RPC = "http://pf.uni.lux:8545"

MONGO_HOST = "pf.uni.lux"
MONGO_PORT = 27017

class colors:
    INFO = '\033[94m'
    OK = '\033[92m'
    FAIL = '\033[91m'
    END = '\033[0m'

def analyze_block(block_number):
    start = time.time()
    print("Analyzing block number: "+str(block_number))

    status = mongo_connection["flashbots"]["miner_payouts_status"].find_one({"block_number": block_number})
    if status:
        print("Block "+str(block_number)+" already analyzed!")
        return status["execution_time"]

    try:
        block = w3.eth.getBlock(block_number, True)

        sender = None
        last_index = None
        miner_payouts = list()
        for transaction in block["transactions"]:
            if transaction["from"] == block["miner"]:
                sender = transaction["from"]
                last_index = transaction["transactionIndex"]
                miner_payouts.append(transaction["hash"].hex())
            elif sender != None and last_index != None and transaction["from"] == sender and transaction["transactionIndex"] == last_index + 1:
                last_index = transaction["transactionIndex"]
                miner_payouts.append(transaction["hash"].hex())
            #print(transaction["from"], "\t", transaction["to"], "\t", transaction["hash"].hex())

        print(miner_payouts)


    except Exception as e:
        import traceback
        print(traceback.format_exc())
        print("Error: "+str(e)+" @ block number: "+str(block_number))

    end = time.time()
    #collection = mongo_connection["flashbots"]["miner_payouts_status"]
    #collection.insert_one({"block_number": block_number, "execution_time": end-start})
    # Indexing...
    #if 'block_number' not in collection.index_information():
    #    collection.create_index('block_number')

    return end - start

def init_process():
    global w3
    global mongo_connection

    w3 = Web3(Web3.HTTPProvider(WEB3_HTTP_RPC))
    if w3.isConnected():
        print("Connected worker to "+w3.clientVersion)
    else:
        print(colors.FAIL+"Error: Could not connect to "+WEB3_HTTP_RPC+colors.END)
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
    if sys.platform.startswith("linux"):
        multiprocessing.set_start_method('fork')
    print("Running detection of miner payouts with "+str(multiprocessing.cpu_count())+" CPUs")
    print("Initializing workers...")
    # 13999993 miner payout (ethermine)
    # 13744536
    # 13744532 miner payout (mining pool hub)
    with multiprocessing.Pool(processes=multiprocessing.cpu_count(), initializer=init_process) as pool:
        start_total = time.time()
        execution_times += pool.map(analyze_block, range(block_range_start, block_range_end+1))
        end_total = time.time()
        print("Total execution time: "+str(end_total - start_total))
        print()
        if execution_times:
            print("Max execution time: "+str(numpy.max(execution_times)))
            print("Mean execution time: "+str(numpy.mean(execution_times)))
            print("Median execution time: "+str(numpy.median(execution_times)))
            print("Min execution time: "+str(numpy.min(execution_times)))

if __name__ == "__main__":
    main()
