#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import sys
import time
import json
import numpy
import pymongo
import requests
import multiprocessing

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

    status = mongo_connection["flashbots"]["eden_private_blocks_status"].find_one({"block_number": block_number})
    if status:
        print("Block "+str(block_number)+" already analyzed!")
        return status["execution_time"]

    try:
        response = requests.get("https://explorer.edennetwork.io/block/"+str(block_number))
        data = json.loads(re.compile('<script id="__NEXT_DATA__" type="application/json">(.+?)</script>').findall(response.text)[0])
        if data["props"]["pageProps"]["isEdenBlock"] == True:
            print(colors.OK+"Block", block_number, "is an Eden block!"+colors.END)

            eden_block = dict(data["props"]["pageProps"])
            del eden_block["isEdenBlock"]
            eden_block["transactions"] = eden_block.pop("labeledTxs")

            collection = mongo_connection["flashbots"]["eden_private_blocks"]
            collection.insert_one(eden_block)
            # Indexing...
            if 'block.number' not in collection.index_information():
                collection.create_index('block.number')
                collection.create_index('block.miner')
                collection.create_index('block.timestamp')
                collection.create_index('bundledTxsCallSuccess')
                collection.create_index('isValidBlock')
                collection.create_index('transactions.bundleIndex')
                collection.create_index('transactions.from')
                collection.create_index('transactions.fromLabel')
                collection.create_index('transactions.gasLimit')
                collection.create_index('transactions.hash')
                collection.create_index('transactions.minerReward')
                collection.create_index('transactions.senderStake')
                collection.create_index('transactions.status')
                collection.create_index('transactions.to')
                collection.create_index('transactions.toLabel')
                collection.create_index('transactions.toSlot')
                collection.create_index('transactions.transactionIndex')
                collection.create_index('transactions.txFee')
                collection.create_index('transactions.type')
                collection.create_index('transactions.value')
                collection.create_index('transactions.viaEdenRPC')
        else:
            print(colors.FAIL+"Block", block_number, "is NOT an Eden block!"+colors.END)
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        print("Error: "+str(e)+" @ block number: "+str(block_number))

    end = time.time()
    collection = mongo_connection["flashbots"]["eden_private_blocks_status"]
    collection.insert_one({"block_number": block_number, "execution_time": end-start})
    # Indexing...
    if 'block_number' not in collection.index_information():
        collection.create_index('block_number')

    return end - start

def init_process():
    global mongo_connection

    mongo_connection = pymongo.MongoClient("mongodb://"+MONGO_HOST+":"+str(MONGO_PORT), maxPoolSize=None)

def main():
    if len(sys.argv) != 2:
        print(colors.FAIL+"Error: Please provide a block range to be crawled: 'python3 "+sys.argv[0]+" <BLOCK_RANGE_START>:<BLOCK_RANGE_END>'"+colors.END)
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
    print("Running detection of Eden Network private blocks with "+str(multiprocessing.cpu_count())+" CPUs")
    print("Initializing workers...")
    with multiprocessing.Pool(processes=multiprocessing.cpu_count(), initializer=init_process, initargs=()) as pool:
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
