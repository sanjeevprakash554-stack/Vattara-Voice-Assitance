import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react';
import { useAuth } from './AuthContext';

const DashboardWebSocketContext = createContext(null);

export function DashboardWebSocketProvider({ children }) {
  const { token, user } = useAuth();
  const [connectionStatus, setConnectionStatus] = useState('disconnected'); // 'connecting' | 'connected' | 'disconnected' | 'error'
  const [lastEvent, setLastEvent] = useState(null);
  const [activeCalls, setActiveCalls] = useState([]);
  const [liveTranscripts, setLiveTranscripts] = useState({}); // call_id -> array of { speaker, text, timestamp }

  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const pingIntervalRef = useRef(null);
  const reconnectAttemptRef = useRef(0);
  const subscribersRef = useRef(new Set());

  // Subscribe to specific event types: subscribe('CALL_STARTED', (data) => ...)
  const subscribe = useCallback((eventType, callback) => {
    const subscriber = { eventType, callback };
    subscribersRef.current.add(subscriber);
    return () => {
      subscribersRef.current.delete(subscriber);
    };
  }, []);

  const connect = useCallback(() => {
    // Only connect if user is authenticated with a valid token
    if (!token || token === 'demo_token' || token.startsWith('mock_jwt_token')) {
      setConnectionStatus('disconnected');
      return;
    }

    // Clean up any existing connection
    if (wsRef.current) {
      try {
        wsRef.current.close();
      } catch (e) {
        // ignore
      }
      wsRef.current = null;
    }

    setConnectionStatus('connecting');

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/v1/dashboard/ws?token=${encodeURIComponent(token)}`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('[DashboardWS] Connected to real-time telemetry stream.');
        setConnectionStatus('connected');
        reconnectAttemptRef.current = 0;

        // Start heartbeat ping every 25 seconds
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send('ping');
          }
        }, 25000);
      };

      ws.onmessage = (evt) => {
        try {
          const payload = JSON.parse(evt.data);
          const { event, data } = payload;

          if (event === 'PONG') return; // ignore heartbeat responses

          setLastEvent(payload);

          // Update active calls state
          if (event === 'CALL_STARTED' && data?.call_id) {
            setActiveCalls((prev) => {
              const exists = prev.some((c) => c.call_id === data.call_id);
              if (exists) return prev;
              return [data, ...prev];
            });
          } else if ((event === 'CALL_COMPLETED' || event === 'CALL_FAILED') && data?.call_id) {
            setActiveCalls((prev) => prev.filter((c) => c.call_id !== data.call_id));
          }

          // Update live transcripts state
          if ((event === 'TRANSCRIPT_RECEIVED' || event === 'AI_RESPONSE_GENERATED') && data?.call_id) {
            setLiveTranscripts((prev) => {
              const existing = prev[data.call_id] || [];
              return {
                ...prev,
                [data.call_id]: [
                  ...existing,
                  {
                    speaker: data.speaker || (event === 'TRANSCRIPT_RECEIVED' ? 'caller' : 'assistant'),
                    text: data.text || '',
                    timestamp: data.timestamp || new Date().toISOString(),
                  },
                ],
              };
            });
          }

          // Notify all registered event subscribers
          subscribersRef.current.forEach(({ eventType, callback }) => {
            if (eventType === '*' || eventType === event) {
              try {
                callback(data, payload);
              } catch (err) {
                console.error(`[DashboardWS] Error in subscriber for ${event}:`, err);
              }
            }
          });
        } catch (err) {
          console.warn('[DashboardWS] Failed to parse message frame:', err);
        }
      };

      ws.onerror = (err) => {
        console.warn('[DashboardWS] WebSocket encounter error:', err);
        setConnectionStatus('error');
      };

      ws.onclose = (evt) => {
        console.log('[DashboardWS] Connection closed (code:', evt.code, ')');
        setConnectionStatus('disconnected');
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }

        // Automatic reconnection with exponential backoff (1s, 2s, 4s, ... max 15s)
        if (token && !evt.wasClean && evt.code !== 4001 && evt.code !== 4003) {
          const delay = Math.min(1000 * Math.pow(1.5, reconnectAttemptRef.current), 15000);
          reconnectAttemptRef.current += 1;
          console.log(`[DashboardWS] Reconnecting in ${Math.round(delay / 1000)}s (attempt ${reconnectAttemptRef.current})...`);
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, delay);
        }
      };
    } catch (exc) {
      console.error('[DashboardWS] Failed to instantiate WebSocket:', exc);
      setConnectionStatus('error');
    }
  }, [token]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  const isConnected = connectionStatus === 'connected';

  return (
    <DashboardWebSocketContext.Provider
      value={{
        connectionStatus,
        isConnected,
        lastEvent,
        activeCalls,
        liveTranscripts,
        subscribe,
        reconnect: connect,
      }}
    >
      {children}
    </DashboardWebSocketContext.Provider>
  );
}

export function useDashboardWebSocket() {
  const ctx = useContext(DashboardWebSocketContext);
  if (!ctx) {
    return {
      connectionStatus: 'disconnected',
      isConnected: false,
      lastEvent: null,
      activeCalls: [],
      liveTranscripts: {},
      subscribe: () => () => {},
      reconnect: () => {},
    };
  }
  return ctx;
}
