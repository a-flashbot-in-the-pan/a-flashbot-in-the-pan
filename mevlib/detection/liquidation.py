#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import json
import copy
import numpy
import decimal
import pymongo
import requests
import multiprocessing

from web3 import Web3

PROVIDER = Web3.HTTPProvider("http://pf.uni.lux:8545")

MONGO_HOST = "pf.uni.lux"
MONGO_PORT = 27017

ETHERSCAN_API_KEY = "ANAZQYWNY3ZBIIMIY9P153TE6Y78PUM226"

UPDATE_PRICES = False

class colors:
    INFO = '\033[94m'
    OK = '\033[92m'
    FAIL = '\033[91m'
    END = '\033[0m'

def get_coin_list():
    print("Getting list of coins from CoinGecko.com...")
    response = requests.get("https://api.coingecko.com/api/v3/coins/list?include_platform=true").json()
    coin_list = dict()
    for coin in response:
        if "ethereum" in coin["platforms"] and coin["platforms"]["ethereum"]:
            coin_list[Web3.toChecksumAddress(coin["platforms"]["ethereum"].lower())] = coin["id"]
    return coin_list

def get_prices():
    coin_list = get_coin_list()
    print("Fetching latest prices from CoinGecko.com...")
    from_timestamp = str(1392577232) # Sun Feb 16 2014 19:00:32 GMT+0000
    to_timestamp = str(int(time.time()))
    prices = dict()
    if os.path.exists("prices.json"):
        with open("prices.json", "r") as f:
            prices = json.load(f)
    else:
        prices["eth_to_usd"] = requests.get("https://api.coingecko.com/api/v3/coins/ethereum/market_chart/range?vs_currency=usd&from="+from_timestamp+"&to="+to_timestamp).json()["prices"]
    if UPDATE_PRICES:
        for address in coin_list:
            if address not in prices:
                market_id = coin_list[address]
                print(address, market_id)
                try:
                    reponse = requests.get("https://api.coingecko.com/api/v3/coins/"+market_id+"/market_chart/range?vs_currency=eth&from="+from_timestamp+"&to="+to_timestamp)
                    prices[address] = reponse.json()["prices"]
                    time.sleep(1)
                except Exception as e:
                    print(e+":", reponse.text)
                    with open("prices.json", "w") as f:
                        json.dump(prices, f, indent=2)
                    return prices
        with open("prices.json", "w") as f:
            json.dump(prices, f, indent=2)
    print("Fetched prices for", len(prices), "coins.")
    return prices

def get_price_from_timestamp(timestamp, prices):
    timestamp *= 1000
    one_eth_to_usd = prices[-1][1]
    for index, _ in enumerate(prices):
        if index < len(prices)-1:
            if prices[index][0] <= timestamp and timestamp <= prices[index+1][0]:
                return prices[index][1]
    print(colors.FAIL+"Error: Could not find timestamp. Returning latest price instead."+colors.END)
    print(colors.FAIL+"Please consider updating prices.json!"+colors.END)
    return one_eth_to_usd

# Liquidation platforms
AAVE_V1         = "0x56864757fd5b1fc9f38f5f3a981cd8ae512ce41b902cf73fc506ee369c6bc237" # Aave Protocol V1 (LiquidationCall)
AAVE_V2         = "0xe413a321e8681d831f4dbccbca790d2952b56f977908e45be37335533e005286" # Aave Protocol V2 (LiquidationCall)
COMPOUND_V1     = "0x196893d3172b176a2d1d257008db8d8d97c8d19c485b21a653c309df6503262f" # Compound V1 (LiquidateBorrow)
COMPOUND_V2     = "0x298637f684da70674f26509b10f07ec2fbc77a335ab1e7d6215a4b2484d8bb52" # Compound V2 (LiquidateBorrow)
DYDX_LIQUIDATE  = "0x1b9e65b359b871d74b1af1fc8b13b11635bfb097c4631b091eb762fda7e67dc7" # dYdX (LogLiquidate)
OPYN            = "0xcab8e1abb9f8235c6db895cf185336dc9461aecf477b98c1be83687ee549e66a" # opyn (Liquidate)

# Flash loans
AAVE_FLASH_LOAN = "0x5b8f46461c1dd69fb968f1a003acee221ea3e19540e350233b612ddb43433b55" # Aave Flash Loan (FlashLoan)
DYDX_WITHDRAW   = "0xbc83c08f0b269b1726990c8348ffdf1ae1696244a14868d766e542a2f18cd7d4" # dYdX Flash Loan (LogWithdraw)
DYDX_DEPOSIT    = "0x2bad8bc95088af2c247b30fa2b2e6a0886f88625e0945cd3051008e0e270198f" # dYdX Flash Loan (LogDeposit)

