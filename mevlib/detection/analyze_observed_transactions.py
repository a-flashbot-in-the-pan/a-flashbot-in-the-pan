
import json
import pymongo

from datetime import datetime

MONGO_HOST = "pf.uni.lux"
MONGO_PORT = 27017

mongo_connection = pymongo.MongoClient("mongodb://"+MONGO_HOST+":"+str(MONGO_PORT), maxPoolSize=None)

observed_transactions = mongo_connection["flashbots"]["observed_transactions"]
print("Number of observerd public transactions:", observed_transactions.count_documents({}))

observed_transactions_per_day = dict()
observed_transactions_per_hour = dict()

cursor = observed_transactions.find({})
for document in cursor:
    day = datetime.utcfromtimestamp(document["timestamp"] / 1000000).strftime('%Y/%m/%d')
    if not day in observed_transactions_per_day:
        observed_transactions_per_day[day] = 0
    observed_transactions_per_day[day] += 1

    hour = datetime.utcfromtimestamp(document["timestamp"] / 1000000).strftime('%Y/%m/%d %H')
    if not hour in observed_transactions_per_hour:
        observed_transactions_per_hour[hour] = 0
    observed_transactions_per_hour[hour] += 1

with open("observed_transactions_per_day.json", "w") as jsonfile:
    json.dump(observed_transactions_per_day, jsonfile)

with open("observed_transactions_per_hour.json", "w") as jsonfile:
    json.dump(observed_transactions_per_hour, jsonfile)
