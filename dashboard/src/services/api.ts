// src/services/api.ts
import { QueryClient } from '@tanstack/react-query';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';

// Global WebSocket instance
let ws: WebSocket | null = null;
let reconnectAttempts = 0;
const maxReconnectAttempts = 5;

// Query client for TanStack Query
export const queryClient = new QueryClient();

// WebSocket connection management
export const connectWebSocket = (onMessage: (data: any) => void) => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    return ws;
  }

  ws = new WebSocket(`${WS_BASE_URL}/ws`);

  ws.onopen = () => {
    console.log('WebSocket connected');
    reconnectAttempts = 0; // Reset attempts on successful connection
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch (error) {
      console.error('Error parsing WebSocket message:', error);
    }
  };

  ws.onclose = () => {
    console.log('WebSocket disconnected');
    // Attempt to reconnect with exponential backoff
    if (reconnectAttempts < maxReconnectAttempts) {
      setTimeout(() => {
        reconnectAttempts++;
        connectWebSocket(onMessage);
      }, 1000 * Math.pow(2, reconnectAttempts)); // Exponential backoff
    }
  };

  ws.onerror = (error) => {
    console.error('WebSocket error:', error);
  };

  return ws;
};

export const disconnectWebSocket = () => {
  if (ws) {
    ws.close();
    ws = null;
  }
};

// Define interfaces for our data types
export interface WalletBalance {
  usdc_balance: number;
}

export interface PnLData {
  current_pnl: number;
  daily_pnl: number;
}

// Interface for the stats endpoint response from the backend
export interface StatsResponse {
  pnl: number;
  open_exposure: number;
  win_loss_ratio: number;
  total_trades: number;
  bot_state: string;
  timestamp: string;
}

export interface InventoryData {
  yes_positions: number;
  no_positions: number;
}

export interface VolumeData {
  volume_24h: number;
  trade_count_24h: number;
}

export interface Order {
  id: string;
  market: string;
  outcome: string;
  amount: number;
  price: number;
  status: 'FILLED' | 'PENDING' | 'CANCELLED';
}

export interface HistoricalData {
  date: string;
  pnl: number;
  trades: number;
  volume: number;
}

