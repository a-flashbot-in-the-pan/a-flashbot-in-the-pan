#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import copy
import numpy
import decimal
import pymongo
import multiprocessing

from web3 import Web3

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from utils.settings import *
from utils.utils import colors, get_coin_list, get_prices, get_price_from_timestamp

# Decentralized Exchanges
SWAP_UNISWAP_V2 = "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822" # UNISWAP V2/Sushiswap (Swap)
SWAP_UNISWAP_V3 = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67" # UNISWAP V3 (Swap)
BALANCER        = "0x908fb5ee8f16c6bc9bc3690973819f32a4d4b10188134543c88706e0e1d43378" # BALANCER (LOG_SWAP)
CURVE_1         = "0xd013ca23e77a65003c2c659c5442c00c805371b7fc1ebd4c206c41d1536bd90b" # CURVE (TokenExchangeUnderlying)
CURVE_2         = "0x8b3e96f2b889fa771c53c981b40daf005f63f637f1869f707052d15a3dd97140" # CURVE (TokenExchange)
BANCOR          = "0x276856b36cbc45526a0ba64f44611557a2a8b68662c5388e9fe6d72e86e1c8cb" # BANCOR (Conversion)
ZERO_EX_1       = "0x6869791f0a34781b29882982cc39e882768cf2c96995c2a110c577c53bc932d5" # 0x Protocol (Fill)
ZERO_EX_2       = "0xab614d2b738543c0ea21f56347cf696a3a0c42a7cbec3212a5ca22a4dcff2124" # 0x Protocol
ZERO_EX_3       = "0x829fa99d94dc4636925b38632e625736a614c154d55006b7ab6bea979c210c32" # 0x Protocol

# Flash loans
AAVE_FLASH_LOAN = "0x5b8f46461c1dd69fb968f1a003acee221ea3e19540e350233b612ddb43433b55" # Aave Flash Loan (FlashLoan)
DYDX_WITHDRAW   = "0xbc83c08f0b269b1726990c8348ffdf1ae1696244a14868d766e542a2f18cd7d4" # dYdX Flash Loan (LogWithdraw)
DYDX_DEPOSIT    = "0x2bad8bc95088af2c247b30fa2b2e6a0886f88625e0945cd3051008e0e270198f" # dYdX Flash Loan (LogDeposit)

def toSigned256(n):
    n = n & 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
    return (n ^ 0x8000000000000000000000000000000000000000000000000000000000000000) - 0x8000000000000000000000000000000000000000000000000000000000000000

