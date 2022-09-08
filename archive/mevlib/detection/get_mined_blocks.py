
import sys
import csv
import json
import time
import multiprocessing

from web3 import Web3
from tqdm import tqdm

def analyze_block(block_info):
    month, block_range = block_info[0], block_info[1]
    print("Analyzing month", month, "with block range", block_range[0], "and", block_range[1])
    count = dict()
    for i in tqdm(range(block_range[0], block_range[1]+1)):
        block = w3.eth.get_block(i)
        if block.miner in miners:
            if not block.miner in count:
                count[block.miner] = 0
            count[block.miner] += 1
        break
    with open(month.replace("/", "_")+'_count.csv', 'w') as csvfile:
        writer = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(['miner', 'counter'])
        for miner in miners:
            if miner in count:
                writer.writerow([miner, count[miner]])
            else:
                writer.writerow([miner, 0])

def init_process():
    global w3
    global miners

    w3 = Web3(Web3.WebsocketProvider("ws://pf.uni.lux:8548"))
    if w3.isConnected():
        print("Connected worker to "+w3.clientVersion)
    else:
        print("Error: Could not connect to Ethereum client!")
    miners = list()
    with open('flashbots_miners.csv', newline='') as csvfile:
        reader = csv.reader(csvfile, delimiter=',', quotechar='"')
        next(reader, None)
        for row in reader:
            miners.append(row[0])
    print("Found", len(miners), "miners")

def main():
    if sys.platform.startswith("linux"):
        multiprocessing.set_start_method('fork')

    block_ranges = list()
    with open('monthly_block_ranges.csv', newline='') as csvfile:
        reader = csv.reader(csvfile, delimiter=',', quotechar='"')
        next(reader, None)
        for row in reader:
            block_ranges.append((row[1], (int(row[2]), int(row[3]))))
    print(block_ranges)

    with multiprocessing.Pool(processes=multiprocessing.cpu_count(), initializer=init_process) as pool:
        start_total = time.time()
        pool.map(analyze_block, block_ranges)
        end_total = time.time()
        print("Total execution time: "+str(end_total - start_total))

if __name__ == "__main__":
    main()
