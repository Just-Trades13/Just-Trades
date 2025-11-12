/**
 * Control Center Page
 * Manual trading interface with real-time updates
 */

import { useState, useEffect } from 'react';
import { strategiesAPI } from '../services/api';
import { wsService } from '../services/websocket';
import Layout from '../components/Layout';
import './ControlCenter.css';

const ControlCenter = () => {
  const [strategies, setStrategies] = useState([]);
  const [selectedStrategy, setSelectedStrategy] = useState(null);
  const [selectedTicker, setSelectedTicker] = useState('');
  const [positionSize, setPositionSize] = useState(1);
  const [logs, setLogs] = useState([]);

  const connectWebSocket = () => {
    wsService.connect();
    wsService.on('log_update', (data) => {
      setLogs((prev) => [data, ...prev].slice(0, 100));
    });
  };

  const loadStrategies = async () => {
    try {
      const response = await strategiesAPI.getManual();
      setStrategies(response.data.strategies || []);
    } catch (error) {
      console.error('Failed to load strategies:', error);
    }
  };

  const handleBuy = async () => {
    // TODO: Implement buy order
    console.log('Buy order:', { selectedStrategy, selectedTicker, positionSize });
  };

  const handleSell = async () => {
    // TODO: Implement sell order
    console.log('Sell order:', { selectedStrategy, selectedTicker, positionSize });
  };

  const handleClose = async () => {
    // TODO: Implement close position
    console.log('Close position:', { selectedStrategy, selectedTicker });
  };

  useEffect(() => {
    loadStrategies();
    connectWebSocket();
    return () => {
      wsService.disconnect();
      wsService.off('log_update');
    };
  }, []);

  const handleCloseAll = async () => {
    if (window.confirm('Close all positions?')) {
      // TODO: Implement close all positions
      console.log('Close all positions');
    }
  };

  const handleClearAll = async () => {
    if (window.confirm('Clear all logs?')) {
      setLogs([]);
    }
  };

  const handleDisableAllStrategies = async () => {
    if (window.confirm('Disable all strategies?')) {
      // TODO: Implement disable all strategies
      console.log('Disable all strategies');
    }
  };

  const toggleStrategy = async (strategyId, currentlyEnabled) => {
    try {
      const newEnabledState = !currentlyEnabled;
      // TODO: Implement strategy toggle API
      // await strategiesAPI.toggleStrategy(strategyId, newEnabledState);
      
      // Optimistically update UI
      setStrategies((prev) =>
        prev.map((strategy) =>
          strategy.id === strategyId
            ? { ...strategy, enabled: newEnabledState }
            : strategy
        )
      );
    } catch (error) {
      console.error('Failed to toggle strategy:', error);
    }
  };

  return (
    <Layout>
      <div className="control-center-container">
        <div className="control-center-header">
          <h2>CONTROL CENTER</h2>
        </div>

        <div className="manual-trader-panel">
          <form className="manual-trader-form">
            <div className="form-row">
              <label>Strategy</label>
              <select
                value={selectedStrategy?.id || ''}
                onChange={(e) => {
                  const strategy = strategies.find((s) => s.id === parseInt(e.target.value));
                  setSelectedStrategy(strategy || null);
                }}
                className="form-select"
              >
                <option value="">Select Strategy</option>
                {strategies.map((strategy) => (
                  <option key={strategy.id} value={strategy.id}>
                    {strategy.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-row">
              <label>Ticker</label>
              <input
                type="text"
                value={selectedTicker}
                onChange={(e) => setSelectedTicker(e.target.value.toUpperCase())}
                placeholder="Enter ticker"
                className="form-input"
              />
            </div>

            <div className="form-row">
              <button
                type="button"
                onClick={handleClose}
                className="btn btn-secondary btn-action"
              >
                Close
              </button>
            </div>

            <div className="form-row form-actions">
              <button
                type="button"
                onClick={handleSell}
                className="btn btn-danger btn-action"
              >
                Sell
              </button>
              <div className="position-size-group">
                <label>Position Size (Qty)</label>
                <input
                  type="number"
                  value={positionSize}
                  onChange={(e) => setPositionSize(parseInt(e.target.value) || 1)}
                  min="1"
                  className="form-input form-input-number"
                />
              </div>
              <button
                type="button"
                onClick={handleBuy}
                className="btn btn-success btn-action"
              >
                Buy
              </button>
            </div>
          </form>
        </div>

        <div className="control-buttons-container">
          <button className="btn btn-control btn-secondary" onClick={handleCloseAll}>
            Close All
          </button>
          <button className="btn btn-control btn-secondary" onClick={handleClearAll}>
            Clear All
          </button>
          <button className="btn btn-control btn-danger" onClick={handleDisableAllStrategies}>
            Disable All Strat
          </button>
        </div>

        <div className="control-center-content">
          <div className="live-strategies-panel">
            <h3>LIVE STRATEGIES</h3>
            <div className="strategies-list">
              {strategies.length === 0 ? (
                <div className="no-strategies">No strategies available</div>
              ) : (
                strategies.map((strategy) => (
                  <div key={strategy.id} className="strategy-item">
                    <div className="strategy-info">
                      <div className="strategy-name">{strategy.name}</div>
                    </div>
                    <label className="toggle-switch">
                      <input
                        type="checkbox"
                        checked={strategy.enabled || false}
                        onChange={(e) => toggleStrategy(strategy.id, strategy.enabled)}
                      />
                      <span className="toggle-slider"></span>
                    </label>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="logs-panel">
            <h3>LOGS</h3>
            <div className="logs-container">
              {logs.length === 0 ? (
                <div className="no-logs">No logs yet</div>
              ) : (
                logs.map((log, index) => (
                  <div key={index} className="log-entry">
                    {log.timestamp && (
                      <span className="log-timestamp">
                        {new Date(log.timestamp).toLocaleTimeString()}
                      </span>
                    )}
                    <span className="log-message">{log.message || log}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default ControlCenter;

