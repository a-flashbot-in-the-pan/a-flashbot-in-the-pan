#!/bin/bash

echo "!!! The following downloads might fail and you might get an error message stating access denied. In that case try to download and import the data manually by downloading it from: https://drive.google.com/drive/folders/1nW3Ar2u9jtDX-pxAayO4auZHGXEUkq-W?usp=sharing !!!"

# Download and import flashbots data
echo "Downloading Flashbots data..."
gdown https://drive.google.com/uc?id=1Cge4XiuvZJK5i31JzmqrlPYFTvrQxzVj
unzip flashbots_blocks.zip
rm flashbots_blocks.zip
echo "Importing Flashbots data..."
mongoimport --uri="mongodb://localhost:27017/flashbots" --collection flashbots_blocks --type json --file flashbots_blocks.json
rm flashbots_blocks.json

# Download and import sandwich data
echo "Downloading sandwich data..."
gdown https://drive.google.com/uc?id=1K5kB5PlZ55EzGwNHlSRNVuQhWSp2CWPY
unzip sandwich_results.zip
rm sandwich_results.zip
echo "Importing sandwich data..."
mongoimport --uri="mongodb://localhost:27017/flashbots" --collection sandwich_results --type json --file sandwich_results.json
rm sandwich_results.json

# Download and import arbitrage data
echo "Downloading arbitrage data..."
gdown https://drive.google.com/uc?id=1oMgUONsdHZ8XsfrxmVaNF2Hl7fs-hE6R
unzip arbitrage_results.zip
rm arbitrage_results.zip
echo "Importing arbitrage data..."
mongoimport --uri="mongodb://localhost:27017/flashbots" --collection arbitrage_results --type json --file arbitrage_results.json
rm arbitrage_results.json

# Download and import liquidation data
echo "Downloading liquidation data..."
gdown https://drive.google.com/uc?id=10sSee0lSmXx4bYsosCnJo8jMldQKJv8s
unzip liquidation_results.zip
rm liquidation_results.zip
echo "Importing liquidation data..."
mongoimport --uri="mongodb://localhost:27017/flashbots" --collection liquidation_results --type json --file liquidation_results.json
rm liquidation_results.json

# Download and import pending transactions data
echo "Downloading pending transactions data..."
gdown https://drive.google.com/uc?id=1tCCKFu6lJyCTiZ2gLuLNuph-4b2Cv9Rr
unzip observed_transactions.zip
rm observed_transactions.zip
echo "Importing pending transactions data..."
mongoimport --uri="mongodb://localhost:27017/flashbots" --collection observed_transactions --type json --file observed_transactions.json
rm observed_transactions.json
