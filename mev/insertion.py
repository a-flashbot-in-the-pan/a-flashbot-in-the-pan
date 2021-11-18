#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from argparse import ArgumentParser
import logging
import os
import sys
import time
import numpy
import decimal
import pymongo
import requests
import multiprocessing

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from .utils.settings import *
from .utils.utils import colors, get_prices, get_one_eth_to_usd, TRANSFER, TOKEN_PURCHASE, ETH_PURCHASE

log = logging.getLogger(__name__)

if os.getenv("WEB3_INFURA_PROJECT_ID"):
    from web3.auto.infura import w3
else:
    from web3.auto import w3

TOKEN_AMOUNT_DELTA = 0.01 # Maximum difference between buying and selling amount of tokens. Default value is 1%.

def get_transaction(transactions, transaction_hash):
    for transaction in transactions:
        if transaction.hash == transaction_hash:
            return transaction
    return None

def analyze_block_for_insertion(w3, block, transactions, token_transfer_events, uniswap_purchase_events, prices):
    insertions = list()
    whales = set()
    attackers = set()
    transfer_to = {}
    asset_transfers = {}
    block_number = block["number"]

    for event in token_transfer_events:
        # Ignore Wrapped ETH and Bancor ETH token transfers
        if (event["address"].lower() != "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2" and
            event["address"].lower() != "0xc0829421c1d260bd3cb3e0f06cfe2d52db2ce315"):

            if event["data"].replace("0x", "") and len(event["topics"]) == 3:
                _from  = Web3.toChecksumAddress("0x"+event["topics"][1].hex().replace("0x", "")[24:64])
                _to    = Web3.toChecksumAddress("0x"+event["topics"][2].hex().replace("0x", "")[24:64])
                _value = int(event["data"].replace("0x", "")[0:64], 16)

                if _value > 0 and _from != _to:
                    if (event["address"]+_from in transfer_to and
                        transfer_to[event["address"]+_from]["transactionIndex"] + 1 < event["transactionIndex"]):

                        event_a1 = transfer_to[event["address"]+_from]
                        event_a2 = event

                        _from_a1  = Web3.toChecksumAddress("0x"+event_a1["topics"][1].hex().replace("0x", "")[24:64])
                        _to_a1    = Web3.toChecksumAddress("0x"+event_a1["topics"][2].hex().replace("0x", "")[24:64])
                        _value_a1 = int(event_a1["data"].replace("0x", "")[0:64], 16)

                        _from_a2  = Web3.toChecksumAddress("0x"+event_a2["topics"][1].hex().replace("0x", "")[24:64])
                        _to_a2    = Web3.toChecksumAddress("0x"+event_a2["topics"][2].hex().replace("0x", "")[24:64])
                        _value_a2 = int(event_a2["data"].replace("0x", "")[0:64], 16)

                        delta = abs(_value_a2 - _value_a1)/max(_value_a2, _value_a1)
                        if delta <= TOKEN_AMOUNT_DELTA:

                            # Search for whale
                            event_w = None
                            for asset_transfer in asset_transfers[event["address"]]:
                                if (transfer_to[event["address"]+_from]["transactionIndex"] < asset_transfer["transactionIndex"] and
                                                                  event["transactionIndex"] > asset_transfer["transactionIndex"] and
                                    asset_transfer["transactionHash"].hex() not in attackers):

                                    _from_w  = Web3.toChecksumAddress("0x"+asset_transfer["topics"][1].hex().replace("0x", "")[24:64])
                                    _to_w    = Web3.toChecksumAddress("0x"+asset_transfer["topics"][2].hex().replace("0x", "")[24:64])
                                    _value_w = int(asset_transfer["data"].replace("0x", "")[0:64], 16)

                                    if _from_a1 == _from_w and _from_w == _to_a2 and _value_w > 0:
                                        event_w = asset_transfer

                            if event_w:
                                whales.add(event_w["transactionHash"].hex())

                                if event_a1["transactionHash"].hex() not in whales and event_a2["transactionHash"].hex() not in whales:
                                    _from_w  = Web3.toChecksumAddress("0x"+event_w["topics"][1].hex().replace("0x", "")[24:64])
                                    _to_w    = Web3.toChecksumAddress("0x"+event_w["topics"][2].hex().replace("0x", "")[24:64])
                                    _value_w = int(event_w["data"].replace("0x", "")[0:64], 16)

                                    tx1      = get_transaction(transactions, event_a1["transactionHash"])
                                    whale_tx = get_transaction(transactions, event_w["transactionHash"])
                                    tx2      = get_transaction(transactions, event_a2["transactionHash"])

                                    if  (tx1["from"] != whale_tx["from"] and tx2["from"] != whale_tx["from"]) and \
                                        ((tx1["gasPrice"]  > whale_tx["gasPrice"] and tx2["gasPrice"] <= whale_tx["gasPrice"]) or \
                                         (tx1["transactionIndex"] + 1 == whale_tx["transactionIndex"] and whale_tx["transactionIndex"] == tx2["transactionIndex"] - 1)):

                                        if tx1["to"] == whale_tx["to"] == tx2["to"] and tx1["from"] != tx2["from"]:
                                            continue

                                        # Get token address and name
                                        token_address = event_w["address"]
                                        try:
                                            token_contract = w3.eth.contract(address=token_address, abi=[{"constant":True,"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"payable":False,"stateMutability":"view","type":"function"}])
                                            token_name = token_contract.functions.name().call()
                                        except:
                                            try:
                                                token_contract = w3.eth.contract(address=token_address, abi=[{"name": "name", "outputs": [{"type": "bytes32", "name": "out"}], "inputs": [], "constant": True, "payable": False, "type": "function", "gas": 1623}])
                                                token_name = token_contract.functions.name().call().decode("utf-8").replace(u"\u0000", "")
                                            except:
                                                token_name = token_address

                                        # Get exchange address and name
                                        exchange_address = Web3.toChecksumAddress("0x"+event_w["topics"][1].hex().replace("0x", "")[24:64])
                                        exchange_name = None
                                        # Uniswap V2 and SushiSwap
                                        if not exchange_name:
                                            try:
                                                exchange_contract = w3.eth.contract(address=exchange_address, abi=[{"constant":True,"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"payable":False,"stateMutability":"view","type":"function"}])
                                                exchange_name = exchange_contract.functions.name().call()
                                                if exchange_name.startswith("SushiSwap"):
                                                    exchange_name = "SushiSwap"
                                            except:
                                                pass
                                        # Uniswap V1
                                        if not exchange_name:
                                            try:
                                                exchange_contract = w3.eth.contract(address=exchange_address, abi=[{"name": "name", "outputs": [{"type": "bytes32", "name": "out"}], "inputs": [], "constant": True, "payable": False, "type": "function", "gas": 1623}])
                                                exchange_name = exchange_contract.functions.name().call().decode("utf-8").replace(u"\u0000", "")
                                            except:
                                                pass
                                        # Bancor
                                        if not exchange_name:
                                            try:
                                                exchange_contract = w3.eth.contract(address=exchange_address, abi=[{"constant": True, "inputs": [], "name": "converterType", "outputs": [{"name": "", "type": "string"}], "payable": False, "stateMutability": "view", "type": "function"}])
                                                exchange_name = exchange_contract.functions.converterType().call().capitalize()
                                                if exchange_name.startswith("Bancor"):
                                                    exchange_name = "Bancor"
                                            except:
                                                pass
                                        # Etherscan
                                        if not exchange_name:
                                            try:
                                                response = requests.get("https://api.etherscan.io/api?module=contract&action=getsourcecode&address="+exchange_address+"&apikey="+ETHERSCAN_API_KEY).json()
                                                exchange_name = response["result"][0]["ContractName"]
                                                if exchange_name.startswith("Bancor"):
                                                    exchange_name = "Bancor"
                                            except:
                                                pass
                                        if not exchange_name:
                                            exchange_name = exchange_address

                                        receipt1 = w3.eth.getTransactionReceipt(tx1["hash"])
                                        cost1 = receipt1["gasUsed"]*tx1["gasPrice"]
                                        receipt2 = w3.eth.getTransactionReceipt(tx2["hash"])
                                        cost2 = receipt2["gasUsed"]*tx2["gasPrice"]
                                        total_cost = cost1+cost2

                                        gain = None
                                        eth_spent, eth_received, eth_whale = 0, 0, 0
                                        tx1_event, tx2_event, whale_event = None, None, None
                                        for transfer_event in token_transfer_events:
                                            if   (not tx1_event and transfer_event["transactionHash"] == tx1["hash"] and transfer_event["address"] == "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2" or # Wrapped ETH
                                                  not tx1_event and transfer_event["transactionHash"] == tx1["hash"] and transfer_event["address"] == "0xc0829421C1d260BD3cB3E0F06cfE2D52db2cE315"):  # Bancor ETH Token
                                                tx1_event = transfer_event
                                            elif (not tx2_event and transfer_event["transactionHash"] == tx2["hash"] and transfer_event["address"] == "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2" or # Wrapped ETH
                                                  not tx2_event and transfer_event["transactionHash"] == tx2["hash"] and transfer_event["address"] == "0xc0829421C1d260BD3cB3E0F06cfE2D52db2cE315"):  # Bancor ETH Token
                                                tx2_event = transfer_event
                                            elif (not whale_event and transfer_event["transactionHash"] == whale_tx["hash"] and transfer_event["address"] == "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2" or # Wrapped ETH
                                                  not whale_event and transfer_event["transactionHash"] == whale_tx["hash"] and transfer_event["address"] == "0xc0829421C1d260BD3cB3E0F06cfE2D52db2cE315"):  # Bancor ETH Token
                                                whale_event = transfer_event
                                            if tx1_event and tx2_event and whale_event:
                                                break
                                        if tx1_event and tx2_event and whale_event:
                                            eth_spent = int(tx1_event["data"].replace("0x", "")[0:64], 16)
                                            eth_received = int(tx2_event["data"].replace("0x", "")[0:64], 16)
                                            eth_whale = int(whale_event["data"].replace("0x", "")[0:64], 16)
                                            gain = eth_received - eth_spent
                                        else:
                                            exchange_events = []
                                            exchange_events += w3.eth.filter({"fromBlock": block_number, "toBlock": block_number, "topics": [TOKEN_PURCHASE]}).get_all_entries()
                                            exchange_events += w3.eth.filter({"fromBlock": block_number, "toBlock": block_number, "topics": [ETH_PURCHASE]}).get_all_entries()
                                            for exchange_event in exchange_events:
                                                if   exchange_event["transactionHash"] == tx1["hash"]:
                                                    tx1_event = exchange_event
                                                elif exchange_event["transactionHash"] == tx2["hash"]:
                                                    tx2_event = exchange_event
                                                elif exchange_event["transactionHash"] == whale_tx["hash"]:
                                                    whale_event = exchange_event
                                                if tx1_event and tx2_event and whale_event:
                                                    break
                                            if tx1_event and tx2_event and tx1_event["address"] == tx2_event["address"] and tx1_event["topics"][0].hex() == TOKEN_PURCHASE and tx2_event["topics"][0].hex() == ETH_PURCHASE:
                                                eth_spent = int(tx1_event["topics"][2].hex(), 16)
                                                eth_received = int(tx2_event["topics"][3].hex(), 16)
                                                eth_whale = int(tx1_event["topics"][2].hex(), 16)
                                                gain = eth_received - eth_spent

                                        if gain != None:
                                            attackers.add(event_a1["transactionHash"].hex())
                                            attackers.add(event_a2["transactionHash"].hex())

                                            log.info("   Index Block Number \t Transaction Hash \t\t\t\t\t\t\t From \t\t\t\t\t\t To \t\t\t\t\t\t Gas Price \t Exchange (Token)")
                                            log.info("1. "+str(tx1["transactionIndex"])+" \t "+str(tx1["blockNumber"])+" \t "+tx1["hash"].hex()+" \t "+tx1["from"]+" \t "+tx1["to"]+" \t "+str(tx1["gasPrice"]))
                                            log.info(colors.INFO+"W: "+str(whale_tx["transactionIndex"])+" \t "+str(whale_tx["blockNumber"])+" \t "+whale_tx["hash"].hex()+" \t "+whale_tx["from"]+" \t "+whale_tx["to"]+" \t "+str(whale_tx["gasPrice"])+" \t "+exchange_name+" ("+token_name+")"+colors.END)
                                            log.info("2. "+str(tx2["transactionIndex"])+" \t "+str(tx2["blockNumber"])+" \t "+tx2["hash"].hex()+" \t "+tx2["from"]+" \t "+tx2["to"]+" \t "+str(tx2["gasPrice"]))

                                            log.info("Cost: "+str(Web3.fromWei(total_cost, 'ether'))+" ETH")

                                            if gain > 0:
                                                log.info("Gain: "+str(Web3.fromWei(gain, 'ether'))+" ETH")
                                            else:
                                                log.info("Gain: -"+str(Web3.fromWei(abs(gain), 'ether'))+" ETH")

                                            profit = gain - total_cost
                                            block = w3.eth.getBlock(block_number)
                                            one_eth_to_usd_price = decimal.Decimal(float(get_one_eth_to_usd(block["timestamp"], prices)))
                                            if profit >= 0:
                                                profit_usd = Web3.fromWei(profit, 'ether') * one_eth_to_usd_price
                                                log.info(colors.OK+"Profit: "+str(Web3.fromWei(profit, 'ether'))+" ETH ("+str(profit_usd)+" USD)"+colors.END)
                                            else:
                                                profit_usd = -Web3.fromWei(abs(profit), 'ether') * one_eth_to_usd_price
                                                log.info(colors.FAIL+"Profit: -"+str(Web3.fromWei(abs(profit), 'ether'))+" ETH ("+str(profit_usd)+" USD)"+colors.END)

                                            # Save finding to results
                                            tx1 = dict(tx1)
                                            del tx1["blockNumber"]
                                            del tx1["blockHash"]
                                            del tx1["r"]
                                            del tx1["s"]
                                            del tx1["v"]
                                            tx1["value"] = str(tx1["value"])
                                            tx1["hash"] = tx1["hash"].hex()

                                            whale_tx = dict(whale_tx)
                                            del whale_tx["blockNumber"]
                                            del whale_tx["blockHash"]
                                            del whale_tx["r"]
                                            del whale_tx["s"]
                                            del whale_tx["v"]
                                            whale_tx["value"] = str(whale_tx["value"])
                                            whale_tx["hash"] = whale_tx["hash"].hex()

                                            tx2 = dict(tx2)
                                            del tx2["blockNumber"]
                                            del tx2["blockHash"]
                                            del tx2["r"]
                                            del tx2["s"]
                                            del tx2["v"]
                                            tx2["value"] = str(tx2["value"])
                                            tx2["hash"] = tx2["hash"].hex()

                                            if gain >= 0:
                                                gain = Web3.fromWei(gain, 'ether')
                                            else:
                                                gain = -Web3.fromWei(abs(gain), 'ether')

                                            if profit >= 0:
                                                profit = Web3.fromWei(profit, 'ether')
                                            else:
                                                profit = -Web3.fromWei(abs(profit), 'ether')

                                            interface = "bot"
                                            if (tx1["to"] == whale_tx["to"] == tx2["to"] or
                                                _to_a1 == tx1["from"] and _from_a2 == tx2["from"]):
                                                interface = "exchange"

                                            bot_address = None
                                            if interface == "bot" and _from_a2 == _to_a1:
                                                bot_address = _to_a1

                                            same_sender = False
                                            if tx1["from"] == tx2["from"]:
                                                same_sender = True

                                            same_receiver = False
                                            if tx1["to"] == tx2["to"]:
                                                same_receiver = True

                                            same_token_amount = False
                                            if _value_a1 == _value_a2:
                                                same_token_amount = True

                                            finding = {
                                                "block_number": block_number,
                                                "block_timestamp": block["timestamp"],
                                                "first_transaction": tx1,
                                                "whale_transaction": whale_tx,
                                                "second_transaction": tx2,
                                                "eth_usd_price": float(one_eth_to_usd_price),
                                                "cost_eth": float(Web3.fromWei(total_cost, 'ether')),
                                                "cost_usd": float(Web3.fromWei(total_cost, 'ether') * one_eth_to_usd_price),
                                                "gain_eth": float(gain),
                                                "gain_usd": float(gain * one_eth_to_usd_price),
                                                "profit_eth": float(profit),
                                                "profit_usd": float(profit_usd),
                                                "exchange_address": exchange_address,
                                                "exchange_name": exchange_name,
                                                "token_address": token_address,
                                                "token_name": token_name,
                                                "first_transaction_eth_amount": str(eth_spent),
                                                "whale_transaction_eth_amount": str(eth_whale),
                                                "second_transaction_eth_amount": str(eth_received),
                                                "first_transaction_token_amount": str(_value_a1),
                                                "whale_transaction_token_amount": str(_value_w),
                                                "second_transaction_token_amount": str(_value_a2),
                                                "interface": interface,
                                                "bot_address": bot_address,
                                                "same_sender": same_sender,
                                                "same_receiver": same_receiver,
                                                "same_token_amount": same_token_amount
                                            }
                                            insertions.append(finding)

                    transfer_to[event["address"]+_to] = event
                    if event["address"] not in asset_transfers:
                        asset_transfers[event["address"]] = []
                    asset_transfers[event["address"]].append(event)
    return insertions

def main(block_range_start, block_range_end):
    if w3.isConnected():
        log.info("Connected to "+w3.clientVersion)
    else:
        log.error(colors.FAIL+"Error: Could not connect to the provider!"+colors.END)

    start_total = time.time()
    execution_times = list()
    for block_number in range(block_range_start, block_range_end+1):
        log.info("Analyzing block number: "+str(block_number))
        start = time.time()
        token_transfer_events = []
        uniswap_purchase_events = []
        try:
            token_transfer_events += w3.eth.filter({"fromBlock": block_number, "toBlock": block_number, "topics": [TRANSFER]}).get_all_entries()
            uniswap_purchase_events += w3.eth.filter({"fromBlock": block_number, "toBlock": block_number, "topics": [TOKEN_PURCHASE]}).get_all_entries()
            uniswap_purchase_events += w3.eth.filter({"fromBlock": block_number, "toBlock": block_number, "topics": [ETH_PURCHASE]}).get_all_entries()
        except Exception as e:
            log.error(colors.FAIL+"Error: "+str(e)+", block number: "+str(block_number)+colors.END)
            execution_times.append(time.time() - start)
            continue
        block = w3.eth.getBlock(block_number, True)
        prices = get_prices()
        execution_times.append(analyze_block_for_insertion(w3, block, block.transactions, token_transfer_events, uniswap_purchase_events, prices))
    end_total = time.time()
    log.info("Total execution time: %s", str(end_total - start_total))

def main_args(args):
    main(args.block_range_start, args.block_range_end)

if __name__ == "__main__":
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
        "block_range_start",
        type=int,
        help="The first block in the block range to analyze",
    )
    parser.add_argument(
        "block_range_end",
        type=int,
        help="The last block in the block range to analyze",
    )

    args = parser.parse_args()
    logging.basicConfig(stream=sys.stdout, filemode="w", level=args.log_level.upper())
    main(args.block_range_start, args.block_range_end)
