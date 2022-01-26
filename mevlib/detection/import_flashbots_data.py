#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import pymongo
import requests
import subprocess

MONGO_HOST = "pf.uni.lux"
MONGO_PORT = 27017

MAX_BLOCK_RANGE = 14000000

def main():
    # Download latest "all_blocks" file
    subprocess.run(["rm", "all_blocks"])
    subprocess.run(["wget", "https://blocks.flashbots.net/v1/all_blocks"])
    # Insert new data
    print("Loading all blocks into memory...")
    with open("all_blocks", "r") as f:
        all_blocks = json.load(f)
        print("Total number of blocks:", len(all_blocks))
        min = None
        max = None
        for block in all_blocks:
            if min == None or block["block_number"] < min:
                min = block["block_number"]
            if max == None or block["block_number"] > max:
                max = block["block_number"]
        print("Smallest flashbots block:", min)
        print("Largest flashbots block:", max)
    # Crawl the API for latest blocks
    print("Connecting to MongoDB...")
    mongo_connection = pymongo.MongoClient("mongodb://"+MONGO_HOST+":"+str(MONGO_PORT), maxPoolSize=None)
    collection = mongo_connection["flashbots"]["all_blocks"]
    before = MAX_BLOCK_RANGE + 1
    while True:
        print("Requesting:", "https://blocks.flashbots.net/v1/blocks?before="+str(before)+"&limit=10000")
        response = requests.get("https://blocks.flashbots.net/v1/blocks?before="+str(before)+"&limit=10000").json()
        for block in response["blocks"]:
            exists = mongo_connection["flashbots"]["all_blocks"].find_one({"block_number": block["block_number"]})
            if not exists:
                print("Adding new block:"+str(block["block_number"]))
                collection.insert_one(block)
                # Indexing...
                if 'block_number' not in collection.index_information():
                    collection.create_index('block_number')
        if response["blocks"][0]["block_number"] > max:
            before = response["blocks"][0]["block_number"]
        else:
            break
    # Clean up
    subprocess.run(["rm", "all_blocks"])

if __name__ == "__main__":
    main()
