#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess

MONGO_HOST = "localhost"
MONGO_PORT = 27017

def main():
    # Download latest "all_blocks" file if it does not exist
    if not os.path.exists("all_blocks"):
        subprocess.run(["wget", "https://blocks.flashbots.net/v1/all_blocks"])
    # Import into mongodb
    subprocess.run(["mongoimport", '--uri="mongodb://'+MONGO_HOST+':'+str(MONGO_PORT)+'/flashbots" --collection flashbots_blocks --jsonArray --type json --file all_blocks'])
    # Clean up
    subprocess.run(["rm", "all_blocks"])

if __name__ == "__main__":
    main()
