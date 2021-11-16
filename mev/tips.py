#!/usr/bin/env python3

from argparse import ArgumentParser, Namespace
import logging
import json
import os
import sys
from typing import Dict

import pandas as pd

if os.getenv("WEB3_INFURA_PROJECT_ID"):
    from web3.auto.infura import w3
else:
    from web3.auto import w3

log = logging.getLogger(__name__)

def calculate_tip_arg(args: Namespace):
    return calculate_tip(args.data_file)

def calculate_tip(filepath: str) -> float:
    log.debug("Connected to ETH provider: %s", w3.isConnected())
    # return w3.eth.block_number
    with open(filepath, 'r') as f:
        return calculate_tip_dataframe(json.load(f))


def calculate_tip_dataframe(flashbots_blocks: Dict) -> float:
    for block in flashbots_blocks['blocks']:
        import pdb; pdb.set_trace()
        for bundle in block:
            expense = bundle.txs[0].spent
            revenue = bundle.txs[-1].sold
            profit_pre_fee = revenue - expense # difference is amount made from arbitrage (or frontrunning)
            mining_fee = sum([tx.miner_reward for tx in bundle.txs])
    profit_true = profit_pre_fee - mining_fee
    return 0.0


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

if __name__ == '__main__':
    main()