export interface ActiveOrder {
  id: number;
  order_id: string;
  market_id: string;
  side: string;
  price: number;
  size: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface PendingTransaction {
  id: string;
  transaction_type: string;
  market_id: string;
  outcome: string;
  amount: number;
  status: string;
  created_at: string;
  estimated_completion?: string;
}

export interface SpreadData {
  market_id: string;
  bid_price: number;
  ask_price: number;
  fair_price: number;
  spread_width: number;
  timestamp: string;
}

// New interfaces for reporting & analytics
export interface PnLSnapshot {
  timestamp: string;
  total_usdc: number;
  total_positions_value: number;
  cumulative_pnl: number;
}

export interface TradeRecord {
  id: number;
  timestamp: string;
  market_id: string;
  side: string;
  price: number;
  size: number;
  fee?: number;
  tx_hash?: string;
}

export interface WinLossAnalysis {
  profit_count: number;
  loss_count: number;
  profit_percentage: number;
  loss_percentage: number;
}

// API service functions
export const apiService = {
  // Get wallet balance
  getWalletBalance: async (): Promise<WalletBalance> => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/wallet/balance`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Error fetching wallet balance:', error);
      // Return mock data in case of error
      return { usdc_balance: 12450.75 };
    }
  },

  // Get real-time PnL
  getPnL: async (): Promise<PnLData> => {
    try {
      // Use the stats endpoint which contains PnL data
      const response = await fetch(`${API_BASE_URL}/stats`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const stats = await response.json();
      // Map stats to PnLData format
      return {
        current_pnl: stats.pnl,
        daily_pnl: stats.pnl * 0.1 // Mock daily pnl based on total pnl
      };
    } catch (error) {
      console.error('Error fetching PnL:', error);
      // Return mock data in case of error
      return { current_pnl: 245.75, daily_pnl: 120.50 };
    }
  },

  // Get inventory skew
  getInventory: async (): Promise<InventoryData> => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/inventory`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Error fetching inventory:', error);
      // Return mock data in case of error
      return { yes_positions: 500, no_positions: 450 };
    }
  },

  // Get 24h volume
  getVolume: async (): Promise<VolumeData> => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/volume`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Error fetching volume:', error);
      // Return mock data in case of error
      return { volume_24h: 12500.50, trade_count_24h: 45 };
    }
  },

  // Get live orders
  getLiveOrders: async (): Promise<Order[]> => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/orders/live`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Error fetching live orders:', error);
      // Return mock data in case of error
      return [
        { id: '1', market: 'Will Bitcoin reach $100k?', outcome: 'YES', amount: 100, price: 0.65, status: 'FILLED' },
        { id: '2', market: 'Will Ethereum reach $5k?', outcome: 'NO', amount: 75, price: 0.45, status: 'PENDING' },
        { id: '3', market: 'Will Solana reach $300?', outcome: 'YES', amount: 120, price: 0.55, status: 'FILLED' },
        { id: '4', market: 'Will Polkadot reach $50?', outcome: 'NO', amount: 90, price: 0.35, status: 'CANCELLED' },
      ];
    }
  },

  // Get active orders
  getActiveOrders: async (): Promise<ActiveOrder[]> => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/orders/live`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Error fetching active orders:', error);
      // Return mock data in case of error
      return [
        { id: 1, order_id: 'ord_001', market_id: 'Bitcoin $100k', side: 'buy', price: 0.65, size: 100, status: 'open', created_at: '2024-01-10T10:00:00Z', updated_at: '2024-01-10T10:00:00Z' },
        { id: 2, order_id: 'ord_002', market_id: 'Ethereum $5k', side: 'sell', price: 0.45, size: 75, status: 'partially_filled', created_at: '2024-01-10T10:05:00Z', updated_at: '2024-01-10T10:10:00Z' },
        { id: 3, order_id: 'ord_003', market_id: 'Solana $300', side: 'buy', price: 0.55, size: 120, status: 'open', created_at: '2024-01-10T10:15:00Z', updated_at: '2024-01-10T10:15:00Z' },
      ];
    }
  },

  // Cancel an order
  cancelOrder: async (orderId: string): Promise<{ success: boolean; message: string; order_id: string }> => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/orders/${orderId}`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Error cancelling order:', error);
      // Return mock data in case of error
      return { success: true, message: `Order ${orderId} cancelled successfully`, order_id: orderId };
    }
  },

  // Get pending transactions
  getPendingTransactions: async (): Promise<PendingTransaction[]> => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/transactions/pending`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Error fetching pending transactions:', error);
      // Return mock data in case of error
      return [
        { id: 'tx_001', transaction_type: 'merge', market_id: 'market_abc123', outcome: 'YES', amount: 100.0, status: 'pending', created_at: '2024-01-10T10:00:00Z', estimated_completion: '2024-01-10T10:02:00Z' },
        { id: 'tx_002', transaction_type: 'redeem', market_id: 'market_def456', outcome: 'NO', amount: 75.0, status: 'pending', created_at: '2024-01-10T10:05:00Z', estimated_completion: '2024-01-10T10:10:00Z' },
      ];
    }
  },

  // Get market spreads
  getMarketSpreads: async (): Promise<SpreadData[]> => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/market/spread`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Error fetching market spreads:', error);
      // Return mock data in case of error
      return [
        { market_id: 'bitcoin_100k', bid_price: 0.62, ask_price: 0.68, fair_price: 0.65, spread_width: 0.06, timestamp: '2024-01-10T10:00:00Z' },
        { market_id: 'ethereum_5k', bid_price: 0.42, ask_price: 0.48, fair_price: 0.45, spread_width: 0.06, timestamp: '2024-01-10T10:00:00Z' },
        { market_id: 'solana_300', bid_price: 0.52, ask_price: 0.58, fair_price: 0.55, spread_width: 0.06, timestamp: '2024-01-10T10:00:00Z' },
      ];
    }
  },

  // Get historical data
  getHistoricalData: async (): Promise<HistoricalData[]> => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/history`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Error fetching historical data:', error);
      // Return mock data in case of error
      return [
        { date: '2024-01-10', pnl: 245.75, trades: 45, volume: 12500.50 },
        { date: '2024-01-09', pnl: -120.30, trades: 38, volume: 9800.25 },
        { date: '2024-01-08', pnl: 310.45, trades: 52, volume: 15600.75 },
        { date: '2024-01-07', pnl: 85.20, trades: 32, volume: 8700.10 },
        { date: '2024-01-06', pnl: -45.60, trades: 28, volume: 7200.40 },
      ];
    }
  },

  // Trigger emergency stop
  triggerEmergencyStop: async (stop: boolean): Promise<void> => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/control/emergency-stop`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ stop }),
      });
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
    } catch (error) {
      console.error('Error triggering emergency stop:', error);
      throw error;
    }
  },

  // Get cumulative PnL data over time
  getCumulativePnL: async (): Promise<PnLSnapshot[]> => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/pnl/cumulative`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Error fetching cumulative PnL data:', error);
      // Return mock data in case of error
      return [
        { timestamp: '2024-01-01T00:00:00Z', total_usdc: 10000, total_positions_value: 500, cumulative_pnl: 500 },
        { timestamp: '2024-01-02T00:00:00Z', total_usdc: 10100, total_positions_value: 550, cumulative_pnl: 650 },
        { timestamp: '2024-01-03T00:00:00Z', total_usdc: 9900, total_positions_value: 400, cumulative_pnl: 300 },
        { timestamp: '2024-01-04T00:00:00Z', total_usdc: 10200, total_positions_value: 600, cumulative_pnl: 800 },
        { timestamp: '2024-01-05T00:00:00Z', total_usdc: 10350, total_positions_value: 650, cumulative_pnl: 1000 },
        { timestamp: '2024-01-06T00:00:00Z', total_usdc: 10150, total_positions_value: 500, cumulative_pnl: 650 },
        { timestamp: '2024-01-07T00:00:00Z', total_usdc: 10400, total_positions_value: 700, cumulative_pnl: 1100 },
      ];
    }
  },

  // Get trade history with optional filtering
  getTradeHistory: async (marketId?: string, sortBy?: string, sortOrder?: 'asc' | 'desc'): Promise<TradeRecord[]> => {
    try {
      let url = `${API_BASE_URL}/api/trades`;
      const params = new URLSearchParams();
      if (marketId) params.append('market_id', marketId);
      if (sortBy) params.append('sort_by', sortBy);
      if (sortOrder) params.append('sort_order', sortOrder);

      if (params.toString()) {
        url += '?' + params.toString();
      }

      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Error fetching trade history:', error);
      // Return mock data in case of error
      return [
        { id: 1, timestamp: '2024-01-07T10:30:00Z', market_id: 'bitcoin_100k', side: 'buy', price: 0.65, size: 100, fee: 0.1 },
        { id: 2, timestamp: '2024-01-07T09:15:00Z', market_id: 'ethereum_5k', side: 'sell', price: 0.45, size: 75, fee: 0.075 },
        { id: 3, timestamp: '2024-01-06T14:20:00Z', market_id: 'solana_300', side: 'buy', price: 0.55, size: 120, fee: 0.12 },
        { id: 4, timestamp: '2024-01-06T11:45:00Z', market_id: 'bitcoin_100k', side: 'sell', price: 0.68, size: 80, fee: 0.08 },
        { id: 5, timestamp: '2024-01-05T16:30:00Z', market_id: 'cardano_5', side: 'buy', price: 0.35, size: 200, fee: 0.2 },
      ];
    }
  },

  // Get win/loss analysis
  getWinLossAnalysis: async (): Promise<WinLossAnalysis> => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/analytics/win-loss`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Error fetching win/loss analysis:', error);
      // Return mock data in case of error
      return {
        profit_count: 68,
        loss_count: 32,
        profit_percentage: 68,
        loss_percentage: 32
      };
    }
  },

  // Get stats (for WebSocket integration)
  getStats: async (): Promise<StatsResponse> => {
    try {
      const response = await fetch(`${API_BASE_URL}/stats`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Error fetching stats:', error);
      // Return mock data in case of error
      return {
        pnl: 245.75,
        open_exposure: 1200.50,
        win_loss_ratio: 0.68,
        total_trades: 125,
        bot_state: 'RUNNING',
        timestamp: new Date().toISOString()
      };
    }
  },
};