const WebSocket = require('ws');

console.log('Connecting to WebSocket server...');
const ws = new WebSocket('ws://localhost:8002/ws');

ws.on('open', function open() {
  console.log('Connected to WebSocket server');
  console.log('Waiting for initial data and updates...');
});

ws.on('message', function message(data) {
  const parsedData = JSON.parse(data.toString());
  console.log('Received data type:', parsedData.type);
  if (parsedData.type === 'initial_data') {
    console.log('Initial data received:', {
      stats: parsedData.stats,
      live_orders_count: parsedData.live_orders.length,
      pending_transactions_count: parsedData.pending_transactions.length
    });
  } else if (parsedData.type === 'update') {
    console.log('Update received:', {
      stats: parsedData.stats,
      timestamp: parsedData.timestamp
    });
  }
});

ws.on('close', function close() {
  console.log('Disconnected from WebSocket server');
});

ws.on('error', function error(err) {
  console.error('WebSocket error:', err);
});