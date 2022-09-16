#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import json
import requests

from web3 import Web3
from .settings import UPDATE_PRICES

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
    path = os.path.dirname(__file__)
    if os.path.exists(path+"/prices.json"):
        with open(path+"/prices.json", "r") as f:
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
