#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import csv
import cfscrape

def get_flashbots_blocks(session_cookie=None):
    flashbots_blocks = list()

    if os.path.exists('flashbots_blocks.csv'):
        with open('flashbots_blocks.csv') as flashbots_blocks_file:
            reader = csv.reader(flashbots_blocks_file, delimiter=',')
            header_skiped = False
            for row in reader:
                if not header_skiped:
                    header_skiped = True
                else:
                    flashbots_blocks.append(row)
    print(len(flashbots_blocks))

    scraper = cfscrape.create_scraper()
    offset = 0#len(flashbots_blocks)
    while True:
        found_new_entries = False
        content = scraper.get('https://etherscan.io/blocks/label/flashbots?&size=100&start='+str(offset)).content.decode('utf-8')
        rows = re.compile("<tr class='.+?'>.+?</tr>").findall(content)
        if len(rows) == 0:
            break
        for row in rows:
            result = re.compile("<td><a href='/block/.+?'>(.+?)</a></td><td><div class='showDate ' style='display:none !important; '><span rel='tooltip' data-toggle='tooltip' data-placement='bottom' title='.+?'>(.+?)</span>.+?<td><a href='/address/(.+?)' class='hash-tag text-truncate'.*?>(.+?)</a></td>").findall(row)
            if not list(result[0]) in flashbots_blocks:
                print(list(result[0]))
                flashbots_blocks.append(list(result[0]))
                found_new_entries = True
        if not found_new_entries:
            break
        offset += 100
        print(offset)

    with open('flashbots_blocks.csv', mode='w') as flashbots_blocks_file:
        writer = csv.writer(flashbots_blocks_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(['Block', 'Timestamp', 'Miner Address', 'Miner Name'])
        flashbots_blocks.sort(key=lambda tup: int(tup[0]), reverse=True)
        for flashbots_block in flashbots_blocks:
            writer.writerow(flashbots_block)

def main():
    get_flashbots_blocks()

if __name__ == '__main__':
    main()
