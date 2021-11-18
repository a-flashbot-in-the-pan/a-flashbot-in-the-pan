# Frontrunning-Mitigation

## Installation Instructions

``` shell
python3 -m pip install -r requirements.txt
```

A `shell.nix` file has also been provided for those using `nix`.

## `mev` tool
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

More information on how to run an archive node can be found
[here](https://docs.ethhub.io/using-ethereum/running-an-ethereum-node/#archive-nodes). 

### Calculating tips
The following command calculates the tips accrued in the flashbots block in
`resources/flashbots-blocks-test.json`. This script writes the output to a csv
file in `output/tips-<first_block_num>-<last_block_num>.csv`. To view logging
output, include `--log-level [DEBUG,INFO,WARN,ERROR,CRITICAL]` after
`mev` but before `tips`. 

``` shell
./mev tips resources/flashbots-blocks-test.json
```

### Detecting insertion
The insertion detection script can be run like the following. Note that all
output is written to the logs, so to view output, the log level must be at least
`INFO`. 

``` shell
./mev --log-level INFO detection <BLOCK_NUM1> <BLOCK_NUM2>
```


#### Testing Insertion
TODO need to update the following to reflect the new syntax (code changes
probably required). This section will probably get merged with the above.
``` shell
# Examples
python3 main.py -b 10882755 # Uniswap V2
python3 main.py -b 9317713  # Uniswap V1
python3 main.py -b 10892526 # SushiSwap
python3 main.py -b 7100448  # Bancor
```

## TODO's

- [ ] Improve the execution time of executing transactions
- [ ] Add support for displacement
- [ ] Add support for suppression