def analyze_block(block_number):
    start = time.time()
    print("Analyzing block number: "+str(block_number))

    status = mongo_connection["flashbots"]["arbitrage_status"].find_one({"block_number": block_number})
    if status:
        print("Block "+str(block_number)+" already analyzed!")
        return status["execution_time"]

    swaps = dict()
    flash_loans = dict()
    transaction_index_to_hash = dict()

    try:
        # Search for Uniswap V2/Sushiswap swaps
        events = w3.eth.filter({"fromBlock": block_number, "toBlock": block_number, "topics": [SWAP_UNISWAP_V2]}).get_all_entries()
        for event in events:
            if not event["transactionIndex"] in transaction_index_to_hash:
                transaction_index_to_hash[event["transactionIndex"]] = event["transactionHash"].hex()
            if not event["transactionIndex"] in swaps:
                swaps[event["transactionIndex"]] = list()
            _amount0In  = int(event["data"].replace("0x", "")[0:64], 16)
            _amount1In  = int(event["data"].replace("0x", "")[64:128], 16)
            _amount0Out = int(event["data"].replace("0x", "")[128:192], 16)
            _amount1Out = int(event["data"].replace("0x", "")[192:256], 16)
            exchange_contract = w3.eth.contract(address=event["address"], abi=[
                {"constant":True,"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"payable":False,"stateMutability":"view","type":"function"},
                {"inputs":[],"name":"token0","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},
                {"inputs":[],"name":"token1","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"}
            ])
            try:
                _token0 = exchange_contract.functions.token0().call()
                _token1 = exchange_contract.functions.token1().call()
                _name = exchange_contract.functions.name().call()
                if _name.startswith("SushiSwap"):
                    _name = "SushiSwap"
                if _amount0In == 0 and _amount1Out == 0:
                    amount_in  = _amount1In
                    amount_out = _amount0Out
                    in_token = _token1
                    out_token = _token0
                elif _amount1In == 0 and _amount0Out == 0:
                    amount_in  = _amount0In
                    amount_out = _amount1Out
                    in_token = _token0
                    out_token = _token1
                else:
                    continue
                try:
                    token_contract = w3.eth.contract(address=in_token, abi=[{"constant":True,"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"payable":False,"stateMutability":"view","type":"function"}])
                    in_token_name = token_contract.functions.name().call()
                except:
                    try:
                        token_contract = w3.eth.contract(address=in_token, abi=[{"name": "name", "outputs": [{"type": "bytes32", "name": "out"}], "inputs": [], "constant": True, "payable": False, "type": "function", "gas": 1623}])
                        in_token_name = token_contract.functions.name().call().decode("utf-8").replace(u"\u0000", "")
                    except:
                        in_token_name = in_token
                try:
                    token_contract = w3.eth.contract(address=out_token, abi=[{"constant":True,"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"payable":False,"stateMutability":"view","type":"function"}])
                    out_token_name = token_contract.functions.name().call()
                except:
                    try:
                        token_contract = w3.eth.contract(address=out_token, abi=[{"name": "name", "outputs": [{"type": "bytes32", "name": "out"}], "inputs": [], "constant": True, "payable": False, "type": "function", "gas": 1623}])
                        out_token_name = token_contract.functions.name().call().decode("utf-8").replace(u"\u0000", "")
                    except:
                        out_token_name = out_token
                in_token_name = in_token_name.replace(".", " ").replace("$", "")
                out_token_name = out_token_name.replace(".", " ").replace("$", "")
                swaps[event["transactionIndex"]].append({"index": event["logIndex"], "in_token": in_token, "in_token_name": in_token_name, "out_token": out_token, "out_token_name": out_token_name, "in_amount": amount_in, "out_amount": amount_out, "exchange": event["address"], "exchange_name": _name})
                swaps[event["transactionIndex"]] = sorted(swaps[event["transactionIndex"]], key=lambda d: d["index"])
            except:
                pass

        # Search for Uniswap V3 swaps
        events = w3.eth.filter({"fromBlock": block_number, "toBlock": block_number, "topics": [SWAP_UNISWAP_V3]}).get_all_entries()
        for event in events:
            if not event["transactionIndex"] in transaction_index_to_hash:
                transaction_index_to_hash[event["transactionIndex"]] = event["transactionHash"].hex()
            if not event["transactionIndex"] in swaps:
                swaps[event["transactionIndex"]] = list()
            _amount0   = toSigned256(int(event["data"].replace("0x", "")[0:64], 16))
            _amount1   = toSigned256(int(event["data"].replace("0x", "")[64:128], 16))
            exchange_contract = w3.eth.contract(address=event["address"], abi=[
                {"inputs":[],"name":"token0","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},
                {"inputs":[],"name":"token1","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"}
            ])
            _token0 = exchange_contract.functions.token0().call()
            _token1 = exchange_contract.functions.token1().call()
            if _amount0 < 0:
                amount_in = _amount1
                amount_out = abs(_amount0)
                in_token = _token1
                out_token = _token0
            else:
                amount_in = _amount0
                amount_out = abs(_amount1)
                in_token = _token0
                out_token = _token1
            try:
                token_contract = w3.eth.contract(address=in_token, abi=[{"constant":True,"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"payable":False,"stateMutability":"view","type":"function"}])
                in_token_name = token_contract.functions.name().call()
            except:
                try:
                    token_contract = w3.eth.contract(address=in_token, abi=[{"name": "name", "outputs": [{"type": "bytes32", "name": "out"}], "inputs": [], "constant": True, "payable": False, "type": "function", "gas": 1623}])
                    in_token_name = token_contract.functions.name().call().decode("utf-8").replace(u"\u0000", "")
                except:
                    in_token_name = in_token
            try:
                token_contract = w3.eth.contract(address=out_token, abi=[{"constant":True,"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"payable":False,"stateMutability":"view","type":"function"}])
                out_token_name = token_contract.functions.name().call()
            except:
                try:
                    token_contract = w3.eth.contract(address=out_token, abi=[{"name": "name", "outputs": [{"type": "bytes32", "name": "out"}], "inputs": [], "constant": True, "payable": False, "type": "function", "gas": 1623}])
                    out_token_name = token_contract.functions.name().call().decode("utf-8").replace(u"\u0000", "")
                except:
                    out_token_name = out_token
            in_token_name = in_token_name.replace(".", " ").replace("$", "")
            out_token_name = out_token_name.replace(".", " ").replace("$", "")
            swaps[event["transactionIndex"]].append({"index": event["logIndex"], "in_token": in_token, "in_token_name": in_token_name, "out_token": out_token, "out_token_name": out_token_name, "in_amount": amount_in, "out_amount": amount_out, "exchange": event["address"], "exchange_name": "Uniswap V3"})
            swaps[event["transactionIndex"]] = sorted(swaps[event["transactionIndex"]], key=lambda d: d["index"])

        # Search for Balancer swaps
        events = w3.eth.filter({"fromBlock": block_number, "toBlock": block_number, "topics": [BALANCER]}).get_all_entries()
        for event in events:
            if not event["transactionIndex"] in transaction_index_to_hash:
                transaction_index_to_hash[event["transactionIndex"]] = event["transactionHash"].hex()
            if not event["transactionIndex"] in swaps:
                swaps[event["transactionIndex"]] = list()
            _tokenIn        = Web3.toChecksumAddress("0x"+event["topics"][2].hex().replace("0x", "")[24:64])
            _tokenOut       = Web3.toChecksumAddress("0x"+event["topics"][3].hex().replace("0x", "")[24:64])
            _tokenAmountIn  = int(event["data"].replace("0x", "")[0:64], 16)
            _tokenAmountOut = int(event["data"].replace("0x", "")[64:128], 16)
            try:
                token_contract = w3.eth.contract(address=_tokenIn, abi=[{"constant":True,"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"payable":False,"stateMutability":"view","type":"function"}])
                in_token_name = token_contract.functions.name().call()
            except:
                try:
                    token_contract = w3.eth.contract(address=_tokenIn, abi=[{"name": "name", "outputs": [{"type": "bytes32", "name": "out"}], "inputs": [], "constant": True, "payable": False, "type": "function", "gas": 1623}])
                    in_token_name = token_contract.functions.name().call().decode("utf-8").replace(u"\u0000", "")
                except:
                    in_token_name = _tokenIn
            try:
                token_contract = w3.eth.contract(address=_tokenOut, abi=[{"constant":True,"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"payable":False,"stateMutability":"view","type":"function"}])
                out_token_name = token_contract.functions.name().call()
            except:
                try:
                    token_contract = w3.eth.contract(address=_tokenOut, abi=[{"name": "name", "outputs": [{"type": "bytes32", "name": "out"}], "inputs": [], "constant": True, "payable": False, "type": "function", "gas": 1623}])
                    out_token_name = token_contract.functions.name().call().decode("utf-8").replace(u"\u0000", "")
                except:
                    out_token_name = _tokenOut
            in_token_name = in_token_name.replace(".", " ").replace("$", "")
            out_token_name = out_token_name.replace(".", " ").replace("$", "")
            swaps[event["transactionIndex"]].append({"index": event["logIndex"], "in_token": _tokenIn, "in_token_name": in_token_name, "out_token": _tokenOut, "out_token_name": out_token_name, "in_amount": _tokenAmountIn, "out_amount": _tokenAmountOut, "exchange": event["address"], "exchange_name": "Balancer"})
            swaps[event["transactionIndex"]] = sorted(swaps[event["transactionIndex"]], key=lambda d: d["index"])

        # Search for Curve swaps
        events = list()
        events += w3.eth.filter({"fromBlock": block_number, "toBlock": block_number, "topics": [CURVE_1]}).get_all_entries()
        events += w3.eth.filter({"fromBlock": block_number, "toBlock": block_number, "topics": [CURVE_2]}).get_all_entries()
        for event in events:
            if not event["transactionIndex"] in transaction_index_to_hash:
                transaction_index_to_hash[event["transactionIndex"]] = event["transactionHash"].hex()
            if not event["transactionIndex"] in swaps:
                swaps[event["transactionIndex"]] = list()
            _sold_id       = int(event["data"].replace("0x", "")[0*64:0*64+64], 16)
            _tokens_sold   = int(event["data"].replace("0x", "")[1*64:1*64+64], 16)
            _bought_id     = int(event["data"].replace("0x", "")[2*64:2*64+64], 16)
            _tokens_bought = int(event["data"].replace("0x", "")[3*64:3*64+64], 16)
            try:
                curve_contract = w3.eth.contract(address=event["address"], abi=[{"name":"underlying_coins","outputs":[{"type":"address","name":"out"}],"inputs":[{"type":"int128","name":"arg0"}],"constant":True,"payable":False,"type":"function","gas":2190}])
                in_token = curve_contract.functions.underlying_coins(_sold_id).call()
                out_token = curve_contract.functions.underlying_coins(_bought_id).call()
            except:
                try:
                    curve_contract = w3.eth.contract(address=event["address"], abi=[{"name":"underlying_coins","outputs":[{"type":"address","name":""}],"inputs":[{"type":"uint256","name":"arg0"}],"stateMutability":"view","type":"function","gas":2340}])
                    in_token = curve_contract.functions.underlying_coins(_sold_id).call()
                    out_token = curve_contract.functions.underlying_coins(_bought_id).call()
                except:
                    try:
                        curve_contract = w3.eth.contract(address=event["address"], abi=[{"name":"coins","outputs":[{"type":"address","name":""}],"inputs":[{"type":"int128","name":"arg0"}],"constant":True,"payable":False,"type":"function","gas":2310}])
                        in_token = curve_contract.functions.coins(min(1, _sold_id)).call()
                        out_token = curve_contract.functions.coins(min(1, _bought_id)).call()
                    except:
                        curve_contract = w3.eth.contract(address=event["address"], abi=[{"name":"coins","outputs":[{"type":"address","name":""}],"inputs":[{"type":"uint256","name":"arg0"}],"stateMutability":"view","type":"function","gas":2250}])
                        in_token = curve_contract.functions.coins(min(1, _sold_id)).call()
                        out_token = curve_contract.functions.coins(min(1, _bought_id)).call()
            try:
                token_contract = w3.eth.contract(address=in_token, abi=[{"constant":True,"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"payable":False,"stateMutability":"view","type":"function"}])
                in_token_name = token_contract.functions.name().call()
            except:
                try:
                    token_contract = w3.eth.contract(address=in_token, abi=[{"name": "name", "outputs": [{"type": "bytes32", "name": "out"}], "inputs": [], "constant": True, "payable": False, "type": "function", "gas": 1623}])
                    in_token_name = token_contract.functions.name().call().decode("utf-8").replace(u"\u0000", "")
                except:
                    in_token_name = in_token
            try:
                token_contract = w3.eth.contract(address=out_token, abi=[{"constant":True,"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"payable":False,"stateMutability":"view","type":"function"}])
                out_token_name = token_contract.functions.name().call()
            except:
                try:
                    token_contract = w3.eth.contract(address=out_token, abi=[{"name": "name", "outputs": [{"type": "bytes32", "name": "out"}], "inputs": [], "constant": True, "payable": False, "type": "function", "gas": 1623}])
                    out_token_name = token_contract.functions.name().call().decode("utf-8").replace(u"\u0000", "")
                except:
                    out_token_name = out_token
            in_token_name = in_token_name.replace(".", " ").replace("$", "")
            out_token_name = out_token_name.replace(".", " ").replace("$", "")
            swaps[event["transactionIndex"]].append({"index": event["logIndex"], "in_token": in_token, "in_token_name": in_token_name, "out_token": out_token, "out_token_name": out_token_name, "in_amount": _tokens_sold, "out_amount": _tokens_bought, "exchange": event["address"], "exchange_name": "Curve"})
            swaps[event["transactionIndex"]] = sorted(swaps[event["transactionIndex"]], key=lambda d: d["index"])

        # Search for Bancor swaps
        events = w3.eth.filter({"fromBlock": block_number, "toBlock": block_number, "topics": [BANCOR]}).get_all_entries()
        for event in events:
            if not event["transactionIndex"] in transaction_index_to_hash:
                transaction_index_to_hash[event["transactionIndex"]] = event["transactionHash"].hex()
            if not event["transactionIndex"] in swaps:
                swaps[event["transactionIndex"]] = list()
            _fromToken = Web3.toChecksumAddress("0x"+event["topics"][1].hex().replace("0x", "")[24:64])
            _toToken = Web3.toChecksumAddress("0x"+event["topics"][2].hex().replace("0x", "")[24:64])
            _amount = int(event["data"].replace("0x", "")[0*64:0*64+64], 16)
            _return = int(event["data"].replace("0x", "")[1*64:1*64+64], 16)
            try:
                token_contract = w3.eth.contract(address=_fromToken, abi=[{"constant":True,"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"payable":False,"stateMutability":"view","type":"function"}])
                in_token_name = token_contract.functions.name().call()
            except:
                try:
                    token_contract = w3.eth.contract(address=_fromToken, abi=[{"name": "name", "outputs": [{"type": "bytes32", "name": "out"}], "inputs": [], "constant": True, "payable": False, "type": "function", "gas": 1623}])
                    in_token_name = token_contract.functions.name().call().decode("utf-8").replace(u"\u0000", "")
                except:
                    in_token_name = _fromToken
            try:
                token_contract = w3.eth.contract(address=_toToken, abi=[{"constant":True,"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"payable":False,"stateMutability":"view","type":"function"}])
                out_token_name = token_contract.functions.name().call()
            except:
                try:
                    token_contract = w3.eth.contract(address=_toToken, abi=[{"name": "name", "outputs": [{"type": "bytes32", "name": "out"}], "inputs": [], "constant": True, "payable": False, "type": "function", "gas": 1623}])
                    out_token_name = token_contract.functions.name().call().decode("utf-8").replace(u"\u0000", "")
                except:
                    out_token_name = _toToken
            if in_token_name.lower() == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE".lower():
                in_token_name = "Ether"
            if out_token_name.lower() == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE".lower():
                out_token_name = "Ether"
            in_token_name = in_token_name.replace(".", " ").replace("$", "")
            out_token_name = out_token_name.replace(".", " ").replace("$", "")
            swaps[event["transactionIndex"]].append({"index": event["logIndex"], "in_token": _fromToken, "in_token_name": in_token_name, "out_token": _toToken, "out_token_name": out_token_name, "in_amount": _amount, "out_amount": _return, "exchange": event["address"], "exchange_name": "Bancor"})
            swaps[event["transactionIndex"]] = sorted(swaps[event["transactionIndex"]], key=lambda d: d["index"])

        # Search for 0x Protocol swaps
        events = list()
        events += w3.eth.filter({"fromBlock": block_number, "toBlock": block_number, "topics": [ZERO_EX_1]}).get_all_entries()
        events += w3.eth.filter({"fromBlock": block_number, "toBlock": block_number, "topics": [ZERO_EX_2]}).get_all_entries()
        events += w3.eth.filter({"fromBlock": block_number, "toBlock": block_number, "topics": [ZERO_EX_3]}).get_all_entries()
        for event in events:
            if not event["transactionIndex"] in transaction_index_to_hash:
                transaction_index_to_hash[event["transactionIndex"]] = event["transactionHash"].hex()
            if not event["transactionIndex"] in swaps:
                swaps[event["transactionIndex"]] = list()
            if event["topics"][0].hex() == ZERO_EX_1:
                index = int(event["data"].replace("0x", "")[0*64:0*64+64], 16) * 2 + 96
                _makerAssetData = Web3.toChecksumAddress("0x"+event["data"].replace("0x", "")[index:index+40])
                index = int(event["data"].replace("0x", "")[1*64:1*64+64], 16) * 2 + 96
                _takerAssetData = Web3.toChecksumAddress("0x"+event["data"].replace("0x", "")[index:index+40])
                _makerAssetFilledAmount = int(event["data"].replace("0x", "")[6*64:6*64+64], 16)
                _takerAssetFilledAmount = int(event["data"].replace("0x", "")[7*64:7*64+64], 16)
            elif event["topics"][0].hex() == ZERO_EX_2:
                _makerAssetData = Web3.toChecksumAddress("0x"+event["data"].replace("0x", "")[4*64+24:4*64+64])
                _takerAssetData = Web3.toChecksumAddress("0x"+event["data"].replace("0x", "")[5*64+24:5*64+64])
                _takerAssetFilledAmount = int(event["data"].replace("0x", "")[6*64:6*64+64], 16)
                _makerAssetFilledAmount = int(event["data"].replace("0x", "")[7*64:7*64+64], 16)
            else:
                _makerAssetData = Web3.toChecksumAddress("0x"+event["data"].replace("0x", "")[3*64+24:3*64+64])
                _takerAssetData = Web3.toChecksumAddress("0x"+event["data"].replace("0x", "")[4*64+24:4*64+64])
                _takerAssetFilledAmount = int(event["data"].replace("0x", "")[5*64:5*64+64], 16)
                _makerAssetFilledAmount = int(event["data"].replace("0x", "")[6*64:6*64+64], 16)
            try:
                token_contract = w3.eth.contract(address=_takerAssetData, abi=[{"constant":True,"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"payable":False,"stateMutability":"view","type":"function"}])
                in_token_name = token_contract.functions.name().call()
            except:
                try:
                    token_contract = w3.eth.contract(address=_takerAssetData, abi=[{"name": "name", "outputs": [{"type": "bytes32", "name": "out"}], "inputs": [], "constant": True, "payable": False, "type": "function", "gas": 1623}])
                    in_token_name = token_contract.functions.name().call().decode("utf-8").replace(u"\u0000", "")
                except:
                    in_token_name = _takerAssetData
            try:
                token_contract = w3.eth.contract(address=_makerAssetData, abi=[{"constant":True,"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"payable":False,"stateMutability":"view","type":"function"}])
                out_token_name = token_contract.functions.name().call()
            except:
                try:
                    token_contract = w3.eth.contract(address=_makerAssetData, abi=[{"name": "name", "outputs": [{"type": "bytes32", "name": "out"}], "inputs": [], "constant": True, "payable": False, "type": "function", "gas": 1623}])
                    out_token_name = token_contract.functions.name().call().decode("utf-8").replace(u"\u0000", "")
                except:
                    out_token_name = _makerAssetData
            in_token_name = in_token_name.replace(".", " ").replace("$", "")
            out_token_name = out_token_name.replace(".", " ").replace("$", "")
            swaps[event["transactionIndex"]].append({"index": event["logIndex"], "in_token": _takerAssetData, "in_token_name": in_token_name, "out_token": _makerAssetData, "out_token_name": out_token_name, "in_amount": _takerAssetFilledAmount, "out_amount": _makerAssetFilledAmount, "exchange": event["address"], "exchange_name": "0x Protocol"})
            swaps[event["transactionIndex"]] = sorted(swaps[event["transactionIndex"]], key=lambda d: d["index"])

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
        print(colors.FAIL+"Error: "+str(e)+" @ block number: "+str(block_number)+colors.END)
        end = time.time()
        return end - start

    try:
        # Search for arbitrage
        for tx_index in swaps:
            if len(swaps[tx_index]) > 1:
                if swaps[tx_index][0]["in_token"] != "" and swaps[tx_index][-1]["out_token"] != "" and (swaps[tx_index][0]["in_token"] == swaps[tx_index][-1]["out_token"] or (swaps[tx_index][0]["in_token"] in ["0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"] and swaps[tx_index][-1]["out_token"] in ["0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"])):
                    valid = True
                    intermediary_swaps = list()
                    intermediary_swaps.append(swaps[tx_index][0])
                    gains = dict()
                    for i in range(1, len(swaps[tx_index])):
                        previous_swap = swaps[tx_index][i-1]
                        current_swap = swaps[tx_index][i]
                        intermediary_swaps.append(current_swap)
                        if previous_swap["out_token"] != current_swap["in_token"]:
                            valid = False
                        if (swaps[tx_index][0]["in_token"] == current_swap["out_token"] or (swaps[tx_index][0]["in_token"] in ["0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"] and current_swap["out_token"] in ["0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"])) and valid:
                            print()
                            print(colors.FAIL+"Arbitrage detected: "+colors.INFO+transaction_index_to_hash[tx_index]+" ("+str(block_number)+")"+colors.END)
                            for swap in intermediary_swaps:
                                if not swap["in_token_name"] in gains:
                                    gains[swap["in_token_name"]] = {"token_address": swap["in_token"], "amount": 0}
                                gains[swap["in_token_name"]]["amount"] -= swap["in_amount"]
                                if not swap["out_token_name"] in gains:
                                    gains[swap["out_token_name"]] = {"token_address": swap["out_token"], "amount": 0}
                                gains[swap["out_token_name"]]["amount"] += swap["out_amount"]
                                if swap["in_token"] == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
                                    in_token_decimals = 18
                                else:
                                    try:
                                        token_contract = w3.eth.contract(address=swap["in_token"], abi=[{"constant":True,"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"payable":False,"stateMutability":"view","type":"function"}])
                                        in_token_decimals = token_contract.functions.decimals().call()
                                    except:
                                        in_token_decimals = 0
                                if swap["out_token"] == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
                                    out_token_decimals = 18
                                else:
                                    try:
                                        token_contract = w3.eth.contract(address=swap["out_token"], abi=[{"constant":True,"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"payable":False,"stateMutability":"view","type":"function"}])
                                        out_token_decimals = token_contract.functions.decimals().call()
                                    except:
                                        out_token_decimals = 0
                                print(colors.INFO+"Swap"+colors.END, decimal.Decimal(swap["in_amount"]) / 10**in_token_decimals, swap["in_token_name"], colors.INFO+"For"+colors.END, decimal.Decimal(swap["out_amount"]) / 10**out_token_decimals, swap["out_token_name"], colors.INFO+"On"+colors.END, swap["exchange_name"])
                            intermediary_swaps = list()
                    if valid:
                        block = w3.eth.getBlock(block_number)
                        one_eth_to_usd_price = decimal.Decimal(float(get_price_from_timestamp(block["timestamp"], prices["eth_to_usd"])))
                        # Check if arbitrage is sponsered by a flash loan
                        if tx_index in flash_loans:
                            for token_address in flash_loans[tx_index]:
                                print(colors.FAIL+"!!! Flash Loan !!!"+colors.END)
                                flash_loan = flash_loans[tx_index][token_address]
                                amount = decimal.Decimal(flash_loans[tx_index][token_address]["amount"]) / 10**flash_loans[tx_index][token_address]["token_decimals"]
                                fee = decimal.Decimal(flash_loans[tx_index][token_address]["fee"]) / 10**flash_loans[tx_index][token_address]["token_decimals"]
                                flash_loan["token_to_eth_price"] = None
                                flash_loan["fee_eth"] = None
                                if token_address in prices:
                                    token_prices = prices[token_address]
                                    flash_loan["token_to_eth_price"] = decimal.Decimal(float(get_price_from_timestamp(block["timestamp"], token_prices)))
                                    flash_loan["fee_eth"] = fee * flash_loan["token_to_eth_price"]
                                print(colors.INFO+"Borrowed"+colors.END, amount, flash_loans[tx_index][token_address]["token_name"], colors.INFO+"From"+colors.END, flash_loans[tx_index][token_address]["platform"], colors.INFO+"For"+colors.END, fee, flash_loans[tx_index][token_address]["token_name"], colors.INFO+"Fee"+colors.END)
                                flash_loan["token_address"] = token_address
                                break
                        # Compute cost
                        tx = w3.eth.getTransaction(transaction_index_to_hash[tx_index])
                        receipt = w3.eth.getTransactionReceipt(tx["hash"])
                        cost = receipt["gasUsed"] * tx["gasPrice"]
                        # Check if arbitrage is part of a flashbots bundle
                        flashbots_block = mongo_connection["flashbots"]["flashbots_blocks"].find_one({"block_number": block_number})
                        flashbots_transactions = set()
                        if flashbots_block:
                            for t in flashbots_block["transactions"]:
                                flashbots_transactions.add(t["transaction_hash"])
                        flashbots_bundle = False
                        frontrunning_arbitrage = False
                        if tx["hash"].hex() in flashbots_transactions:
                            flashbots_bundle = True
                            # Is this frontrunning arbitrage?
                            bundles = dict()
                            bundle_index = None
                            for t in flashbots_block["transactions"]:
                                if not t["bundle_index"] in bundles:
                                    bundles[t["bundle_index"]] = list()
                                bundles[t["bundle_index"]].append(t)
                                if tx["hash"].hex() == t["transaction_hash"]:
                                    bundle_index = t["bundle_index"]
                            if len(bundles[bundle_index]) == 2 and bundles[bundle_index][1]["transaction_hash"] == tx["hash"].hex():
                                frontrunning_arbitrage = True
                                print(colors.FAIL+"!!! Flashbots Bundle (Frontrunning Arbitrage) !!!"+colors.END)
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
                        if flashbots_coinbase_transfer != 0:
                            flashbots_coinbase_transfer_eth = Web3.fromWei(flashbots_coinbase_transfer, 'ether')
                            flashbots_coinbase_transfer_usd = flashbots_coinbase_transfer_eth * one_eth_to_usd_price
                        else:
                            flashbots_coinbase_transfer_eth = 0
                            flashbots_coinbase_transfer_usd = 0
                        if not flashbots_bundle:
                            print("Cost: "+str(cost_eth)+" ETH ("+str(cost_usd)+" USD)")
                        else:
                            print("Cost: "+str(cost_eth)+" ETH ("+str(cost_usd)+" USD) "+colors.INFO+"(Coinbase Transfer "+str(flashbots_coinbase_transfer_eth)+" ETH / "+str(flashbots_coinbase_transfer_usd)+" USD)"+colors.END)
                        # Compute gain
                        print("Tokens Acquired:")
                        gain_eth = 0
                        gain_usd = 0
                        flash_loan = None
                        for coin in gains:
                            if tx_index in flash_loans and gains[coin]["token_address"] in flash_loans[tx_index] and flash_loans[tx_index][gains[coin]["token_address"]]["fee"] != None:
                                gains[coin]["amount"] -= flash_loans[tx_index][gains[coin]["token_address"]]["fee"]
                                if gains[coin]["token_address"] == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
                                    decimals = 18
                                else:
                                    token_contract = w3.eth.contract(address=gains[coin]["token_address"], abi=[{"constant":True,"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"payable":False,"stateMutability":"view","type":"function"}])
                                    try:
                                        decimals = token_contract.functions.decimals().call()
                                    except:
                                        decimals = 0
                                gains[coin]["decimals"] = decimals
                                amount = decimal.Decimal(gains[coin]["amount"]) / 10**decimals
                                gains[coin]["amount"] = float(amount)
                                amount_eth = 0
                                amount_usd = 0
                                if gains[coin]["token_address"] in prices:
                                    token_prices = prices[gains[coin]["token_address"]]
                                    try:
                                        one_token_to_eth_price = decimal.Decimal(float(get_price_from_timestamp(block["timestamp"], token_prices)))
                                    except:
                                        one_token_to_eth_price = 0
                                elif gains[coin]["token_address"] == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
                                    one_token_to_eth_price = decimal.Decimal(float(1.0))
                                else:
                                    one_token_to_eth_price = 0
                                if one_token_to_eth_price:
                                    gains[coin]["one_token_to_eth_price"] = float(one_token_to_eth_price)
                                    if amount != 0:
                                        amount_eth = amount * one_token_to_eth_price
                                        gains[coin]["amount_eth"] = float(amount_eth)
                                    if amount != 0:
                                        amount_usd = amount_eth * one_eth_to_usd_price
                                        gains[coin]["amount_usd"] = float(amount_usd)
                                print("  ", colors.INFO+coin+":"+colors.END, amount, "("+str(amount_eth)+" ETH / "+str(amount_usd)+" USD)", "("+flash_loans[tx_index][gains[coin]["token_address"]]["platform"]+" Flash Loan Fee:", str(flash_loans[tx_index][gains[coin]["token_address"]]["fee"])+")")
                                gain_eth += amount_eth
                                gain_usd += amount_usd
                                flash_loan = flash_loans[tx_index][gains[coin]["token_address"]]
                            else:
                                if gains[coin]["token_address"] == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
                                    decimals = 18
                                else:
                                    token_contract = w3.eth.contract(address=gains[coin]["token_address"], abi=[{"constant":True,"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"payable":False,"stateMutability":"view","type":"function"}])
                                    try:
                                        decimals = token_contract.functions.decimals().call()
                                    except:
                                        decimals = 0
                                gains[coin]["decimals"] = decimals
                                amount = decimal.Decimal(gains[coin]["amount"]) / 10**decimals
                                gains[coin]["amount"] = float(amount)
                                amount_eth = 0
                                amount_usd = 0
                                if gains[coin]["token_address"] in prices:
                                    token_prices = prices[gains[coin]["token_address"]]
                                    try:
                                        one_token_to_eth_price = decimal.Decimal(float(get_price_from_timestamp(block["timestamp"], token_prices)))
                                    except:
                                        one_token_to_eth_price = 0
                                elif gains[coin]["token_address"] == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
                                    one_token_to_eth_price = decimal.Decimal(float(1.0))
                                else:
                                    one_token_to_eth_price = 0
                                if one_token_to_eth_price:
                                    gains[coin]["one_token_to_eth_price"] = float(one_token_to_eth_price)
                                    if amount != 0:
                                        amount_eth = amount * one_token_to_eth_price
                                        gains[coin]["amount_eth"] = float(amount_eth)
                                    if amount != 0:
                                        amount_usd = amount_eth * one_eth_to_usd_price
                                        gains[coin]["amount_usd"] = float(amount_usd)
                                print("  ", colors.INFO+coin+":"+colors.END, amount, "("+str(amount_eth)+" ETH / "+str(amount_usd)+" USD)")
                                gain_eth += amount_eth
                                gain_usd += amount_usd
                        print("Gain: "+str(gain_eth)+" ETH ("+str(gain_usd)+" USD)")
                        # Compute profit
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

                        for i in range(len(swaps[tx_index])):
                            swaps[tx_index][i]["in_amount"] = str(swaps[tx_index][i]["in_amount"])
                            swaps[tx_index][i]["out_amount"] = str(swaps[tx_index][i]["out_amount"])
                            swaps[tx_index][i]["out_token_name"] = ''.join(swaps[tx_index][i]["out_token_name"].split('\x00'))
                            swaps[tx_index][i]["in_token_name"] = ''.join(swaps[tx_index][i]["in_token_name"].split('\x00'))

                        if flash_loan:
                            flash_loan["amount"] = str(flash_loan["amount"])
                            flash_loan["fee"] = str(flash_loan["fee"])
                            flash_loan["token_to_eth_price"] = float(flash_loan["token_to_eth_price"]) if flash_loan["token_to_eth_price"] != None else flash_loan["token_to_eth_price"]
                            flash_loan["fee_eth"] = float(flash_loan["fee_eth"]) if flash_loan["fee_eth"] != None else flash_loan["fee_eth"]

                        copy_gains = copy.deepcopy(gains)
                        for gain in copy_gains:
                            if '\x00' in gain:
                                key = ''.join(gain.split('\x00'))
                                gains[key] = gains[gain]
                                del gains[gain]

                        finding = {
                            "block_number": block_number,
                            "block_timestamp": block["timestamp"],
                            "miner": block["miner"],
                            "transaction": tx,
                            "swaps": swaps[tx_index],
                            "eth_usd_price": float(one_eth_to_usd_price),
                            "cost_eth": float(cost_eth),
                            "cost_usd": float(cost_usd),
                            "gain_eth": float(gain_eth),
                            "gain_usd": float(gain_usd),
                            "profit_eth": float(profit_eth),
                            "profit_usd": float(profit_usd),
                            "tokens_acquired": gains,
                            "flashbots_bundle": flashbots_bundle,
                            "flashbots_coinbase_transfer": float(flashbots_coinbase_transfer_eth),
                            "frontrunning_arbitrage": frontrunning_arbitrage,
                            "flash_loan": flash_loan
                        }

                        collection = mongo_connection["flashbots"]["arbitrage_results"]
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
                            collection.create_index('frontrunning_arbitrage')
                            collection.create_index('flash_loan.platform')
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        print("Error: "+str(e)+" @ block number: "+str(block_number))
        end = time.time()
        return end - start

    end = time.time()
    collection = mongo_connection["flashbots"]["arbitrage_status"]
    collection.insert_one({"block_number": block_number, "execution_time": end-start})
    # Indexing...
    if 'block_number' not in collection.index_information():
        collection.create_index('block_number')

    return end - start

def init_process(_prices):
    global w3
    global prices
    global mongo_connection

    w3 = Web3(PROVIDER)
    if w3.isConnected():
        print("Connected worker to "+w3.clientVersion)
    else:
        print(colors.FAIL+"Error: Could not connect to Ethereum client. Please check the provider!"+colors.END)
    prices = _prices
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
    if sys.platform.startswith("linux"):
        multiprocessing.set_start_method('fork')
    print("Running detection of arbitrage with "+str(multiprocessing.cpu_count())+" CPUs")
    print("Initializing workers...")
    with multiprocessing.Pool(processes=multiprocessing.cpu_count(), initializer=init_process, initargs=(prices,)) as pool:
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
