'use client';

import React, { useState, useEffect } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { apiService, connectWebSocket, Order, HistoricalData, ActiveOrder, PendingTransaction, SpreadData, PnLSnapshot, TradeRecord, WinLossAnalysis } from '@/services/api';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell } from 'recharts';

const TabbedInterface = () => {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<string>('live');
  const [selectedMarket, setSelectedMarket] = useState<string>('');
  const [tradeSortBy, setTradeSortBy] = useState<string>('timestamp');
  const [tradeSortOrder, setTradeSortOrder] = useState<'asc' | 'desc'>('desc');

  // WebSocket state management
  useEffect(() => {
    const handleWebSocketMessage = (data: any) => {
      if (data.type === 'update') {
        // Update query cache with real-time data
        queryClient.setQueryData(['stats'], data.stats);
        queryClient.setQueryData(['active-orders'], data.live_orders);
        queryClient.setQueryData(['pending-transactions'], data.pending_transactions);
        queryClient.setQueryData(['market-spreads'], data.market_spreads);
        queryClient.setQueryData(['cumulative-pnl'], data.cumulative_pnl);
      } else if (data.type === 'initial_data') {
        // Update query cache with initial data
        queryClient.setQueryData(['stats'], data.stats);
        queryClient.setQueryData(['active-orders'], data.live_orders);
        queryClient.setQueryData(['pending-transactions'], data.pending_transactions);
        queryClient.setQueryData(['market-spreads'], data.market_spreads);
      }
    };

    const ws = connectWebSocket(handleWebSocketMessage);

    return () => {
      // Cleanup WebSocket connection
      ws.close();
    };
  }, [queryClient]);

  // Live data queries using TanStack Query
  const { data: activeOrders = [], isLoading: loadingActive } = useQuery<ActiveOrder[]>({
    queryKey: ['active-orders'],
    queryFn: apiService.getActiveOrders,
    refetchInterval: 5000, // Fallback to polling if WebSocket fails
    staleTime: 2000, // Data is considered fresh for 2 seconds
    enabled: activeTab === 'live',
  });

  const { data: pendingTransactions = [], isLoading: loadingTransactions } = useQuery<PendingTransaction[]>({
    queryKey: ['pending-transactions'],
    queryFn: apiService.getPendingTransactions,
    refetchInterval: 5000, // Fallback to polling if WebSocket fails
    staleTime: 2000, // Data is considered fresh for 2 seconds
    enabled: activeTab === 'live',
  });

  const { data: spreadData = [], isLoading: loadingSpread } = useQuery<SpreadData[]>({
    queryKey: ['market-spreads'],
    queryFn: apiService.getMarketSpreads,
    refetchInterval: 5000, // Fallback to polling if WebSocket fails
    staleTime: 2000, // Data is considered fresh for 2 seconds
    enabled: activeTab === 'live',
  });

  // Historical data queries using TanStack Query
  const { data: cumulativePnLData = [], isLoading: loadingCumulativePnL } = useQuery<PnLSnapshot[]>({
    queryKey: ['cumulative-pnl'],
    queryFn: apiService.getCumulativePnL,
    refetchInterval: 10000, // Poll every 10 seconds for historical data
    staleTime: 5000, // Data is considered fresh for 5 seconds
    enabled: activeTab === 'history',
  });

  const { data: tradeHistory = [], isLoading: loadingTradeHistory } = useQuery<TradeRecord[]>({
    queryKey: ['trade-history', selectedMarket, tradeSortBy, tradeSortOrder],
    queryFn: () => apiService.getTradeHistory(selectedMarket, tradeSortBy, tradeSortOrder),
    refetchInterval: 10000, // Poll every 10 seconds for trade history
    staleTime: 5000, // Data is considered fresh for 5 seconds
    enabled: activeTab === 'history',
  });

  const { data: winLossAnalysis, isLoading: loadingWinLoss } = useQuery<WinLossAnalysis>({
    queryKey: ['win-loss-analysis'],
    queryFn: apiService.getWinLossAnalysis,
    refetchInterval: 15000, // Poll every 15 seconds for win/loss analysis
    staleTime: 10000, // Data is considered fresh for 10 seconds
    enabled: activeTab === 'history',
  });

  // Handle order cancellation
  const handleCancelOrder = async (orderId: string) => {
    try {
      const result = await apiService.cancelOrder(orderId);
      if (result.success) {
        // Invalidate the active orders query to refresh data
        queryClient.invalidateQueries({ queryKey: ['active-orders'] });
        console.log(`Order ${orderId} cancelled successfully`);
      }
    } catch (error) {
      console.error('Error cancelling order:', error);
    }
  };

  // Handle trade history filter changes
  const handleMarketFilterChange = (value: string) => {
    setSelectedMarket(value);
  };

  const handleSortByChange = (value: string) => {
    setTradeSortBy(value);
  };

  const handleSortOrderChange = (value: string) => {
    setTradeSortOrder(value as 'asc' | 'desc');
  };

  // Get unique markets for the filter dropdown
  const getUniqueMarkets = () => {
    const markets = new Set(tradeHistory.map(trade => trade.market_id));
    return Array.from(markets).filter(market => market);
  };

  // Prepare data for the cumulative PnL chart
  const prepareCumulativePnLData = () => {
    // For benchmark, we'll create a simple ETH holding simulation
    // Starting with the first PnL value and assuming a simple growth model
    let benchmarkValue = cumulativePnLData.length > 0 ? cumulativePnLData[0].cumulative_pnl : 0;

    return cumulativePnLData.map((pnl, index) => {
      // Simple benchmark calculation: assume 0.1% daily growth for demo purposes
      const benchmarkGrowth = Math.pow(1.001, index); // 0.1% daily growth
      const benchmark = cumulativePnLData.length > 0
        ? cumulativePnLData[0].cumulative_pnl * benchmarkGrowth
        : 0;

      return {
        date: new Date(pnl.timestamp).toLocaleDateString(),
        pnl: pnl.cumulative_pnl,
        benchmark: benchmark,
        timestamp: pnl.timestamp
      };
    });
  };

  return (
    <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
      <TabsList className="grid w-full grid-cols-2">
        <TabsTrigger value="live">Live Operations</TabsTrigger>
        <TabsTrigger value="history">Historical Reports</TabsTrigger>
      </TabsList>

      <TabsContent value="live" className="space-y-4">
        {/* Active Orders Table */}
        <Card>
          <CardContent className="p-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold">Active Orders</h3>
              <div className="flex items-center space-x-2">
                <span className="text-sm">Open: {activeOrders.filter(o => o.status === 'open' || o.status === 'partially_filled').length}</span>
              </div>
            </div>

            {loadingActive ? (
              <div className="space-y-2">
                {[1, 2, 3].map((item) => (
                  <div key={item} className="flex space-x-4 p-2">
                    <Skeleton className="h-4 w-1/5" />
                    <Skeleton className="h-4 w-1/5" />
                    <Skeleton className="h-4 w-1/5" />
                    <Skeleton className="h-4 w-1/5" />
                    <Skeleton className="h-4 w-1/5" />
                  </div>
                ))}
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Market</TableHead>
                    <TableHead>Side</TableHead>
                    <TableHead>Size</TableHead>
                    <TableHead>Price</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {activeOrders.map((order) => (
                    <TableRow key={order.id}>
                      <TableCell className="font-medium">{order.market_id}</TableCell>
                      <TableCell>
                        <span className={order.side === 'buy' ? 'text-green-600' : 'text-red-600'}>
                          {order.side.toUpperCase()}
                        </span>
                      </TableCell>
                      <TableCell>{order.size}</TableCell>
                      <TableCell>${order.price.toFixed(2)}</TableCell>
                      <TableCell>
                        <span className={`px-2 py-1 rounded-full text-xs ${
                          order.status === 'open' ? 'bg-blue-100 text-blue-800' :
                          order.status === 'partially_filled' ? 'bg-yellow-100 text-yellow-800' :
                          order.status === 'filled' ? 'bg-green-100 text-green-800' :
                          'bg-gray-100 text-gray-800'
                        }`}>
                          {order.status.replace('_', ' ')}
                        </span>
                      </TableCell>
                      <TableCell>
                        <Button
                          onClick={() => handleCancelOrder(order.order_id)}
                          disabled={order.status !== 'open' && order.status !== 'partially_filled'}
                          variant="outline"
                          size="sm"
                          className="text-xs"
                        >
                          Cancel
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Pending Transactions */}
        <Card>
          <CardContent className="p-6">
            <h3 className="text-lg font-semibold mb-4">Pending Transactions</h3>

            {loadingTransactions ? (
              <div className="space-y-2">
                {[1, 2].map((item) => (
                  <div key={item} className="flex space-x-4 p-2">
                    <Skeleton className="h-4 w-1/4" />
                    <Skeleton className="h-4 w-1/4" />
                    <Skeleton className="h-4 w-1/4" />
                    <Skeleton className="h-4 w-1/4" />
                  </div>
                ))}
              </div>
            ) : pendingTransactions.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Transaction ID</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Market</TableHead>
                    <TableHead>Outcome</TableHead>
                    <TableHead>Amount</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Est. Completion</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {pendingTransactions.map((tx) => (
                    <TableRow key={tx.id}>
                      <TableCell className="font-mono text-sm">{tx.id}</TableCell>
                      <TableCell>
                        <span className={`px-2 py-1 rounded-full text-xs ${
                          tx.transaction_type === 'merge' ? 'bg-purple-100 text-purple-800' :
                          tx.transaction_type === 'redeem' ? 'bg-indigo-100 text-indigo-800' :
                          'bg-gray-100 text-gray-800'
                        }`}>
                          {tx.transaction_type}
                        </span>
                      </TableCell>
                      <TableCell>{tx.market_id}</TableCell>
                      <TableCell>{tx.outcome}</TableCell>
                      <TableCell>{tx.amount}</TableCell>
                      <TableCell>
                        <span className={`px-2 py-1 rounded-full text-xs ${
                          tx.status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                          tx.status === 'confirmed' ? 'bg-green-100 text-green-800' :
                          'bg-red-100 text-red-800'
                        }`}>
                          {tx.status}
                        </span>
                      </TableCell>
                      <TableCell>
                        {tx.estimated_completion ? new Date(tx.estimated_completion).toLocaleTimeString() : 'N/A'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <div className="text-center py-8 text-gray-500">
                No pending transactions
              </div>
            )}
          </CardContent>
        </Card>

        {/* Live Spread Visualizer */}
        <Card>
          <CardContent className="p-6">
            <h3 className="text-lg font-semibold mb-4">Live Spread Visualizer</h3>

            {loadingSpread ? (
              <div className="h-64 flex items-center justify-center">
                <Skeleton className="h-64 w-full" />
              </div>
            ) : spreadData.length > 0 ? (
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={spreadData}
                    margin={{ top: 20, right: 30, left: 20, bottom: 60 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="market_id"
                      angle={-45}
                      textAnchor="end"
                      height={60}
                      tick={{ fontSize: 12 }}
                    />
                    <YAxis domain={[0, 1]} />
                    <Tooltip
                      formatter={(value) => [`${Number(value).toFixed(2)}`, 'Price']}
                      labelFormatter={(label) => `Market: ${label}`}
                    />
                    <Legend />
                    <Bar dataKey="bid_price" name="Bid Price" fill="#10B981" />
                    <Bar dataKey="ask_price" name="Ask Price" fill="#EF4444" />
                    <Bar dataKey="fair_price" name="Fair Price" fill="#3B82F6" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                No spread data available
              </div>
            )}
          </CardContent>
        </Card>
      </TabsContent>

      <TabsContent value="history" className="space-y-4">
        {/* Cumulative PnL Chart */}
        <Card>
          <CardContent className="p-6">
            <h3 className="text-lg font-semibold mb-4">Cumulative PnL Over Time</h3>
            {loadingCumulativePnL ? (
              <div className="h-80 flex items-center justify-center">
                <Skeleton className="h-80 w-full" />
              </div>
            ) : (
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart
                    data={prepareCumulativePnLData()}
                    margin={{ top: 5, right: 30, left: 20, bottom: 50 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="date"
                      angle={-45}
                      textAnchor="end"
                      height={60}
                      tick={{ fontSize: 12 }}
                    />
                    <YAxis />
                    <Tooltip
                      formatter={(value, name) => [
                        `$${Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
                        name === 'pnl' ? 'Strategy PnL' : 'Benchmark (ETH)'
                      ]}
                      labelFormatter={(label) => `Date: ${label}`}
                    />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="pnl"
                      name="Strategy PnL"
                      stroke="#3B82F6"
                      strokeWidth={2}
                      dot={{ r: 4 }}
                      activeDot={{ r: 6 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="benchmark"
                      name="Benchmark (ETH)"
                      stroke="#10B981"
                      strokeWidth={2}
                      strokeDasharray="3 3"
                      dot={{ r: 4 }}
                      activeDot={{ r: 6 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Trade History Table */}
        <Card>
          <CardContent className="p-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold">Trade History</h3>
              <div className="flex space-x-2">
                <Select value={selectedMarket} onValueChange={handleMarketFilterChange}>
                  <SelectTrigger className="w-[180px]">
                    <SelectValue placeholder="Filter by Market" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">All Markets</SelectItem>
                    {getUniqueMarkets().map((market) => (
                      <SelectItem key={market} value={market}>{market}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Select value={tradeSortBy} onValueChange={handleSortByChange}>
                  <SelectTrigger className="w-[140px]">
                    <SelectValue placeholder="Sort by" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="timestamp">Date</SelectItem>
                    <SelectItem value="market_id">Market</SelectItem>
                    <SelectItem value="price">Price</SelectItem>
                    <SelectItem value="size">Size</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={tradeSortOrder} onValueChange={handleSortOrderChange}>
                  <SelectTrigger className="w-[100px]">
                    <SelectValue placeholder="Order" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="asc">Ascending</SelectItem>
                    <SelectItem value="desc">Descending</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {loadingTradeHistory ? (
              <div className="space-y-2">
                {[1, 2, 3, 4, 5].map((item) => (
                  <div key={item} className="flex space-x-4 p-2">
                    <Skeleton className="h-4 w-1/6" />
                    <Skeleton className="h-4 w-1/6" />
                    <Skeleton className="h-4 w-1/6" />
                    <Skeleton className="h-4 w-1/6" />
                    <Skeleton className="h-4 w-1/6" />
                    <Skeleton className="h-4 w-1/6" />
                  </div>
                ))}
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Market ID</TableHead>
                    <TableHead>Side</TableHead>
                    <TableHead>Price</TableHead>
                    <TableHead>Size</TableHead>
                    <TableHead>Fee</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {tradeHistory.map((trade) => (
                    <TableRow key={trade.id}>
                      <TableCell className="font-medium">
                        {new Date(trade.timestamp).toLocaleString()}
                      </TableCell>
                      <TableCell>{trade.market_id}</TableCell>
                      <TableCell>
                        <span className={trade.side === 'buy' ? 'text-green-600' : 'text-red-600'}>
                          {trade.side.toUpperCase()}
                        </span>
                      </TableCell>
                      <TableCell>${trade.price.toFixed(2)}</TableCell>
                      <TableCell>{trade.size.toFixed(2)}</TableCell>
                      <TableCell>{trade.fee ? `$${trade.fee.toFixed(2)}` : '-'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Win/Loss Analysis */}
        <Card>
          <CardContent className="p-6">
            <h3 className="text-lg font-semibold mb-4">Win/Loss Analysis</h3>
            {loadingWinLoss ? (
              <div className="h-64 flex items-center justify-center">
                <Skeleton className="h-64 w-full" />
              </div>
            ) : winLossAnalysis ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={[
                          { name: 'Profit', value: winLossAnalysis.profit_percentage },
                          { name: 'Loss', value: winLossAnalysis.loss_percentage }
                        ]}
                        cx="50%"
                        cy="50%"
                        labelLine={true}
                        outerRadius={80}
                        fill="#8884d8"
                        dataKey="value"
                        label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                      >
                        <Cell key={`cell-profit`} fill="#10B981" />
                        <Cell key={`cell-loss`} fill="#EF4444" />
                      </Pie>
                      <Tooltip formatter={(value) => [`${value}%`, 'Percentage']} />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="flex flex-col justify-center">
                  <div className="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg">
                    <h4 className="font-medium text-green-800">Profit Trades</h4>
                    <p className="text-2xl font-bold text-green-600">{winLossAnalysis.profit_count}</p>
                    <p className="text-sm text-green-600">{winLossAnalysis.profit_percentage}% of total trades</p>
                  </div>
                  <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
                    <h4 className="font-medium text-red-800">Loss Trades</h4>
                    <p className="text-2xl font-bold text-red-600">{winLossAnalysis.loss_count}</p>
                    <p className="text-sm text-red-600">{winLossAnalysis.loss_percentage}% of total trades</p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                No win/loss analysis data available
              </div>
            )}
          </CardContent>
        </Card>
      </TabsContent>
    </Tabs>
  );
};

export default TabbedInterface;