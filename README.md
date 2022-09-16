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
cd /root/scripts/analysis
jupyter notebook --port=8888 --no-browser --ip=0.0.0.0 --allow-root --NotebookApp.token='' --NotebookApp.password=''
```

## Custom Docker image build

``` shell
docker build -t a-flashbot-in-the-pan .
docker run -m 16g --memory-swap="24g" -p 8888:8888 -it a-flashbot-in-the-pan:latest
```


## Installation Instructions

``` shell
python3 -m pip install -r requirements.txt
```

## Run Instructions

#### Measuring MEV arbitrage

``` shell
python3 arbitrage.py 11706655:11706655
```

#### Measuring MEV liquidations

``` shell
python3 liquidation.py 11181773:11181773
```

## Notebooks
The bulk of the analysis was done in Jupyter notebooks, which can be opened by
running

``` shell
jupyter notebook
```
and selecting the notebook of choice.

## Raw data
Interested researchers can download our data from [here](https://drive.google.com/drive/folders/16fAYXjlt0DqvrUDyYEM8hi24tDcR750i?usp=sharing).

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
