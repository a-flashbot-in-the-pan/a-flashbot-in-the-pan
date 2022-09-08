
import re
import csv
import cfscrape

def main():
    scraper = cfscrape.create_scraper(delay=10)
    miner_labels = dict()
    with open('flashbots_miners.csv', newline='') as csvfile:
        reader = csv.reader(csvfile, delimiter=',', quotechar='"')
        next(reader, None)
        for row in reader:
            miner = row[0]
            print(miner)
            content = scraper.get("https://etherscan.io/address/"+miner).content.decode("utf-8")
            result = re.compile("<span .*? data-toggle='tooltip' title='Public Name Tag \(viewable by anyone\)'>(.+?)</span>").findall(content)
            print(result)
            if len(result) == 1:
                miner_labels[miner] = result[0]
            else:
                miner_labels[miner] = ''
    with open('miner_labels.csv', 'w') as csvfile:
        writer = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(['miner', 'label'])
        for miner in miner_labels:
            writer.writerow([miner, miner_labels[miner]])

if __name__ == "__main__":
    main()
