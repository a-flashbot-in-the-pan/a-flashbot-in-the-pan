<div align="center">
  <img src="logo.png" alt="drawing" width="300"/>
</div>

<h1 align="center">A Flash(bot) in the Pan</h1>

A collection of tools to measure and analyze frontrunning attacks on private pools such as [Flashbots](https://docs.flashbots.net). Our paper can be found [here](https://arxiv.org/ftp/arxiv/papers/2206/2206.04185.pdf).

## Quick Start

A container with all the dependencies can be found [here](https://hub.docker.com/r/christoftorres/a-flashbot-in-the-pan/).

To run the container, please install docker and run:

``` shell
docker pull christoftorres/a-flashbot-in-the-pan && docker run -m 16g --memory-swap="24g" -p 8888:8888 -it christoftorres/a-flashbot-in-the-pan
```

Afterwards, start an instance of MongoDB inside the container:

``` shell
# Start MongoDB
mkdir -p /data/db
mongod --fork --logpath /var/log/mongod.log
```

Import the flashbots blocks into MongoDB by running inside the container the following commands:  

``` shell
cd /root/data-collection/flashbots
python3 import_flashbots_data.py
```

To run the MEV measurement scripts, simply run inside the container the following commands:

``` shell
# Run the sandwich measurement script
cd /root/data-collection/mev/sandwiches
python3 sandwiches.py <BLOCK_RANGE_START>:<BLOCK_RANGE_END> # For exmaple: python3 sandwiches.py 10892526:10892526

# Run the arbitrage measurement script
cd /root/data-collection/mev/arbitrage
python3 arbitrage.py <BLOCK_RANGE_START>:<BLOCK_RANGE_END> # For exmaple: python3 arbitrage.py 11706655:11706655

# Run the liquidation measurement script
cd /root/data-collection/mev/liquidation
python3 liquidation.py <BLOCK_RANGE_START>:<BLOCK_RANGE_END> # For exmaple: python3 liquidation.py 11181773:11181773
```

To run the analysis, please launch the Jupyter notebook server inside the container using the following commands and then open up http://localhost:8888 on your browser:

``` shell
cd /root/analysis
jupyter notebook --port=8888 --no-browser --ip=0.0.0.0 --allow-root --NotebookApp.token='' --NotebookApp.password=''
```

## Custom Docker image build

``` shell
docker build -t a-flashbot-in-the-pan .
docker run -m 16g --memory-swap="24g" -p 8888:8888 -it a-flashbot-in-the-pan:latest
```


## Installation Instructions

### 1. Install MongoDB

##### MacOS

``` shell
brew tap mongodb/brew
brew install mongodb-community@4.4
```

For other operating systems follow the installation instructions on [mongodb.com](https://docs.mongodb.com/manual/installation/).

### 2. Install Python dependencies

``` shell
python3 -m pip install -r requirements.txt
```

## Data Collection

#### Launch MongoDB

``` shell
mongod
```

#### Download and import Flashbots data

``` shell
cd data-collection/flashbots
python3 import_flashbots_data.py
```

#### Measure MEV extraction

:warning: **!! To measure past MEV extraction you will need a connection to a fully synched Ethereum archive node and change ```PROVIDER``` in ```data-collection/mev/utils/settings.py``` accordingly. !!**


``` shell
cd data-collection/mev/sandwiches
python3 sandwiches.py  <BLOCK_RANGE_START>:<BLOCK_RANGE_END> 
cd data-collection/mev/arbitrage
python3 arbitrage.py   <BLOCK_RANGE_START>:<BLOCK_RANGE_END> 
cd data-collection/mev/liquidation
python3 liquidation.py <BLOCK_RANGE_START>:<BLOCK_RANGE_END> 
```

#### Collect pending transactions

:warning: **!! To collect pending transactions you will need a connection to an Ethereum node and set ```web3``` in ```data-collection/pending-transactions/observer.js``` accordingly. !!**

``` shell

```

## Analysis 

You can either run the data collection scripts or download our data from Google drive:

``` shell
# Download flashbot blocks
gdown 

# Download token prices
gdown 

# Download sandwich data
gdown 

# Download arbitrage data
gdown 

# Download liquidation data
gdown 

```

The bulk of the analysis was done in Jupyter notebooks, which can be opened by running:

``` shell
cd analysis
jupyter notebook
```
and selecting the notebook of choice.


## Attribution
If using this repository for research, please cite as

``` bibtex
@inproceedings{
  aflashbotinthepan, 
  address={Nice, France}, 
  title={A Flash(bot) in the Pan: Measuring Maximal Extractable Value in Private Pools}, 
  publisher={Association for Computing Machinery}, 
  author={Weintraub, Ben and Ferreira Torres, Christof and Nita-Rotaru, Cristina and State, Radu}, 
  year={2022} 
}
```
