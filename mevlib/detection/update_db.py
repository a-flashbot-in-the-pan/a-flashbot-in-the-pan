

from web3 import Web3

WEB3_HTTP_RPC = "http://pf.uni.lux:8547"

w3 = Web3(Web3.HTTPProvider(WEB3_HTTP_RPC))
if w3.isConnected():
    print("Connected to "+w3.clientVersion)
else:
    print("error could not connect")
import pymongo

MONGO_HOST = "pf.uni.lux"
MONGO_PORT = 27017

mongo_connection = pymongo.MongoClient("mongodb://"+MONGO_HOST+":"+str(MONGO_PORT), maxPoolSize=None)

blocks_to_be_updated = list(mongo_connection["flashbots"]["arbitrage_results"].find({"miner":{"$exists":False}},{"block_number":1}))
print(len(blocks_to_be_updated))

for document in blocks_to_be_updated:
    mongo_id = document["_id"]
    block_number = document["block_number"]
    block = w3.eth.getBlock(block_number)
    miner = block["miner"]
    mongo_connection["flashbots"]["arbitrage_results"].find_one_and_update({"_id": mongo_id}, {"$set": {"miner": miner}})
    print(block_number, "updated")