TRANSFER        = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef" # ERC-20 Transfer

def analyze_block(block_number):
    start = time.time()
    print("Analyzing block number: "+str(block_number))

    status = mongo_connection["flashbots"]["liquidation_status"].find_one({"block_number": block_number})
    if status:
        print("Block "+str(block_number)+" already analyzed!")
        return status["execution_time"]

    liquidations = dict()
    flash_loans = dict()
    transaction_index_to_hash = dict()

    try:
        # Search for Aave liquidations
        events = list()
        events += w3.eth.filter({"fromBlock": block_number, "toBlock": block_number, "topics": [AAVE_V1]}).get_all_entries()
        events += w3.eth.filter({"fromBlock": block_number, "toBlock": block_number, "topics": [AAVE_V2]}).get_all_entries()
        for event in events:
            if not event["transactionIndex"] in transaction_index_to_hash:
                transaction_index_to_hash[event["transactionIndex"]] = event["transactionHash"].hex()
            if not event["transactionIndex"] in liquidations:
                liquidations[event["transactionIndex"]] = list()
            if event["topics"][0].hex() == AAVE_V1:
                received_token_address = Web3.toChecksumAddress("0x"+event["topics"][1].hex().replace("0x", "")[24:64]) # _collateral
                debt_token_address     = Web3.toChecksumAddress("0x"+event["topics"][2].hex().replace("0x", "")[24:64]) # _reserve
                liquidated_user        = Web3.toChecksumAddress("0x"+event["topics"][3].hex().replace("0x", "")[24:64]) # _user
                debt_token_amount      = int(event["data"].replace("0x", "")[0:64], 16) # _purchaseAmount
                received_token_amount  = int(event["data"].replace("0x", "")[64:128], 16) # _liquidatedCollateralAmount
                liquidator             = Web3.toChecksumAddress("0x"+event["data"].replace("0x", "")[216:256]) # _liquidator
                try:
                    token_contract = w3.eth.contract(address=debt_token_address, abi=[{"constant":True,"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"payable":False,"stateMutability":"view","type":"function"}])
                    debt_token_name = token_contract.functions.name().call()
                except:
                    try:
                        token_contract = w3.eth.contract(address=debt_token_address, abi=[{"name": "name", "outputs": [{"type": "bytes32", "name": "out"}], "inputs": [], "constant": True, "payable": False, "type": "function", "gas": 1623}])
                        debt_token_name = token_contract.functions.name().call().decode("utf-8").replace(u"\u0000", "")
                    except:
                        debt_token_name = debt_token_address
                try:
                    token_contract = w3.eth.contract(address=received_token_address, abi=[{"constant":True,"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"payable":False,"stateMutability":"view","type":"function"}])
                    received_token_name = token_contract.functions.name().call()
                except:
                    try:
                        token_contract = w3.eth.contract(address=received_token_address, abi=[{"name": "name", "outputs": [{"type": "bytes32", "name": "out"}], "inputs": [], "constant": True, "payable": False, "type": "function", "gas": 1623}])
                        received_token_name = token_contract.functions.name().call().decode("utf-8").replace(u"\u0000", "")
                    except:
                        received_token_name = received_token_address
                try:
                    token_contract = w3.eth.contract(address=debt_token_address, abi=[{"constant":True,"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"payable":False,"stateMutability":"view","type":"function"}])
                    debt_token_decimals = token_contract.functions.decimals().call()
                except:
                    debt_token_decimals = 0
                try:
                    token_contract = w3.eth.contract(address=received_token_address, abi=[{"constant":True,"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"payable":False,"stateMutability":"view","type":"function"}])
                    received_token_decimals = token_contract.functions.decimals().call()
                except:
                    received_token_decimals = 0
                liquidations[event["transactionIndex"]].append({
                    "index": event["logIndex"],
                    "liquidator": liquidator,
                    "liquidated_user": liquidated_user,
                    "debt_token_address": debt_token_address,
                    "debt_token_amount": debt_token_amount,
                    "debt_token_name": debt_token_name,
                    "debt_token_decimals": debt_token_decimals,
                    "debt_token_to_eth_price": None,
                    "received_token_address": received_token_address,
                    "received_token_amount": received_token_amount,
                    "received_token_name": received_token_name,
                    "received_token_decimals": received_token_decimals,
                    "received_token_to_eth_price": None,
                    "protocol_address": event["address"],
                    "protocol_name": "Aave V1"
                })
            else:
                received_token_address = Web3.toChecksumAddress("0x"+event["topics"][1].hex().replace("0x", "")[24:64]) # collateralAsset
                debt_token_address     = Web3.toChecksumAddress("0x"+event["topics"][2].hex().replace("0x", "")[24:64]) # debtAsset
                liquidated_user        = Web3.toChecksumAddress("0x"+event["topics"][3].hex().replace("0x", "")[24:64]) # user
                debt_token_amount      = int(event["data"].replace("0x", "")[0:64], 16) # debtToCover
                received_token_amount  = int(event["data"].replace("0x", "")[64:128], 16) # liquidatedCollateralAmount
                liquidator             = Web3.toChecksumAddress("0x"+event["data"].replace("0x", "")[152:192]) # liquidator
                try:
                    token_contract = w3.eth.contract(address=debt_token_address, abi=[{"constant":True,"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"payable":False,"stateMutability":"view","type":"function"}])
                    debt_token_name = token_contract.functions.name().call()
                except:
                    try:
                        token_contract = w3.eth.contract(address=debt_token_address, abi=[{"name": "name", "outputs": [{"type": "bytes32", "name": "out"}], "inputs": [], "constant": True, "payable": False, "type": "function", "gas": 1623}])
                        debt_token_name = token_contract.functions.name().call().decode("utf-8").replace(u"\u0000", "")
                    except:
                        debt_token_name = debt_token_address
                try:
                    token_contract = w3.eth.contract(address=received_token_address, abi=[{"constant":True,"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"payable":False,"stateMutability":"view","type":"function"}])
                    received_token_name = token_contract.functions.name().call()
                except:
                    try:
                        token_contract = w3.eth.contract(address=received_token_address, abi=[{"name": "name", "outputs": [{"type": "bytes32", "name": "out"}], "inputs": [], "constant": True, "payable": False, "type": "function", "gas": 1623}])
                        received_token_name = token_contract.functions.name().call().decode("utf-8").replace(u"\u0000", "")
                    except:
                        received_token_name = received_token_address
                try:
                    token_contract = w3.eth.contract(address=debt_token_address, abi=[{"constant":True,"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"payable":False,"stateMutability":"view","type":"function"}])
                    debt_token_decimals = token_contract.functions.decimals().call()
                except:
                    debt_token_decimals = 0
                try:
                    token_contract = w3.eth.contract(address=received_token_address, abi=[{"constant":True,"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"payable":False,"stateMutability":"view","type":"function"}])
                    received_token_decimals = token_contract.functions.decimals().call()
                except:
                    received_token_decimals = 0
                liquidations[event["transactionIndex"]].append({
                    "index": event["logIndex"],
                    "liquidator": liquidator,
                    "liquidated_user": liquidated_user,
                    "debt_token_address": debt_token_address,
                    "debt_token_amount": debt_token_amount,
                    "debt_token_name": debt_token_name,
                    "debt_token_decimals": debt_token_decimals,
                    "debt_token_to_eth_price": None,
                    "received_token_address": received_token_address,
                    "received_token_amount": received_token_amount,
                    "received_token_name": received_token_name,
                    "received_token_decimals": received_token_decimals,
                    "received_token_to_eth_price": None,
                    "protocol_address": event["address"],
                    "protocol_name": "Aave V2"
                })

        # Search for Compound liquidations
        events = list()
        events += w3.eth.filter({"fromBlock": block_number, "toBlock": block_number, "topics": [COMPOUND_V1]}).get_all_entries()
        events += w3.eth.filter({"fromBlock": block_number, "toBlock": block_number, "topics": [COMPOUND_V2]}).get_all_entries()
        for event in events:
            if not event["transactionIndex"] in transaction_index_to_hash:
                transaction_index_to_hash[event["transactionIndex"]] = event["transactionHash"].hex()
            if not event["transactionIndex"] in liquidations:
                liquidations[event["transactionIndex"]] = list()
            if event["topics"][0].hex() == COMPOUND_V1:
                print(colors.FAIL+"Error: missing implementation of compound version 1"+colors.END)
            else:
                liquidator             = Web3.toChecksumAddress("0x"+event["data"].replace("0x", "")[24:64]) # liquidator
                liquidated_user        = Web3.toChecksumAddress("0x"+event["data"].replace("0x", "")[88:128]) # borrower
                debt_token_amount      = int(event["data"].replace("0x", "")[128:192], 16) # repayAmount
                received_token_address = Web3.toChecksumAddress("0x"+event["data"].replace("0x", "")[216:256]) # cTokenCollateral
                received_token_amount  = int(event["data"].replace("0x", "")[256:320], 16)
                try:
                    token_contract = w3.eth.contract(address=received_token_address, abi=[{"constant":True,"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"payable":False,"stateMutability":"view","type":"function"}])
                    received_token_name = token_contract.functions.name().call()
                except:
                    try:
                        token_contract = w3.eth.contract(address=received_token_address, abi=[{"name": "name", "outputs": [{"type": "bytes32", "name": "out"}], "inputs": [], "constant": True, "payable": False, "type": "function", "gas": 1623}])
                        received_token_name = token_contract.functions.name().call().decode("utf-8").replace(u"\u0000", "")
                    except:
                        received_token_name = received_token_address
                try:
                    token_contract = w3.eth.contract(address=received_token_address, abi=[{"constant":True,"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"payable":False,"stateMutability":"view","type":"function"}])
                    received_token_decimals = token_contract.functions.decimals().call()
                except:
                    received_token_decimals = 0
                liquidations[event["transactionIndex"]].append({
                    "index": event["logIndex"],
                    "liquidator": liquidator,
                    "liquidated_user": liquidated_user,
                    "debt_token_address": "",
                    "debt_token_amount": debt_token_amount,
                    "debt_token_name": "",
                    "debt_token_decimals": 0,
                    "debt_token_to_eth_price": None,
                    "received_token_address": received_token_address,
                    "received_token_amount": received_token_amount,
                    "received_token_name": received_token_name,
                    "received_token_decimals": received_token_decimals,
                    "received_token_to_eth_price": None,
                    "protocol_address": event["address"],
                    "protocol_name": "Compound V2"
                })

        # Search for dYdX liquidations
        events = w3.eth.filter({"fromBlock": block_number, "toBlock": block_number, "topics": [DYDX_LIQUIDATE]}).get_all_entries()
        for event in events:
            if not event["transactionIndex"] in transaction_index_to_hash:
                transaction_index_to_hash[event["transactionIndex"]] = event["transactionHash"].hex()
            if not event["transactionIndex"] in liquidations:
                liquidations[event["transactionIndex"]] = list()
            if event["topics"][0].hex() == COMPOUND_V1:
                print(colors.FAIL+"Error: missing implementation of dydx"+colors.END)

        # Search for opyn liquidations
        events = w3.eth.filter({"fromBlock": block_number, "toBlock": block_number, "topics": [OPYN]}).get_all_entries()
        for event in events:
            if not event["transactionIndex"] in transaction_index_to_hash:
                transaction_index_to_hash[event["transactionIndex"]] = event["transactionHash"].hex()
            if not event["transactionIndex"] in liquidations:
                liquidations[event["transactionIndex"]] = list()
            if event["topics"][0].hex() == COMPOUND_V1:
                print(colors.FAIL+"Error: missing implementation of opyn"+colors.END)

        # Search for ERC-20 transfers
        events = w3.eth.filter({"fromBlock": block_number, "toBlock": block_number, "topics": [TRANSFER]}).get_all_entries()
        for event in events:
            if event["transactionIndex"] in liquidations:
                transfer_to    = Web3.toChecksumAddress("0x"+event["topics"][2].hex().replace("0x", "")[24:64])
                transfer_value = int(event["data"].replace("0x", "")[0:64], 16)
                for liquidation in  liquidations[event["transactionIndex"]]:
                    if liquidation["debt_token_address"] == "" and liquidation["debt_token_amount"] == transfer_value and liquidation["protocol_address"] == transfer_to:
                        liquidation["debt_token_address"] = event["address"]
                        try:
                            token_contract = w3.eth.contract(address=liquidation["debt_token_address"], abi=[{"constant":True,"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"payable":False,"stateMutability":"view","type":"function"}])
                            liquidation["debt_token_name"] = token_contract.functions.name().call()
                        except:
                            try:
                                token_contract = w3.eth.contract(address=liquidation["debt_token_address"], abi=[{"name": "name", "outputs": [{"type": "bytes32", "name": "out"}], "inputs": [], "constant": True, "payable": False, "type": "function", "gas": 1623}])
                                liquidation["debt_token_name"] = token_contract.functions.name().call().decode("utf-8").replace(u"\u0000", "")
                            except:
                                liquidation["debt_token_name"] = liquidation["debt_token_address"]
                        try:
                            token_contract = w3.eth.contract(address=liquidation["debt_token_address"], abi=[{"constant":True,"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"payable":False,"stateMutability":"view","type":"function"}])
                            liquidation["debt_token_decimals"] = token_contract.functions.decimals().call()
                        except:
                            liquidation["debt_token_decimals"] = 0


        # Search for Aave flash loans
        events = w3.eth.filter({"fromBlock": block_number, "toBlock": block_number, "topics": [AAVE_FLASH_LOAN]}).get_all_entries()
        for event in events:
            if not event["transactionIndex"] in transaction_index_to_hash:
                transaction_index_to_hash[event["transactionIndex"]] = event["transactionHash"].hex()
            if not event["transactionIndex"] in flash_loans:
                flash_loans[event["transactionIndex"]] = dict()
            _reserve  = Web3.toChecksumAddress("0x"+event["topics"][2].hex().replace("0x", "")[24:64])
            _amount   = int(event["data"].replace("0x", "")[0:64], 16)
            _totalFee = int(event["data"].replace("0x", "")[64:128], 16)
            try:
                token_contract = w3.eth.contract(address=_reserve, abi=[{"constant":True,"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"payable":False,"stateMutability":"view","type":"function"}])
                token_name = token_contract.functions.name().call()
            except:
                try:
                    token_contract = w3.eth.contract(address=_reserve, abi=[{"name": "name", "outputs": [{"type": "bytes32", "name": "out"}], "inputs": [], "constant": True, "payable": False, "type": "function", "gas": 1623}])
                    token_name = token_contract.functions.name().call().decode("utf-8").replace(u"\u0000", "")
                except:
                    token_name = _reserve
            try:
                token_contract = w3.eth.contract(address=_reserve, abi=[{"constant":True,"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"payable":False,"stateMutability":"view","type":"function"}])
                token_decimals = token_contract.functions.decimals().call()
            except:
                token_decimals = 0
            flash_loans[event["transactionIndex"]][_reserve] = {"token_name": token_name, "token_decimals": token_decimals, "amount": _amount, "fee": _totalFee, "platform": "Aave"}

        # Search for dYdX flash loans
        events = w3.eth.filter({"fromBlock": block_number, "toBlock": block_number, "topics": [DYDX_WITHDRAW]}).get_all_entries()
        for event in events:
            if not event["transactionIndex"] in transaction_index_to_hash:
                transaction_index_to_hash[event["transactionIndex"]] = event["transactionHash"].hex()
            if not event["transactionIndex"] in flash_loans:
                flash_loans[event["transactionIndex"]] = dict()
            dydx_contract = w3.eth.contract(address=event["address"], abi=[{"constant":True,"inputs":[{"name":"marketId","type":"uint256"}],"name":"getMarketTokenAddress","outputs":[{"name":"","type":"address"}],"payable":False,"stateMutability":"view","type":"function"}])
            _market_id = int(event["data"].replace("0x", "")[1*64:1*64+64], 16)
            _market = dydx_contract.functions.getMarketTokenAddress(_market_id).call()
            _amount = int(event["data"].replace("0x", "")[3*64:3*64+64], 16)
            try:
                token_contract = w3.eth.contract(address=_market, abi=[{"constant":True,"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"payable":False,"stateMutability":"view","type":"function"}])
                token_name = token_contract.functions.name().call()
            except:
                try:
                    token_contract = w3.eth.contract(address=_market, abi=[{"name": "name", "outputs": [{"type": "bytes32", "name": "out"}], "inputs": [], "constant": True, "payable": False, "type": "function", "gas": 1623}])
                    token_name = token_contract.functions.name().call().decode("utf-8").replace(u"\u0000", "")
                except:
                    token_name = _market
            try:
                token_contract = w3.eth.contract(address=_market, abi=[{"constant":True,"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"payable":False,"stateMutability":"view","type":"function"}])
                token_decimals = token_contract.functions.decimals().call()
            except:
                token_decimals = 0
            flash_loans[event["transactionIndex"]][_market] = {"token_name": token_name, "token_decimals": token_decimals, "amount": _amount, "fee": None, "platform": "dYdX"}
        events = w3.eth.filter({"fromBlock": block_number, "toBlock": block_number, "topics": [DYDX_DEPOSIT]}).get_all_entries()
        for event in events:
            if not event["transactionIndex"] in transaction_index_to_hash:
                transaction_index_to_hash[event["transactionIndex"]] = event["transactionHash"].hex()
            if not event["transactionIndex"] in flash_loans:
                flash_loans[event["transactionIndex"]] = dict()
            dydx_contract = w3.eth.contract(address=event["address"], abi=[{"constant":True,"inputs":[{"name":"marketId","type":"uint256"}],"name":"getMarketTokenAddress","outputs":[{"name":"","type":"address"}],"payable":False,"stateMutability":"view","type":"function"}])
            _market_id = int(event["data"].replace("0x", "")[1*64:1*64+64], 16)
            _market = dydx_contract.functions.getMarketTokenAddress(_market_id).call()
            _amount = int(event["data"].replace("0x", "")[3*64:3*64+64], 16)
            if _market in flash_loans[event["transactionIndex"]] and flash_loans[event["transactionIndex"]][_market]["platform"] == "dYdX" and flash_loans[event["transactionIndex"]][_market]["fee"] == None:
                flash_loans[event["transactionIndex"]][_market]["fee"] = _amount - flash_loans[event["transactionIndex"]][_market]["amount"]
        flash_loans_copy = copy.deepcopy(flash_loans)
        for transaction_index in flash_loans_copy:
            for market in flash_loans_copy[transaction_index]:
                if flash_loans_copy[transaction_index][market]["fee"] == None:
                    del flash_loans[transaction_index][market]

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        print(colors.FAIL+"Error: "+str(e)+", block number: "+str(block_number)+colors.END)
        return time.time() - start

    try:
        for tx_index in liquidations:
            for liquidation in liquidations[tx_index]:
                if liquidation["debt_token_address"] == "":
                    liquidation["debt_token_name"] = "Ether"
                    liquidation["debt_token_decimals"] = 18
                if liquidation["received_token_address"] == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
                    liquidation["received_token_name"] = "Ether"
                    liquidation["received_token_decimals"] = 18
                print()
                print(colors.FAIL+"Liquidation detected: "+colors.INFO+transaction_index_to_hash[tx_index]+" ("+str(block_number)+")"+colors.END)
                print(colors.INFO+"Liquidator Repay"+colors.END, decimal.Decimal(liquidation["debt_token_amount"]) / 10**liquidation["debt_token_decimals"], liquidation["debt_token_name"], colors.INFO+"To"+colors.END, liquidation["protocol_name"])
                print(colors.INFO+"Liquidation"+colors.END, decimal.Decimal(liquidation["received_token_amount"]) / 10**liquidation["received_token_decimals"], liquidation["received_token_name"], colors.INFO+"On"+colors.END, liquidation["protocol_name"])
                block = w3.eth.getBlock(block_number)
                one_eth_to_usd_price = decimal.Decimal(float(get_price_from_timestamp(block["timestamp"], prices["eth_to_usd"])))
                # Compute cost
                tx = w3.eth.getTransaction(transaction_index_to_hash[tx_index])
                receipt = w3.eth.getTransactionReceipt(tx["hash"])
                cost = receipt["gasUsed"] * tx["gasPrice"]
                # Check if liquidation is part of a flashbots bundle
                flashbots_block = mongo_connection["flashbots"]["flashbots_blocks"].find_one({"block_number": block_number})
                flashbots_transactions = set()
                if flashbots_block:
                    for t in flashbots_block["transactions"]:
                        flashbots_transactions.add(t["transaction_hash"])
                flashbots_bundle = False
                frontrunning_liquidation = False
                if transaction_index_to_hash[tx_index] in flashbots_transactions:
                    flashbots_bundle = True
                    # Is this frontrunning liquidation?
                    bundles = dict()
                    bundle_index = None
                    for t in flashbots_block["transactions"]:
                        if not t["bundle_index"] in bundles:
                            bundles[t["bundle_index"]] = list()
                        bundles[t["bundle_index"]].append(t)
                        if tx["hash"].hex() == t["transaction_hash"]:
                            bundle_index = t["bundle_index"]
                    if len(bundles[bundle_index]) == 2 and bundles[bundle_index][1]["transaction_hash"] == tx["hash"].hex():
                        frontrunning_liquidation = True
                        print(colors.FAIL+"!!! Flashbots Bundle (Frontrunning Liquidation) !!!"+colors.END)
                    else:
                        print(colors.FAIL+"!!! Flashbots Bundle !!!"+colors.END)
                flashbots_coinbase_transfer = 0
                if flashbots_bundle:
                    for t in flashbots_block["transactions"]:
                        if t["transaction_hash"] == tx["hash"].hex():
                            flashbots_coinbase_transfer += int(t["coinbase_transfer"])
                    cost += flashbots_coinbase_transfer
                if cost != 0:
                    cost_eth = Web3.fromWei(cost, 'ether')
                    cost_usd = cost_eth * one_eth_to_usd_price
                else:
                    cost_eth = 0
                    cost_usd = 0
                # Check if liquidation is sponsered by a flash loan
                flash_loan = None
                if tx_index in flash_loans:
                    print(colors.FAIL+"!!! Flash Loan !!!"+colors.END)
                    for token_address in flash_loans[tx_index]:
                        flash_loan = flash_loans[tx_index][token_address]
                        amount = decimal.Decimal(flash_loans[tx_index][token_address]["amount"]) / 10**flash_loans[tx_index][token_address]["token_decimals"]
                        fee = decimal.Decimal(flash_loans[tx_index][token_address]["fee"]) / 10**flash_loans[tx_index][token_address]["token_decimals"]
                        flash_loan["token_to_eth_price"] = None
                        flash_loan["fee_eth"] = None
                        if token_address in prices:
                            token_prices = prices[token_address]
                            flash_loan["token_to_eth_price"] = decimal.Decimal(float(get_price_from_timestamp(block["timestamp"], token_prices)))
                            flash_loan["fee_eth"] = fee * flash_loan["token_to_eth_price"]
                            cost_eth += flash_loan["fee_eth"]
                        print(colors.INFO+"Borrowed"+colors.END, amount, flash_loans[tx_index][token_address]["token_name"], colors.INFO+"From"+colors.END, flash_loans[tx_index][token_address]["platform"], colors.INFO+"For"+colors.END, fee, flash_loans[tx_index][token_address]["token_name"], colors.INFO+"Fee"+colors.END)
                        flash_loan["token_address"] = token_address
                        break
                if liquidation["debt_token_address"] in prices:
                    debt_tokens = decimal.Decimal(liquidation["debt_token_amount"]) / 10**liquidation["debt_token_decimals"]
                    token_prices = prices[liquidation["debt_token_address"]]
                    liquidation["debt_token_to_eth_price"] = decimal.Decimal(float(get_price_from_timestamp(block["timestamp"], token_prices)))
                    cost_eth += debt_tokens * liquidation["debt_token_to_eth_price"]
                    cost_usd = cost_eth * one_eth_to_usd_price
                elif liquidation["debt_token_address"] == "":
                    cost_eth += Web3.fromWei(liquidation["debt_token_amount"], 'ether')
                    cost_usd = cost_eth * one_eth_to_usd_price
                else:
                    cost_eth = None
                    cost_usd = None
                if flashbots_coinbase_transfer != 0:
                    flashbots_coinbase_transfer_eth = Web3.fromWei(flashbots_coinbase_transfer, 'ether')
                    flashbots_coinbase_transfer_usd = flashbots_coinbase_transfer_eth * one_eth_to_usd_price
                else:
                    flashbots_coinbase_transfer_eth = 0
                    flashbots_coinbase_transfer_usd = 0
                if cost_eth == None and cost_usd == None:
                    print(colors.FAIL+"Cost could not be computed!"+colors.END)
                else:
                    if not flashbots_bundle:
                        print("Cost: "+str(cost_eth)+" ETH ("+str(cost_usd)+" USD)")
                    else:
                        print("Cost: "+str(cost_eth)+" ETH ("+str(cost_usd)+" USD) "+colors.INFO+"(Coinbase Transfer "+str(flashbots_coinbase_transfer_eth)+" ETH / "+str(flashbots_coinbase_transfer_usd)+" USD)"+colors.END)
                # Compute gain
                gain_eth = None
                gain_usd = None
                if liquidation["received_token_address"] in prices:
                    received_tokens = decimal.Decimal(liquidation["received_token_amount"]) / 10**liquidation["received_token_decimals"]
                    token_prices = prices[liquidation["received_token_address"]]
                    liquidation["received_token_to_eth_price"] = decimal.Decimal(float(get_price_from_timestamp(block["timestamp"], token_prices)))
                    gain_eth = received_tokens * liquidation["received_token_to_eth_price"]
                    gain_usd = gain_eth * one_eth_to_usd_price
                elif liquidation["received_token_address"] == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
                    gain_eth = Web3.fromWei(liquidation["received_token_amount"], 'ether')
                    gain_usd = gain_eth * one_eth_to_usd_price
                if gain_eth == None and gain_usd == None:
                    print(colors.FAIL+"Gain could not be computed!"+colors.END)
                else:
                    print("Gain: "+str(gain_eth)+" ETH ("+str(gain_usd)+" USD)")
                # Compute profit
                profit_eth = None
                profit_usd = None
                if gain_eth == None or cost_eth == None:
                    print(colors.FAIL+"Profit could not be computed!"+colors.END)
                else:
                    profit_eth = gain_eth - cost_eth
                    profit_usd = profit_eth * one_eth_to_usd_price
                    if profit_eth >= 0:
                        print(colors.OK+"Profit: "+str(profit_eth)+" ETH ("+str(profit_usd)+" USD)"+colors.END)
                    else:
                        print(colors.FAIL+"Profit: "+str(profit_eth)+" ETH ("+str(profit_usd)+" USD)"+colors.END)

                tx = dict(tx)
                del tx["blockNumber"]
                del tx["blockHash"]
                del tx["r"]
                del tx["s"]
                del tx["v"]
                tx["value"] = str(tx["value"])
                tx["hash"] = tx["hash"].hex()

                if flash_loan:
                    flash_loan["amount"] = str(flash_loan["amount"])
                    flash_loan["fee"] = str(flash_loan["fee"])
                    flash_loan["token_to_eth_price"] = float(flash_loan["token_to_eth_price"]) if flash_loan["token_to_eth_price"] != None else flash_loan["token_to_eth_price"]
                    flash_loan["fee_eth"] = float(flash_loan["fee_eth"]) if flash_loan["fee_eth"] != None else flash_loan["fee_eth"]

                finding = {
                    "block_number": block_number,
                    "block_timestamp": block["timestamp"],
                    "miner": block["miner"],
                    "transaction": tx,
                    "liquidator": liquidation["liquidator"],
                    "liquidated_user": liquidation["liquidated_user"],
                    "debt_token_address": liquidation["debt_token_address"],
                    "debt_token_amount": str(liquidation["debt_token_amount"]),
                    "debt_token_name": liquidation["debt_token_name"],
                    "debt_token_decimals": liquidation["debt_token_decimals"],
                    "debt_token_to_eth_price": float(liquidation["debt_token_to_eth_price"]) if liquidation["debt_token_to_eth_price"] != None else liquidation["debt_token_to_eth_price"],
                    "received_token_address": liquidation["received_token_address"],
                    "received_token_amount": str(liquidation["received_token_amount"]),
                    "received_token_name": liquidation["received_token_name"],
                    "received_token_decimals": liquidation["received_token_decimals"],
                    "received_token_to_eth_price": float(liquidation["received_token_to_eth_price"]) if liquidation["received_token_to_eth_price"] != None else liquidation["received_token_to_eth_price"],
                    "protocol_address": liquidation["protocol_address"],
                    "protocol_name": liquidation["protocol_name"],
                    "eth_usd_price": float(one_eth_to_usd_price),
                    "cost_eth": float(cost_eth) if cost_eth != None else cost_eth,
                    "cost_usd": float(cost_usd) if cost_usd != None else cost_usd,
                    "gain_eth": float(gain_eth) if gain_eth != None else gain_eth,
                    "gain_usd": float(gain_usd) if gain_usd != None else gain_usd,
                    "profit_eth": float(profit_eth) if profit_eth != None else profit_eth,
                    "profit_usd": float(profit_usd) if profit_usd != None else profit_usd,
                    "flashbots_bundle": flashbots_bundle,
                    "flashbots_coinbase_transfer": float(flashbots_coinbase_transfer_eth),
                    "frontrunning_liquidation": frontrunning_liquidation,
                    "flash_loan": flash_loan
                }

                collection = mongo_connection["flashbots"]["liquidation_results"]
                collection.insert_one(finding)
                # Indexing...
                if 'block_number' not in collection.index_information():
                    collection.create_index('block_number')
                    collection.create_index('block_timestamp')
                    collection.create_index('miner')
                    collection.create_index('eth_usd_price')
                    collection.create_index('cost_eth')
                    collection.create_index('cost_usd')
                    collection.create_index('gain_eth')
                    collection.create_index('gain_usd')
                    collection.create_index('profit_eth')
                    collection.create_index('profit_usd')
                    collection.create_index('transaction.hash')
                    collection.create_index('flashbots_bundle')
                    collection.create_index('flashbots_coinbase_transfer')
                    collection.create_index('frontrunning_liquidation')
                    collection.create_index('flash_loan.platform')
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        print("Error: "+str(e)+" @ block number: "+str(block_number))

    end = time.time()
    collection = mongo_connection["flashbots"]["liquidation_status"]
    collection.insert_one({"block_number": block_number, "execution_time": end-start})
    # Indexing...
    if 'block_number' not in collection.index_information():
        collection.create_index('block_number')

    return end - start

def init_process(_prices, _coin_list):
    global w3
    global prices
    global coin_list
    global mongo_connection

    w3 = Web3(PROVIDER)
    if w3.isConnected():
        print("Connected worker to "+w3.clientVersion)
    else:
        print(colors.FAIL+"Error: Could not connect to Ethereum client. Please check the provider!"+colors.END)
    prices = _prices
    coin_list = _coin_list
    mongo_connection = pymongo.MongoClient("mongodb://"+MONGO_HOST+":"+str(MONGO_PORT), maxPoolSize=None)

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

    execution_times = []
    prices = get_prices()
    coin_list = get_coin_list()
    if sys.platform.startswith("linux"):
        multiprocessing.set_start_method('fork')
    print("Running detection of liquidation with "+str(multiprocessing.cpu_count())+" CPUs")
    print("Initializing workers...")
    # 11181773 Flash loan liquidation
    with multiprocessing.Pool(processes=multiprocessing.cpu_count(), initializer=init_process, initargs=(prices,coin_list,)) as pool:
        start_total = time.time()
        execution_times += pool.map(analyze_block, range(block_range_start, block_range_end+1))
        end_total = time.time()
        print("Total execution time: "+str(end_total - start_total))
        print()
        if execution_times:
            print("Max execution time: "+str(numpy.max(execution_times)))
            print("Mean execution time: "+str(numpy.mean(execution_times)))
            print("Median execution time: "+str(numpy.median(execution_times)))
            print("Min execution time: "+str(numpy.min(execution_times)))

if __name__ == "__main__":
    main()
