| Field | Description |
| ----- | ----------- |
| block_number | Number of the block where the frontrunning was detected. |
| block_timestamp | Timestamo of the block where the frontrunning was detected. |
| first_transaction | A transaction object of the first transaction of the attacker containing the fields: from, gas, gasPrice, hash, input, nonce, to, transactionIndex, type. |
| whale_transaction | A transaction object of the victim transaction containing the fields: from, gas, gasPrice, hash, input, nonce, to, transactionIndex, type. |
| second_transaction | A transaction object of the second transaction of the attacker containing the fields: from, gas, gasPrice, hash, input, nonce, to, transactionIndex, type. |
| eth_usd_price | The price of one ether to USD that was used to compute cost, gain, and profit in USD. |
| cost_eth | The cost that the attacker had in ether. This includes the transaction fees that the attacker had to pay for the two transactions and in case the attacker used Flashbots, the cost also contain the ether that the attacker to payed the miner through the coinbase. |
| cost_usd | The cost of the attacker in USD. This value is computed by multiplying cost_eth with eth_usd_price. |
| gain_eth | The amount of ether that the attacker gained by buying and selling the asset. |
| gain_usd | The gain of the attacker in USD. This value is computed by multiplying gain_eth with eth_usd_price. |
| profit_eth | The effective profit of the attack in ether. This value is computed by subtracting cost_eth from gain_eth. |
| profit_usd | The effective profit of the attack in USD. This value is computed by multiplying profit_eth with eth_usd_price. |
| exchange_address | The address of the smart contract of the decentralized exchange where the frontrunning attack occured. | 
| exchange_name | The name of the decentralized exchange where the frontrunning attack occured. | 
| token_address | The address of the smart contract of the token that was purchased by the victim. |
| token_name | The name of the token that was purchased by the victim. |
| first_transaction_eth_amount | The amount of ether that the attacker used to purchase its tokens. |
| whale_transaction_eth_amount | The amount of ether the victim used to purchase its tokens. |
| second_transaction_eth_amount | The amount of ether the attacker got from selling its tokens. |
| first_transaction_token_amount | The amount of tokens purchased by the attacker. |
| whale_transaction_token_amount | The amount of tokens puchased by the victim. |
| second_transaction_token_amount | The amount of tokens sold by the attacker. |
| interface | Interface used by the attacker. The interface can be either "bot" or "exchange", where bot means the attacker used a smart contract to coordinate the two transactions, and exchange means the attacker directly called the exchange for the two transactions. |
| bot_address | Address of the smart contract bot that the attacker used. |
| same_sender | Boolean value that is true if the two attacker transactions share the same sender address, otherwise the value is false. |
| same_receiver | Boolean value that is true if the two attacker transactions share the same receiver address, otherwise the value is false. |
| same_token_amount | Boolean value that is true if the two attacker transactions share the same token amount, otherwise the value is false. |
| flashbots_bundle | Boolean value that is true if the attacker used a flashbots bundle to perform the frontrunning attack. |
| flashbots_miner | Address of the miner that mined the flashbots bundle that includes the transactions from the attacker. |
| flashbots_coinbase_transfer | Total amount of ether that the attacker sent to the miner via a coinbase transfer. This value is already added to cost_eth if a coinbase transfer was used. The transactions can be computed by subtracting this value from cost_eth.|  
