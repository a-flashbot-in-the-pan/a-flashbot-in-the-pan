#!/usr/bin/env python3

from argparse import ArgumentParser, Namespace
import logging
import json
from mev.insertion import analyze_block_for_insertion
import os
import sys
from typing import Dict

import pandas as pd

from .utils.utils import get_prices, TRANSFER, TOKEN_PURCHASE, ETH_PURCHASE

if os.getenv("WEB3_INFURA_PROJECT_ID"):
    from web3.auto.infura import w3
else:
    from web3.auto import w3

log = logging.getLogger(__name__)


def calculate_tip_arg(args: Namespace):
    # TODO write this to a csv for plotting
    print(f"Total tips={calculate_tip(args.data_file)}")


def calculate_tip(filepath: str) -> float:
    log.debug("Connected to ETH provider: %s", w3.isConnected())
    with open(filepath, "r") as f:
        return calculate_tip_dataframe(json.load(f))


def extract_purchase_events(block_number):
    token_transfer_events = []
    uniswap_purchase_events = []
    default_filter = {
        "fromBlock": block_number,
        "toBlock": block_number,
    }

    default_filter["topics"] = [TRANSFER]
    token_transfer_events.extend(w3.eth.filter(default_filter).get_all_entries())

    default_filter["topics"] = [TOKEN_PURCHASE]
    uniswap_purchase_events.extend(w3.eth.filter(default_filter).get_all_entries())

    default_filter["topics"] = [ETH_PURCHASE]
    uniswap_purchase_events.extend(w3.eth.filter(default_filter).get_all_entries())

    return {
        "token_transfer": token_transfer_events,
        "uniswap_purchase": uniswap_purchase_events,
    }


def calculate_tip_dataframe(flashbots_blocks: Dict) -> float:
    revenue = 0
    mining_fee = 0
    for block in flashbots_blocks["blocks"]:
        events = extract_purchase_events(block["block_number"])
        eth_block = w3.eth.getBlock(block["block_number"], True)
        results = analyze_block_for_insertion(
            w3,
            eth_block,
            eth_block.transactions,
            events["token_transfer"],
            events["uniswap_purchase"],
            get_prices(),
        )

        # Need to subtract miner tips to get true profit
        for tx in results:
            revenue += tx["gain_eth"]

        mining_fee = 0.0
        for tx in block["transactions"]:
            if tx["gas_price"] == "0":
                continue
            mining_fee += float(tx["total_miner_reward"])/1e18


    log.debug(
        "Accrued revenue (pre-fees) of %f, and mining fee of %f", revenue, mining_fee
    )
    return revenue - mining_fee


def parse_args() -> Namespace:
    parser = ArgumentParser()
    parser.add_argument(
        "-l",
        "--log-level",
        type=str,
        help="The log level to be written to stdout.",
        default="INFO",
        choices=["DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"],
    )

    parser.add_argument(
        "data_file",
        type=str,
        help="Path to file containing blocks/transactions to analyze",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(stream=sys.stdout, filemode="w", level=args.log_level.upper())

    tip = calculate_tip(args.data_file)
    print(tip)


if __name__ == "__main__":
    main()
