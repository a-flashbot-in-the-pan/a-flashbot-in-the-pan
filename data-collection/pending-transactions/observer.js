require('log-timestamp');
const Web3 = require('web3')
const Chalk = require('chalk');
const PerformanceNow = require('performance-now');
const { MongoClient } = require('mongodb');

let web3 = new Web3(Web3.givenProvider || 'ws://localhost:8546');
const uri = 'mongodb://localhost:27017';
const client = new MongoClient(uri);

web3.eth.extend({
  property: 'txpool',
  methods: [{
    name: 'content',
    call: 'txpool_content'
  },{
    name: 'inspect',
    call: 'txpool_inspect'
  },{
    name: 'status',
    call: 'txpool_status'
  }]
});

console.log('Web3 Version:', Chalk.green(web3.version));
web3.eth.getNodeInfo().then(console.log);
web3.eth.net.getPeerCount().then(function(peerCount) {
  console.log('Peer Count:', Chalk.green(peerCount));
});

async function run() {
  // Connect the client to the server
  await client.connect();
  // Establish and verify connection
  await client.db('flashbots').command({ ping: 1 });
  console.log('Connected successfully to MongoDB server.');
  const collection = client.db('flashbots').collection('observed_transactions');
  // Listen to upcoming pending transactions
  const subscription = web3.eth.subscribe('pendingTransactions', function(error, result){}).on('data', function(hash) {
    var timestamp = (Date.now() + PerformanceNow()) * 1000
    // Get transaction details
    web3.eth.getTransaction(hash).then((tx) => {
      if (tx) {
        tx['timestamp'] = timestamp;
        // Store transaction inside 'observed_transactions'
        collection.insertOne(tx).then((mongodb_result) => {
          console.log('Inserted transaction', Chalk.green(hash), '(ID: '+mongodb_result.insertedId+')');
        }).catch((error) => {
            console.log('MongoDB Error', error);
            client.close();
        });
      }
    }).catch((error) => {
        console.log('Error', error);
        client.close();
    })
  });
}

run().catch(console.dir);
