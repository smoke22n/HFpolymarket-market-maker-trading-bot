# Polymarket Trading Bot Dashboard

This is the dashboard for the high-frequency polymarket market-maker trading bot. It provides a visual command center for monitoring and controlling the trading operations.

## Features

- **Connection Status**: Shows WebSocket connection health
- **Wallet Balance**: Displays current USDC balance
- **Emergency Stop**: Allows stopping trading operations immediately
- **Real-time PnL**: Shows current profit and loss
- **Inventory Skew**: Displays current position distribution
- **24h Volume**: Shows trading volume for the last 24 hours
- **Live Operations**: Displays active orders and market opportunities
- **Historical Reports**: Shows historical PnL and performance metrics

## Prerequisites

- Node.js (v18 or higher)
- npm or yarn

## Setup

1. Install dependencies:
```bash
npm install
```

2. Create a `.env.local` file in the root of the dashboard directory with the following content:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

3. Run the development server:
```bash
npm run dev
```

4. Open [http://localhost:3000](http://localhost:3000) in your browser to view the dashboard.

## Environment Variables

- `NEXT_PUBLIC_API_URL`: The URL of the backend API server (default: http://localhost:8000)

## API Integration

The dashboard connects to the backend API to fetch real-time data:

- `/api/wallet/balance` - Wallet balance
- `/api/pnl` - Profit and loss data
- `/api/inventory` - Inventory positions
- `/api/volume` - Trading volume
- `/api/orders/live` - Active orders
- `/api/history` - Historical data
- `/api/control/emergency-stop` - Emergency stop control

## WebSocket Connection

The dashboard connects to the backend via WebSocket to monitor connection status. The default WebSocket URL is `ws://localhost:8000/ws`.

## Components

- `Header.tsx` - Top header with connection status, wallet balance, and emergency stop button
- `KPICards.tsx` - Key performance indicators cards
- `TabbedInterface.tsx` - Tabbed interface for live operations and historical reports
- `useWebSocket.ts` - Custom hook for WebSocket connection management
- `api.ts` - Service layer for API calls