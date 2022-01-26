#!/usr/bin/env python3

from argparse import ArgumentParser, Namespace
from itertools import chain
import json
import logging
import os
from pprint import pprint
import sys
from typing import Dict, List, Union

import pandas as pd
from pymongo import MongoClient
from pymongo.collection import Collection


# from .utils.utils import (
#     OUTPUT_DIR,
#     convert_wei_to_eth,
#     get_prices,
#     TRANSFER,
#     TOKEN_PURCHASE,
#     ETH_PURCHASE,
# )


MONGODB_ENDPOINT = os.getenv("MONGODB_ENDPOINT")
MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD")
MONGODB_USERNAME = os.getenv("MONGODB_USERNAME")

log = logging.getLogger(__name__)

# fb_blocks = None


def build_indexed_flashbots_dict(original_dict):
    log.info("Building tx-indexed set of flashbots blocks")
    tx_indexed_dict = {}
    for bundle in original_dict:
        for tx in bundle["transactions"]:
            tx_indexed_dict[tx["transaction_hash"]] = bundle

    return tx_indexed_dict


# def get_flashbots_blocks(fb_blocks_file="resources/all_blocks"):
#     global fb_blocks
#     log.debug("Getting Flashbots blocks")
#     if not fb_blocks:
#         log.info("Parsing Flashbots file, only done on first request")
#         with open(fb_blocks_file, "r") as f:
#             original_dict = json.load(f)

#         fb_blocks = build_indexed_flashbots_dict(original_dict)

#     return fb_blocks


# def is_flashbots_tx(tx):
#     return tx in fb_blocks


def get_tx_ids(mev_attempt):
    return (
        mev_attempt["first_transaction"]["hash"],
        mev_attempt["second_transaction"]["hash"],
    )


def get_db_and_collection():
    log.info("Connecting to MongoDB")
    client = MongoClient(
        MONGODB_ENDPOINT, username=MONGODB_USERNAME, password=MONGODB_PASSWORD
    )
    log.debug("Retieving DB object and collection object")
    return (client.flashbots, client.flashbots.confirmed_mevs)


def extract_mev_tx_ids(mev_attempts: Collection):
    log.info("First call to extract_mev_tx_ids()")
    for mev_attempt in mev_attempts.find():
        log.debug("Iteration in extract_mv_tx_ids()")
        yield from get_tx_ids(mev_attempt)


def main_flashbots(args):
    logging.basicConfig(stream=sys.stdout, filemode="w", level=args.log_level.upper())
    db, measured_mev_attempts = get_db_and_collection()
    # measured_mev_attempts = collection.find_one()
    # fb = get_flashbots_blocks(fb_blocks_file="resources/all_blocks.1-25-22.json")

    are_flashbots_txs = [
        tx for tx in extract_mev_tx_ids(measured_mev_attempts) if is_flashbots_tx(tx)
    ]

    import pdb

    pdb.set_trace()
    pprint(tx)
    # pprint(fb)

    # print(is_flashbots_tx(record))

    print("Hiya")
