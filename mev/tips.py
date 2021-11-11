#!/usr/bin/env python3

from argparse import ArgumentParser, Namespace
import logging
import sys

import pandas as pd
from web3 import Web3

log = logging.getLogger(__name__)

infura_url = "https://mainnet.infura.io/v3/0f0ac9aba45a4143b6707971db4d6b70"
web3 = Web3(Web3.HTTPProvider(infura_url))

def calcuate_tip(filepath: str) -> float:
    return calculate_tip_dataframe(pd.read_json(filepath))


def calculate_tip_dataframe(df: pd.DataFrame) -> float:
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

    tip = calcuate_tip(args.data_file)
    print(web3.isConnected())
    print(tip)

if __name__ == '__main__':
    main()
