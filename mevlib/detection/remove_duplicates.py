
import pymongo

MONGO_HOST = "pf.uni.lux"
MONGO_PORT = 27017

mongo_connection = pymongo.MongoClient("mongodb://"+MONGO_HOST+":"+str(MONGO_PORT), maxPoolSize=None)

documents_to_be_deleted = list(mongo_connection["flashbots"]["insertion_results"].aggregate([
        {"$group": {"_id": "$first_transaction.hash", "unique_ids": {"$addToSet": "$_id"}, "count": {"$sum": 1}}},
        {"$match": {"count": { "$gte": 2 }}}
    ], allowDiskUse=True))

print(len(documents_to_be_deleted))

for document in documents_to_be_deleted:
    print(document)
    for i in range(document["count"] - 1):
        print("removing", document["unique_ids"][i+1])
        mongo_connection["flashbots"]["insertion_results"].delete_one({"_id": document["unique_ids"][i+1]})
