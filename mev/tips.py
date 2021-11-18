#!/usr/bin/env python3

from argparse import ArgumentParser, Namespace
import logging
import json
from mev.insertion import analyze_block_for_insertion
import os
import sys
from typing import Dict, List, Union

import pandas as pd

from .utils.utils import (
    OUTPUT_DIR,
    convert_wei_to_eth,
    get_prices,
    TRANSFER,
    TOKEN_PURCHASE,
    ETH_PURCHASE,
)

if os.getenv("WEB3_INFURA_PROJECT_ID"):
    from web3.auto.infura import w3
else:
    from web3.auto import w3

log = logging.getLogger(__name__)


def generate_csv_filename(df: pd.DataFrame) -> str:
    filename = f"{OUTPUT_DIR}/tips-{df.iloc[0]['block_number']}-{df.iloc[-1]['block_number']}.csv"
    print(f"Writing file to: {filename}")
    return filename


def calculate_tip_arg(args: Namespace):
    df = calculate_tips_from_file(args.data_file)
    tips = (df["pre_fee_revenue"] - df["mining_fee"]).sum()
    log.info(f"Total tips={tips}")

    # write this to a csv for analysis
    df.to_csv(path_or_buf=generate_csv_filename(df), index=False)


def calculate_tips_from_file(filepath: str) -> pd.DataFrame:
    log.debug("Connected to ETH provider: %s", w3.isConnected())
    with open(filepath, "r") as f:
        return calculate_tips(json.load(f))


def extract_purchase_events(block_number: int) -> Dict:
    token_transfer_events = []
    uniswap_purchase_events = []
    default_filter: Dict[str, Union[List[str], int]] = {
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


def calculate_tips(flashbots_blocks: Dict) -> pd.DataFrame:
    result_df = pd.DataFrame(columns=["block_number", "pre_fee_revenue", "mining_fee"])
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

        # This is revenue before miner fees are subtracted
        revenue = sum([tx["gain_eth"] for tx in results])

        mining_fee = sum(
            [
                convert_wei_to_eth(float(tx["total_miner_reward"]))
                for tx in block["transactions"]
                if tx["gas_price"] != "0"
            ]
        )
        row = pd.Series(
            [block["block_number"], revenue, mining_fee], index=result_df.columns
        )
        result_df = result_df.append(row, ignore_index=True)

    log.debug(
        "Accrued revenue (pre-fees) of %f, and mining fee of %f",
        result_df["pre_fee_revenue"].sum(),
        result_df["mining_fee"].sum(),
    )
    return result_df


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

    tip = calculate_tips_from_file(args.data_file)
    print(tip)


if __name__ == "__main__":
    main()
