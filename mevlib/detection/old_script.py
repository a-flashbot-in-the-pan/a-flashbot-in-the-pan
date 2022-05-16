#!/usr/bin/python3
# -*- coding: utf-8 -*-

import csv
import sys
import json
import web3
import enum
import queue
import logging
import pymongo
import threading
import pandas

global w3
#w3 = web3.Web3(web3.Web3.IPCProvider("/home/cool/chain_data/geth/geth.ipc"))
w3 = web3.Web3(web3.Web3.HTTPProvider("http://pf:8545"))

global exitFlag
exitFlag = 0

global unknown_count
unknown_count = 0

global empty_count
empty_count = 0

global gas_price_count
gas_price_count = 0

global parity_default_count
parity_default_count = 0

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

class OrderStrategy(enum.IntEnum):
    UNKNOWN = 0
    EMPTY = 1
    GAS_PRICE = 2
    PARITY_DEFAULT = 3

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

class searchThread(threading.Thread):
   def __init__(self, threadID, queue, database):
      threading.Thread.__init__(self)
      self.threadID = threadID
      self.queue = queue
      self.database = database
   def run(self):
      searchBlock(self.queue, self.database)

def searchBlock(queue, database):
    global unknown_count
    global empty_count
    global gas_price_count
    global parity_default_count

    while not exitFlag:
        queueLock.acquire()
        if not queue.empty():
            blockNumber = queue.get()
            queueLock.release()
            if database["ordering"].count_documents({'block': blockNumber}) != 0:
                logging.info('Already analyzed block '+str(blockNumber)+'...')
            else:
                logging.info('Analyzing block '+str(blockNumber)+'...')
                cursor = database["transactions"].find({"block_number": blockNumber}).sort("transaction_index")

                transaction_hashes = []
                transactions = []
                gas_price_list = []
                senders = []

                for transaction in cursor:
                    if transaction["hash"] not in transaction_hashes:
                        if transaction["from_address"] not in senders:
                            transactions.append(transaction)
                            gas_price_list.append(transaction["gas_price"])
                            senders.append(transaction["from_address"])
                        transaction_hashes.append(transaction["hash"])

                if len(gas_price_list) == 0:
                    empty_count += 1
                    strategy = OrderStrategy.EMPTY
                elif is_sorted_by_gas_price(gas_price_list):
                    gas_price_count += 1
                    strategy = OrderStrategy.GAS_PRICE
                else:
                    transactions_df = pandas.DataFrame(transactions)
                    transactions_single_from_df = remove_txs_from_same_sender(transactions_df)
                    gas_price_list = transactions_single_from_df.gas_price.tolist()[::-1]
                    if is_parity_ordering(gas_price_list):
                        parity_default_count += 1
                        strategy = OrderStrategy.PARITY_DEFAULT
                    else:
                        unknown_count += 1
                        strategy = OrderStrategy.UNKNOWN

                block = database["blocks"].find_one({"number": blockNumber})

                database["ordering"].insert_one({
                    "block": blockNumber,
                    "miner": block["miner"],
                    "timestamp": block["timestamp"],
                    "gas_used": block["gas_used"]/block["gas_limit"],
                    "extra_data": block["extra_data"],
                    "gas_price_list": gas_price_list,
                    "ordering_strategy": strategy,
                    "transaction_count": block["transaction_count"]
                })

                # Indexing...
                if 'block' not in database["ordering"].index_information():
                    database["ordering"].create_index('block', unique=True)
        else:
            queueLock.release()

def remove_txs_from_same_sender(dataframe):
    dataframe_copy = dataframe.copy()
    transaction_counts = dataframe_copy["from_address"].value_counts()
    multi_transaction_accounts = transaction_counts[transaction_counts > 1].keys()
    for account in multi_transaction_accounts:
        indexes = dataframe_copy[dataframe_copy["from_address"] == account].index
        for index in indexes[1:]:
            dataframe_copy = dataframe_copy.drop(index)
    return dataframe_copy

if __name__ == "__main__":
    queueLock = threading.Lock()
    blockQueue = queue.Queue()

    # Create new threads
    threads = []
    threadID = 1
    for i in range(100):
        thread = searchThread(threadID, blockQueue, pymongo.MongoClient("127.0.0.1", 27017)["dex"])
        threads.append(thread)
        thread.start()
        threadID += 1

    startBlockNumber = 6627917
    endBlockNumber = 9000000

    # Fill the queue with block numbers
    total = 0
    queueLock.acquire()
    for i in range(startBlockNumber, endBlockNumber+1):
        blockQueue.put(i)
        total += 1
    queueLock.release()

    logging.info('Analyzing transaction order within blocks '+str(startBlockNumber)+' and '+str(endBlockNumber))

    # Wait for queue to empty
    while not blockQueue.empty():
        pass

    # Notify threads it's time to exit
    exitFlag = 1

    # Wait for all threads to complete
    for t in threads:
       t.join()

    if unknown_count + empty_count + gas_price_count + parity_default_count != total:
        logging.error("Error counts do not match total!!")

    logging.info('Strategy \t \t Count \t Ratio')
    logging.info('----------------------------------------')
    logging.info('UNKNOWN \t \t %d \t %f', unknown_count, unknown_count/total)
    logging.info('EMPTY \t \t %d \t %f', empty_count, empty_count/total)
    logging.info('GAS_PRICE \t \t %d \t %f', gas_price_count, gas_price_count/total)
    logging.info('PARITY_DEFAULT \t %d \t %f', parity_default_count, parity_default_count/total)

    logging.info('Done')
