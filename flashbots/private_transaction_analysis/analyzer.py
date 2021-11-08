#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pymongo
import requests

from web3 import Web3

WEB3_WS_PROVIDER = "ws://pf.uni.lux:8546"
MONGO_HOST = "pf.uni.lux"
MONGO_PORT = 27017

class colors:
    INFO = '\033[94m'
    OK = '\033[92m'
    FAIL = '\033[91m'
    END = '\033[0m'

def main():
    w3 = Web3(Web3.WebsocketProvider(WEB3_WS_PROVIDER))
    if w3.isConnected():
        print("Connected to "+w3.clientVersion)
    else:
        print(colors.FAIL+"Error: Could not connect to "+WEB3_WS_PROVIDER+colors.END)
    mongo_connection = pymongo.MongoClient("mongodb://"+MONGO_HOST+":"+str(MONGO_PORT), maxPoolSize=None)

    print(colors.INFO+"(F) = Flashbots Transaction"+colors.END)
    print(colors.FAIL+"(U) = Unknown Private Transaction"+colors.END)
    print()

    for block_number in range(13576340, 13576340+10):
        block = w3.eth.getBlock(block_number)
        print("Block number:", block["number"])
        flashbots_blocks = None
        flashbots_transactions = set()
        for i in range(len(block["transactions"])):
            tx = block["transactions"][i]
            found = mongo_connection["flashbots"]["observed_transactions_test"].find_one({"hash": tx.hex()})
            if not found:
                if not flashbots_blocks:
                    flashbots_blocks = requests.get("https://blocks.flashbots.net/v1/blocks?block_number="+str(block_number)).json()
                    flashbots_transactions = set()
                    if len(flashbots_blocks["blocks"]) > 0:
                        for b in flashbots_blocks["blocks"]:
                            for t in b["transactions"]:
                                flashbots_transactions.add(t["transaction_hash"])
                if tx.hex() in flashbots_transactions:
                    print(colors.INFO+tx.hex()+' (F) miner: '+block["miner"]+' ('+block["extraData"].decode('utf8').replace("\n", "")+')'+colors.END)
                else:
                    print(colors.FAIL+tx.hex()+' (U) miner: '+block["miner"]+' ('+block["extraData"].decode('utf8').replace("\n", "")+')'+colors.END)
            #else:
            #    print(colors.OK+tx.hex()+colors.END)

if __name__ == "__main__":
    main()
