'use client';

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { AlertTriangle, Wifi, WifiOff } from 'lucide-react';
import useWebSocket from '@/utils/useWebSocket';
import { apiService, WalletBalance } from '@/services/api';

const Header = () => {
  // Using a mock WebSocket URL for now - in a real app this would connect to the backend
  const { isConnected } = useWebSocket('ws://localhost:8080/ws');
  const [walletBalance, setWalletBalance] = useState<number>(0);
  const [loadingBalance, setLoadingBalance] = useState<boolean>(true);
  const [emergencyStopActive, setEmergencyStopActive] = useState<boolean>(false);

  // Load wallet balance on component mount
  useEffect(() => {
    const fetchBalance = async () => {
      try {
        const data: WalletBalance = await apiService.getWalletBalance();
        setWalletBalance(data.usdc_balance);
      } catch (error) {
        console.error('Failed to fetch wallet balance:', error);
      } finally {
        setLoadingBalance(false);
      }
    };

    fetchBalance();
  }, []);

  const handleEmergencyStop = async () => {
    try {
      await apiService.triggerEmergencyStop(!emergencyStopActive);
      setEmergencyStopActive(!emergencyStopActive);
    } catch (error) {
      console.error('Failed to trigger emergency stop:', error);
      // Fallback to local state if API fails
      setEmergencyStopActive(!emergencyStopActive);
    }
  };

  return (
    <Card className="mb-6">
      <CardContent className="py-4 flex justify-between items-center">
        <div className="flex items-center space-x-4">
          <div className={`flex items-center ${isConnected ? 'text-green-500' : 'text-red-500'}`}>
            {isConnected ? <Wifi className="mr-2 h-4 w-4" /> : <WifiOff className="mr-2 h-4 w-4" />}
            <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
          </div>
          <div className="flex items-center">
            <span className="font-semibold">Wallet Balance:</span>
            <span className="ml-2 font-mono">
              {loadingBalance ? 'Loading...' : `${walletBalance.toFixed(2)} USDC`}
            </span>
          </div>
        </div>

        <Button
          variant={emergencyStopActive ? "destructive" : "default"}
          onClick={handleEmergencyStop}
          className="flex items-center"
        >
          {emergencyStopActive ? (
            <>
              <AlertTriangle className="mr-2 h-4 w-4" />
              EMERGENCY STOP ACTIVE
            </>
          ) : (
            <>
              <AlertTriangle className="mr-2 h-4 w-4" />
              EMERGENCY STOP
            </>
          )}
        </Button>
      </CardContent>
    </Card>
  );
};

export default Header;