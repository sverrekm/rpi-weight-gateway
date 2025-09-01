import React, { useEffect, useState } from 'react';

interface StatusIndicatorProps {
  label: string;
  isActive: boolean;
  additionalInfo?: string;
}

export const StatusIndicator: React.FC<StatusIndicatorProps> = ({ 
  label, 
  isActive, 
  additionalInfo 
}) => {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      marginLeft: '16px',
      padding: '4px 8px',
      borderRadius: '4px',
      backgroundColor: isActive ? '#10B98120' : '#F3F4F6',
      color: isActive ? '#065F46' : '#6B7280',
      fontSize: '12px',
      fontWeight: 500,
    }}>
      <div style={{
        width: '8px',
        height: '8px',
        borderRadius: '50%',
        backgroundColor: isActive ? '#10B981' : '#9CA3AF',
        marginRight: '6px',
      }} />
      <span>{label}</span>
      {additionalInfo && (
        <span style={{
          marginLeft: '4px',
          fontWeight: 600,
          color: isActive ? '#065F46' : '#4B5563'
        }}>
          {additionalInfo}
        </span>
      )}
    </div>
  );
};

export const StatusBar: React.FC = () => {
  const [ipAddress, setIpAddress] = useState<string>('');
  const [isOnline, setIsOnline] = useState<boolean>(navigator.onLine);
  const [brokerStatus, setBrokerStatus] = useState<boolean>(false);

  useEffect(() => {
    // Check network status
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // Fetch IP address
    const fetchIP = async () => {
      try {
        const response = await fetch('/api/network/ip');
        if (response.ok) {
          const data = await response.json();
          setIpAddress(data.ip || 'N/A');
        }
      } catch (error) {
        console.error('Error fetching IP:', error);
      }
    };

    // Check MQTT broker status
    const checkBrokerStatus = async () => {
      try {
        const response = await fetch('/api/mqtt/status');
        if (response.ok) {
          const data = await response.json();
          setBrokerStatus(data.connected || false);
        }
      } catch (error) {
        console.error('Error checking broker status:', error);
        setBrokerStatus(false);
      }
    };

    fetchIP();
    checkBrokerStatus();
    
    // Set up polling for status updates
    const interval = setInterval(() => {
      fetchIP();
      checkBrokerStatus();
    }, 30000); // Update every 30 seconds

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
      clearInterval(interval);
    };
  }, []);

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      marginLeft: 'auto',
      gap: '12px'
    }}>
      <StatusIndicator 
        label="Network" 
        isActive={isOnline} 
        additionalInfo={ipAddress || 'Offline'} 
      />
      <StatusIndicator 
        label="MQTT" 
        isActive={brokerStatus} 
        additionalInfo={brokerStatus ? 'Connected' : 'Disconnected'} 
      />
    </div>
  );
};
