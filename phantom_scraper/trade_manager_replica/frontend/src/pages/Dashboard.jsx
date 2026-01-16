/**
 * Dashboard Page
 * View recorded strategy performance and analytics
 */

import { useState, useEffect } from 'react';
import { dashboardAPI, tradesAPI, profilesAPI } from '../services/api';
import api from '../services/api';
import Layout from '../components/Layout';
import './Dashboard.css';

const Dashboard = () => {
  const [summary, setSummary] = useState(null);
  const [trades, setTrades] = useState([]);
  const [openTrades, setOpenTrades] = useState([]);
  const [filters, setFilters] = useState({
    user: 'J.T.M.J',
    strategy: '',
    symbol: '',
    timeframe: '',
    dateRange: { start: null, end: null },
  });
  const [statConfig, setStatConfig] = useState(null);
  const [favorites, setFavorites] = useState([]);
  const [loading, setLoading] = useState(false);
  const [mounted, setMounted] = useState(false);

  // Real data states for chart and calendar
  const [chartData, setChartData] = useState([]);
  const [calendarData, setCalendarData] = useState({});

  useEffect(() => {
    setMounted(true);
    loadDashboardData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Only load once on mount

  // Separate effect for filters
  useEffect(() => {
    const timer = setTimeout(() => {
      loadDashboardData();
    }, 300); // Debounce filter changes
    
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.user, filters.strategy, filters.symbol, filters.timeframe]); // Re-run when filter values change

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      console.log('Loading dashboard data...');
      
      // Load data sequentially to catch which one fails
      try {
        const summaryRes = await dashboardAPI.getSummary();
        console.log('Summary loaded:', summaryRes.data);
        // Only update if we got valid data, otherwise keep mock data
        if (summaryRes.data && (summaryRes.data.total_strategies > 0 || summaryRes.data.total_pnl !== 0)) {
          setSummary(summaryRes.data);
        }
      } catch (error) {
        console.log('Summary API failed, keeping mock data:', error.message);
        // Keep existing mock data, don't overwrite with zeros
      }
      
      try {
        const tradesRes = await tradesAPI.getAll({ usageType: true, ...filters });
        console.log('Trades loaded:', tradesRes.data);
        // Only update if we got valid trades, otherwise keep mock data
        if (tradesRes.data && tradesRes.data.trades && tradesRes.data.trades.length > 0) {
          setTrades(tradesRes.data.trades);
        }
      } catch (error) {
        console.log('Trades API failed, keeping mock data:', error.message);
        // Keep existing mock data
      }
      
      try {
        const openTradesRes = await tradesAPI.getOpen({ usageType: true, ...filters });
        console.log('Open trades loaded:', openTradesRes.data);
        setOpenTrades(openTradesRes.data.trades || []);
      } catch (error) {
        console.log('Open trades API failed, using empty array:', error.message);
        setOpenTrades([]);
      }
      
      try {
        const configRes = await profilesAPI.getStatConfig();
        console.log('Config loaded:', configRes.data);
        setStatConfig(configRes.data);
      } catch (error) {
        console.log('Config API failed:', error.message);
      }
      
      try {
        const favoritesRes = await profilesAPI.getFavorites();
        console.log('Favorites loaded:', favoritesRes.data);
        if (favoritesRes.data && favoritesRes.data.favorites) {
          setFavorites(favoritesRes.data.favorites);
        } else if (Array.isArray(favoritesRes.data)) {
          setFavorites(favoritesRes.data);
        }
      } catch (error) {
        console.log('Favorites API failed:', error.message);
        // Don't set state if API fails
      }

      // Fetch chart data (PnL and drawdown)
      try {
        const chartRes = await api.get('/dashboard/pnl-drawdown-chart');
        console.log('Chart data loaded:', chartRes.data);
        if (chartRes.data && chartRes.data.chart_data && chartRes.data.chart_data.length > 0) {
          // Transform API data to chart format
          const formattedChartData = chartRes.data.chart_data.map(d => ({
            date: new Date(d.timestamp),
            profit: d.pnl || 0,
            drawdown: d.drawdown || 0
          }));
          setChartData(formattedChartData);
        }
      } catch (error) {
        console.log('Chart API failed:', error.message);
      }

      // Fetch calendar data
      try {
        const calendarRes = await api.get('/dashboard/calendar-data');
        console.log('Calendar data loaded:', calendarRes.data);
        if (calendarRes.data && calendarRes.data.calendar_data) {
          // Transform API data to calendar format: { 'YYYY-MM-DD': { profit: X, count: Y } }
          const formattedCalendarData = {};
          calendarRes.data.calendar_data.forEach(d => {
            formattedCalendarData[d.date] = {
              profit: d.pnl || 0,
              count: d.trade_count || 0
            };
          });
          setCalendarData(formattedCalendarData);
        }
      } catch (error) {
        console.log('Calendar API failed:', error.message);
      }

      console.log('Dashboard data loading complete');
    } catch (error) {
      console.error('Failed to load dashboard data:', error);
      // Set empty data on error so page still renders
      setSummary({ total_strategies: 0, active_positions: 0, total_pnl: 0, today_pnl: 0 });
      setTrades([]);
      setOpenTrades([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <div className="dashboard-container">
        <div className="dashboard-header">
          <h2>DASHBOARD</h2>
          <button className="btn btn-primary">VIEWING RECORDED STRATS</button>
        </div>

        {/* Filters */}
        <div className="dashboard-filters">
          <select
            value={filters.user || 'J.T.M.J'}
            onChange={(e) => setFilters({ ...filters, user: e.target.value })}
            className="form-control"
          >
            <option value="J.T.M.J">J.T.M.J</option>
            <option value="">Select User (optional)</option>
          </select>
          <select
            value={filters.strategy}
            onChange={(e) => setFilters({ ...filters, strategy: e.target.value })}
            className="form-control"
          >
            <option value="">Select Strategy (optional)</option>
          </select>
          <select
            value={filters.symbol}
            onChange={(e) => setFilters({ ...filters, symbol: e.target.value })}
            className="form-control"
          >
            <option value="">Select Symbol (optional)</option>
          </select>
          <select
            value={filters.timeframe}
            onChange={(e) => setFilters({ ...filters, timeframe: e.target.value })}
            className="form-control"
          >
            <option value="">Select TimeFrame (optional)</option>
          </select>
          <a href="#" className="show-all-link">
            Show All Cards
          </a>
        </div>

        {/* Summary Cards - Always render, show loading indicator if loading */}
        <div className="dashboard-summary">
          {loading && !summary && (
            <div className="loading">Loading dashboard data...</div>
          )}
          <div className="summary-card">
            <h3>TOTAL STRATEGIES</h3>
            <p className="summary-value">{summary?.total_strategies || 0}</p>
          </div>
          <div className="summary-card">
            <h3>ACTIVE POSITIONS</h3>
            <p className="summary-value">{summary?.active_positions || 0}</p>
          </div>
          <div className="summary-card">
            <h3>TOTAL P&L</h3>
            <p className="summary-value">${(summary?.total_pnl || 0).toFixed(2)}</p>
          </div>
          <div className="summary-card">
            <h3>TODAY P&L</h3>
            <p className="summary-value">${(summary?.today_pnl || 0).toFixed(2)}</p>
          </div>
        </div>

        {/* Profit vs Drawdown Chart */}
        <div className="dashboard-chart">
          <h3>PROFIT VS DRAWDOWN</h3>
          <div className="chart-container">
            <div className="chart-legend">
              <span className="legend-item">
                <span className="legend-color profit-color"></span>
                Cumulative Profit
              </span>
              <span className="legend-item">
                <span className="legend-color drawdown-color"></span>
                Cumulative Drawdown
              </span>
            </div>
            <div className="chart-area">
              <svg className="chart-svg" viewBox="0 0 1000 500" preserveAspectRatio="none">
                {/* Dynamic Y-axis and chart rendering based on real data */}
                {(() => {
                  // Calculate max values from actual data
                  const maxProfit = chartData.length > 0
                    ? Math.max(...chartData.map(d => Math.abs(d.profit || 0)), ...chartData.map(d => Math.abs(d.drawdown || 0)))
                    : 1000;
                  // Round up to nearest nice number
                  const yMax = Math.ceil(maxProfit / 1000) * 1000 || 1000;
                  const yStep = yMax / 5;
                  const yLabels = Array.from({ length: 6 }, (_, i) => i * yStep);

                  // Build date positions from actual chart data
                  const tradingDays = chartData.length;
                  const xStep = tradingDays > 1 ? 900 / (tradingDays - 1) : 0;

                  const dates = chartData.map((d, i) => {
                    const date = d.date instanceof Date ? d.date : new Date(d.date);
                    const month = date.toLocaleString('default', { month: 'short' });
                    const day = date.getDate();
                    return {
                      x: 50 + i * xStep,
                      label: `${month} ${day}`,
                      date: date,
                      dataIndex: i
                    };
                  });

                  // Draw profit and drawdown lines
                  const profitPoints = chartData.map((d, i) => {
                    const x = dates[i]?.x || 50;
                    const y = 450 - ((d.profit || 0) / yMax * 400);
                    return `${x},${y}`;
                  }).join(' ');

                  const drawdownPoints = chartData.map((d, i) => {
                    const x = dates[i]?.x || 50;
                    const y = 450 - ((d.drawdown || 0) / yMax * 400);
                    return `${x},${y}`;
                  }).join(' ');

                  return (
                    <>
                      {/* Y-axis labels */}
                      {yLabels.map((val, i) => {
                        const yPos = 450 - (val / yMax * 400);
                        return (
                          <g key={i}>
                            <line x1="50" y1={yPos} x2="950" y2={yPos}
                                  stroke="rgba(255, 255, 255, 0.1)" strokeWidth="1" />
                            <text x="40" y={yPos + 4} fill="rgba(255, 255, 255, 0.6)"
                                  fontSize="11" textAnchor="end" fontFamily="Poppins, sans-serif">
                              {val.toLocaleString()}
                            </text>
                          </g>
                        );
                      })}
                      {/* Profit line (green) */}
                      {chartData.length > 0 && (
                        <polyline
                          points={profitPoints}
                          fill="none"
                          stroke="#2dce89"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      )}
                      {/* Drawdown line (red) */}
                      {chartData.length > 0 && (
                        <polyline
                          points={drawdownPoints}
                          fill="none"
                          stroke="#fd5d93"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      )}
                      {/* Data point circles */}
                      {chartData.map((d, i) => {
                        const x = dates[i]?.x || 50;
                        const profitY = 450 - ((d.profit || 0) / yMax * 400);
                        const drawdownY = 450 - ((d.drawdown || 0) / yMax * 400);
                        return (
                          <g key={i}>
                            <circle cx={x} cy={profitY} r="3" fill="#2dce89" stroke="#fff" strokeWidth="1" />
                            {(d.drawdown || 0) > 0 && (
                              <circle cx={x} cy={drawdownY} r="3" fill="#fd5d93" stroke="#fff" strokeWidth="1" />
                            )}
                          </g>
                        );
                      })}
                      {/* X-axis labels - show only every few labels if many data points */}
                      {dates.filter((_, i) => chartData.length < 15 || i % Math.ceil(chartData.length / 10) === 0).map((dateInfo, i) => (
                        <g key={i}>
                          <line x1={dateInfo.x} y1="450" x2={dateInfo.x} y2="455"
                                stroke="rgba(255, 255, 255, 0.3)" strokeWidth="1" />
                          <text x={dateInfo.x} y="470" fill="rgba(255, 255, 255, 0.6)"
                                fontSize="10" textAnchor="middle" fontFamily="Poppins, sans-serif">
                            {dateInfo.label}
                          </text>
                        </g>
                      ))}
                      {/* Show message if no data */}
                      {chartData.length === 0 && (
                        <text x="500" y="250" fill="rgba(255, 255, 255, 0.5)"
                              fontSize="14" textAnchor="middle" fontFamily="Poppins, sans-serif">
                          No trade data available
                        </text>
                      )}
                    </>
                  );
                })()}
              </svg>
            </div>
          </div>
        </div>

        {/* Trade History Table and Calendar */}
        <div className="dashboard-content-grid">
          <div className="dashboard-table">
            <h3>TRADE HISTORY</h3>
            {loading && trades.length === 0 ? (
              <div className="loading">Loading trades...</div>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>STATUS</th>
                    <th>OPEN TIME</th>
                    <th>CLOSED TIME</th>
                    <th>STRATEGY</th>
                    <th>SYMBOL</th>
                    <th>SIDE</th>
                    <th>SIZE</th>
                    <th>ENTRY</th>
                    <th>EXIT</th>
                    <th>PROFIT</th>
                    <th>DRAWDOWN</th>
                  </tr>
                </thead>
                <tbody>
                  {trades.length === 0 ? (
                    <tr>
                      <td colSpan="11" className="empty-state">
                        No trades found
                      </td>
                    </tr>
                  ) : (
                    trades.map((trade) => (
                      <tr key={trade.id}>
                        <td>
                          <span className={`status-badge ${(trade.status || '').toLowerCase()}`}>
                            {trade.status || 'Filled'}
                          </span>
                        </td>
                        <td>{trade.open_time ? (() => {
                          const d = new Date(trade.open_time);
                          if (isNaN(d.getTime())) return '-';
                          const month = d.toLocaleString('en-US', { month: 'short' });
                          const day = d.getDate();
                          const year = d.getFullYear();
                          const hour = d.getHours();
                          const minute = d.getMinutes();
                          const ampm = hour >= 12 ? 'PM' : 'AM';
                          const hour12 = hour % 12 || 12;
                          const minStr = minute.toString().padStart(2, '0');
                          return `${month} ${day}, ${year} ${hour12}:${minStr} ${ampm}`;
                        })() : '-'}</td>
                        <td>{trade.closed_time ? (() => {
                          const d = new Date(trade.closed_time);
                          if (isNaN(d.getTime())) return trade.status === 'OPEN' ? 'In Progress' : '-';
                          const month = d.toLocaleString('en-US', { month: 'short' });
                          const day = d.getDate();
                          const year = d.getFullYear();
                          const hour = d.getHours();
                          const minute = d.getMinutes();
                          const ampm = hour >= 12 ? 'PM' : 'AM';
                          const hour12 = hour % 12 || 12;
                          const minStr = minute.toString().padStart(2, '0');
                          return `${month} ${day}, ${year} ${hour12}:${minStr} ${ampm}`;
                        })() : (trade.status === 'OPEN' ? 'In Progress' : '-')}</td>
                        <td>{trade.strategy_name || trade.strategy || 'N/A'}</td>
                        <td>{trade.symbol || 'N/A'}</td>
                        <td className={trade.side === 'BUY' ? 'buy' : 'sell'}>{trade.side || 'N/A'}</td>
                        <td>{trade.quantity || trade.size || 'N/A'}</td>
                        <td>{trade.entry_price?.toFixed(2) || '-'}</td>
                        <td>{trade.exit_price?.toFixed(2) || '-'}</td>
                        <td className={(trade.pnl || trade.profit || 0) >= 0 ? 'profit' : 'loss'}>
                          ${(trade.pnl ?? trade.profit)?.toFixed(2) || '0.00'}
                        </td>
                        <td className={trade.drawdown >= 0 ? 'drawdown' : ''}>
                          {trade.drawdown !== null && trade.drawdown !== undefined ? `$${trade.drawdown.toFixed(2)}` : '-'}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            )}
          </div>

          {/* Calendar Widget - Dynamic based on current date */}
          <div className="dashboard-calendar">
            {(() => {
              const now = new Date();
              const currentMonth = now.getMonth();
              const currentYear = now.getFullYear();
              const monthName = now.toLocaleString('default', { month: 'long' }).toUpperCase();

              // Get first day of month and calculate start of calendar grid
              const firstOfMonth = new Date(currentYear, currentMonth, 1);
              const startDayOfWeek = firstOfMonth.getDay(); // 0 = Sunday
              const calendarStart = new Date(firstOfMonth);
              calendarStart.setDate(calendarStart.getDate() - startDayOfWeek);

              // Generate 14 days (2 weeks) for the calendar grid
              const days = [];
              for (let i = 0; i < 14; i++) {
                const date = new Date(calendarStart);
                date.setDate(calendarStart.getDate() + i);
                const day = date.getDate();
                const isCurrentMonth = date.getMonth() === currentMonth;
                const dateKey = date.toISOString().split('T')[0];
                const dayTrades = calendarData[dateKey];
                const hasTrades = !!dayTrades;

                days.push(
                  <div
                    key={i}
                    className={`calendar-day ${!isCurrentMonth ? 'other-month' : ''} ${hasTrades ? 'has-trades' : ''}`}
                  >
                    {hasTrades ? (
                      <div className="calendar-day-content">
                        <div className={`calendar-day-profit ${dayTrades.profit >= 0 ? 'profit' : 'loss'}`}>
                          ${Math.abs(dayTrades.profit).toLocaleString()}
                        </div>
                        <div className="calendar-day-count">({dayTrades.count} trades)</div>
                      </div>
                    ) : (
                      day
                    )}
                  </div>
                );
              }

              return (
                <>
                  <div className="calendar-header">
                    <h3>{monthName} {currentYear}</h3>
                    <div className="calendar-nav">
                      <button className="calendar-nav-btn">today</button>
                      <button className="calendar-nav-btn">back</button>
                      <button className="calendar-nav-btn">next</button>
                    </div>
                  </div>
                  <div className="calendar-grid">
                    <div className="calendar-weekdays">
                      {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(day => (
                        <div key={day} className="calendar-weekday">{day}</div>
                      ))}
                    </div>
                    <div className="calendar-days">
                      {days}
                    </div>
                  </div>
                  <div className="calendar-footer">
                    <div className="calendar-logo">JT</div>
                  </div>
                </>
              );
            })()}
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default Dashboard;

