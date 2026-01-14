'use client';

import React, { useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { apiService, connectWebSocket, PnLData, InventoryData, VolumeData } from '@/services/api';

const KPICards = () => {
  const queryClient = useQueryClient();

  // WebSocket connection to receive real-time updates
  useEffect(() => {
    const handleWebSocketMessage = (data: any) => {
      if (data.type === 'update' && data.stats) {
        // Update the query cache with real-time stats
        queryClient.setQueryData(['stats'], data.stats);
      }
    };

    const ws = connectWebSocket(handleWebSocketMessage);

    return () => {
      // Cleanup WebSocket connection
      ws.close();
    };
  }, [queryClient]);

  // Use TanStack Query to fetch and cache data
  const { data: stats, isLoading } = useQuery({
    queryKey: ['stats'],
    queryFn: apiService.getStats, // Using the stats endpoint that matches backend
    refetchInterval: 5000, // Fallback to polling if WebSocket fails
    staleTime: 2000, // Data is considered fresh for 2 seconds
  });

  // Extract data from the stats object - map backend stats to PnL format
  const pnl = stats?.pnl || 0;
  const dailyPnl = stats ? (stats.pnl * 0.1) : 0; // Mock daily pnl based on total pnl

  // For inventory and volume, we'll use separate queries
  const { data: inventoryData } = useQuery<InventoryData>({
    queryKey: ['inventory'],
    queryFn: apiService.getInventory,
    refetchInterval: 5000,
    staleTime: 2000,
  });

  const { data: volumeData } = useQuery<VolumeData>({
    queryKey: ['volume'],
    queryFn: apiService.getVolume,
    refetchInterval: 5000,
    staleTime: 2000,
  });

  // Calculate inventory skew
  const inventorySkew = {
    yes: inventoryData?.yes_positions || 0,
    no: inventoryData?.no_positions || 0
  };

  // Calculate volume data
  const volume24h = volumeData?.volume_24h || 0;
  const tradeCount24h = volumeData?.trade_count_24h || 0;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
      {/* Real-time PnL Card */}
      <Card>
        <CardHeader className="pb-2">
          <CardDescription>Real-time PnL</CardDescription>
          <CardTitle className={`text-2xl ${pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
            {isLoading ? 'Loading...' : `$${pnl.toFixed(2)}`}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className={`text-sm ${dailyPnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
            {isLoading ? '' : `${dailyPnl >= 0 ? '▲' : '▼'} ${Math.abs(dailyPnl).toFixed(2)} (24h)`}
          </div>
        </CardContent>
      </Card>

      {/* Inventory Skew Card */}
      <Card>
        <CardHeader className="pb-2">
          <CardDescription>Current Inventory Skew</CardDescription>
          <CardTitle className="text-2xl">
            {isLoading ? 'Loading...' : `Long YES: ${inventorySkew.yes} | Long NO: ${inventorySkew.no}`}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-muted-foreground">
            {isLoading ? '' : `Net Position: ${inventorySkew.yes - inventorySkew.no}`}
          </div>
        </CardContent>
      </Card>

      {/* 24h Volume Card */}
      <Card>
        <CardHeader className="pb-2">
          <CardDescription>24h Volume Traded</CardDescription>
          <CardTitle className="text-2xl">
            {isLoading ? 'Loading...' : `$${volume24h.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-muted-foreground">
            {isLoading ? '' : `Trades: ${tradeCount24h}`}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default KPICards;