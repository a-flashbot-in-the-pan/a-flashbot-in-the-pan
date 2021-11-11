#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import numpy
import decimal
import pymongo
import requests
import multiprocessing

from web3 import Web3

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from utils.settings import *
from utils.utils import colors

TOKEN_AMOUNT_DELTA = 0.01 # Maximum difference between buying and selling amount of tokens. Default value is 1%.

TRANSFER       = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef" # ERC20 "Transfer"
TOKEN_PURCHASE = "0xcd60aa75dea3072fbc07ae6d7d856b5dc5f4eee88854f5b4abf7b680ef8bc50f" # Uniswap V1 "TokenPurchase"
ETH_PURCHASE   = "0x7f4091b46c33e918a0f3aa42307641d17bb67029427a5369e54b353984238705" # Uniswap V1 "ETHPurchase"

def get_transaction(transactions, transaction_hash):
    for transaction in transactions:
        if transaction.hash == transaction_hash:
            return transaction
    return None

def analyze_block_for_insertion(w3, block, transactions, token_transfer_events, uniswap_purchase_events):
    results = list()
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

                                    if (tx1["from"]     != whale_tx["from"]     and tx2["from"]     != whale_tx["from"] and
                                        tx1["gasPrice"]  > whale_tx["gasPrice"] and tx2["gasPrice"] <= whale_tx["gasPrice"]):

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

                                        attackers.add(event_a1["transactionHash"].hex())
                                        attackers.add(event_a2["transactionHash"].hex())

                                        print("-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------")
                                        print("   Index Block Number \t Transaction Hash \t\t\t\t\t\t\t From \t\t\t\t\t\t To \t\t\t\t\t\t Gas Price \t Exchange (Token)")
                                        print("1. "+str(tx1["transactionIndex"])+" \t "+str(tx1["blockNumber"])+" \t "+tx1["hash"].hex()+" \t "+tx1["from"]+" \t "+tx1["to"]+" \t "+str(tx1["gasPrice"]))
                                        print(colors.INFO+"W: "+str(whale_tx["transactionIndex"])+" \t "+str(whale_tx["blockNumber"])+" \t "+whale_tx["hash"].hex()+" \t "+whale_tx["from"]+" \t "+whale_tx["to"]+" \t "+str(whale_tx["gasPrice"])+" \t "+exchange_name+" ("+token_name+")"+colors.END)
                                        print("2. "+str(tx2["transactionIndex"])+" \t "+str(tx2["blockNumber"])+" \t "+tx2["hash"].hex()+" \t "+tx2["from"]+" \t "+tx2["to"]+" \t "+str(tx2["gasPrice"]))
                                        print("-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------")

                                        result = dict()
                                        result["attacker_tx_1"] = tx1
                                        result["attacker_tx_2"] = tx2
                                        result["victim_tx"] = whale_tx
                                        results.append(result)

                    transfer_to[event["address"]+_to] = event
                    if event["address"] not in asset_transfers:
                        asset_transfers[event["address"]] = []
                    asset_transfers[event["address"]].append(event)
    return results

def main():
    if len(sys.argv) != 2:
        print(colors.FAIL+"Error: Please provide a block range to be analyzed: 'python3 "+sys.argv[0]+" <BLOCK_RANGE_START>:<BLOCK_RANGE_END>'"+colors.END)
        sys.exit(-1)
    if not ":" in sys.argv[1]:
        print(colors.FAIL+"Error: Please provide a valid block range: 'python3 "+sys.argv[0]+" <BLOCK_RANGE_START>:<BLOCK_RANGE_END>'"+colors.END)
        sys.exit(-2)
    block_range_start, block_range_end = sys.argv[1].split(":")[0], sys.argv[1].split(":")[1]
    if not block_range_start.isnumeric() or not block_range_end.isnumeric():
        print(colors.FAIL+"Error: Please provide integers as block range: 'python3 "+sys.argv[0]+" <BLOCK_RANGE_START>:<BLOCK_RANGE_END>'"+colors.END)
        sys.exit(-3)
    block_range_start, block_range_end = int(block_range_start), int(block_range_end)

    w3 = Web3(PROVIDER)
    if w3.isConnected():
        print("Connected to "+w3.clientVersion)
    else:
        print(colors.FAIL+"Error: Could not connect to the provider!"+colors.END)

    start_total = time.time()
    execution_times = list()
    for block_number in range(block_range_start, block_range_end+1):
        print("Analyzing block number: "+str(block_number))
        start = time.time()
        token_transfer_events = []
        uniswap_purchase_events = []
        try:
            token_transfer_events += w3.eth.filter({"fromBlock": block_number, "toBlock": block_number, "topics": [TRANSFER]}).get_all_entries()
            uniswap_purchase_events += w3.eth.filter({"fromBlock": block_number, "toBlock": block_number, "topics": [TOKEN_PURCHASE]}).get_all_entries()
            uniswap_purchase_events += w3.eth.filter({"fromBlock": block_number, "toBlock": block_number, "topics": [ETH_PURCHASE]}).get_all_entries()
        except Exception as e:
            print(colors.FAIL+"Error: "+str(e)+", block number: "+str(block_number)+colors.END)
            execution_times.append(time.time() - start)
            continue
        block = w3.eth.getBlock(block_number, True)
        execution_times.append(analyze_block_for_insertion(w3, block, block.transactions, token_transfer_events, uniswap_purchase_events))
    end_total = time.time()
    print(len(token_transfer_events))
    print(len(uniswap_purchase_events))
    print("Total execution time: "+str(end_total - start_total))
    print()

if __name__ == "__main__":
    main()
