# Frontrunning-Mitigation

## `mev_analyzer` tool
If using Infura, instead of an archive node, you must set the following
environment variables
``` shell
export WEB3_INFURA_PROJECT_ID="XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
export WEB3_INFURA_API_SECRET="XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
```

To use an archive node as a provider set the following variable instead of the
above ones
``` shell
export WEB3_PROVIDER_URI="wss://<HOST>:<PORT>"
```


## Installation Instructions

``` shell
python3 -m pip install -r requirements.txt
```

## Running Instructions

:warning: **!! A connection to a fully synced archive node is required. !!**

Please update ```utils/settings.py``` with the hostname and port number of your fully synced archive node accordingly.
More information on how to run an archive node can be found [here](https://docs.ethhub.io/using-ethereum/running-an-ethereum-node/#archive-nodes).

#### Testing Insertion

``` shell
# Examples
python3 main.py -b 10882755 # Uniswap V2
python3 main.py -b 9317713  # Uniswap V1
python3 main.py -b 10892526 # SushiSwap
python3 main.py -b 7100448  # Bancor
```

## TODO's

- [ ] Improve the execution time of executing transactions
- [ ] Add VDFs
- [ ] Add support for displacement
- [ ] Add support for suppression
