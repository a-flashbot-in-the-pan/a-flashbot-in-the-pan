#!/bin/bash

# Download and import flashbots data
gdown https://drive.google.com/uc?id=1Cge4XiuvZJK5i31JzmqrlPYFTvrQxzVj
unzip flashbots_blocks.zip
rm flashbots_blocks.zip
mongoimport --uri="mongodb://localhost:27017/flashbots" --collection flashbots_blocks --type json --file flashbots_blocks.json
rm flashbots_blocks.json

# Download and import sandwich data
gdown https://drive.google.com/uc?id=1K5kB5PlZ55EzGwNHlSRNVuQhWSp2CWPY
unzip sandwich_results.zip
rm sandwich_results.zip
mongoimport --uri="mongodb://localhost:27017/flashbots" --collection sandwich_results --type json --file sandwich_results.json
rm sandwich_results.json

# Download and import arbitrage data
gdown https://drive.google.com/uc?id=1oMgUONsdHZ8XsfrxmVaNF2Hl7fs-hE6R
unzip arbitrage_results.zip
rm arbitrage_results.zip
mongoimport --uri="mongodb://localhost:27017/flashbots" --collection arbitrage_results --type json --file arbitrage_results.json
rm arbitrage_results.json

# Download and import liquidation data
gdown https://drive.google.com/uc?id=10sSee0lSmXx4bYsosCnJo8jMldQKJv8s
unzip liquidation_results.zip
rm liquidation_results.zip
mongoimport --uri="mongodb://localhost:27017/flashbots" --collection liquidation_results --type json --file liquidation_results.json
rm liquidation_results.json
