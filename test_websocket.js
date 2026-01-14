const WebSocket = require('ws');

console.log('Connecting to WebSocket server...');
const ws = new WebSocket('ws://localhost:8002/ws');

ws.on('open', function open() {
  console.log('Connected to WebSocket server');
});

ws.on('message', function message(data) {
  console.log('Received data from server:', data.toString());
});

ws.on('close', function close() {
  console.log('Disconnected from WebSocket server');
});

ws.on('error', function error(err) {
  console.error('WebSocket error:', err);
});