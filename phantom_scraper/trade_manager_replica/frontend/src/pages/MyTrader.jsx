/**
 * My Trader Page
 * Live trading strategies
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { strategiesAPI } from '../services/api';
import Layout from '../components/Layout';
import './MyTrader.css';

const MyTrader = () => {
  const [strategies, setStrategies] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);
  const [expandedRows, setExpandedRows] = useState(new Set());
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage] = useState(10);
  const navigate = useNavigate();

  useEffect(() => {
    loadStrategies();
  }, []);

  const loadStrategies = async () => {
    try {
      setLoading(true);
      const response = await strategiesAPI.getByStyle('at');
      setStrategies(response.data.strategies || []);
    } catch (error) {
      console.error('Failed to load strategies:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    navigate('/trader/strats/create');
  };

  const handleEdit = (id) => {
    navigate(`/trader/strats/edit/${id}`);
  };

  const toggleRow = (id) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedRows(newExpanded);
  };

  const filteredStrategies = strategies.filter((strategy) =>
    strategy.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Pagination
  const totalPages = Math.ceil(filteredStrategies.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const paginatedStrategies = filteredStrategies.slice(startIndex, startIndex + itemsPerPage);

  return (
    <Layout>
      <div className="my-trader-container">
        <div className="my-trader-header">
          <h2>MY TRADER</h2>
          <button className="btn btn-primary" onClick={handleCreate}>
            Create Strategy
          </button>
        </div>

        <div className="my-trader-search">
          <input
            type="text"
            placeholder="Search strategy..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="form-control"
          />
        </div>

        {loading ? (
          <div className="loading">Loading...</div>
        ) : (
          <>
            <div className="strategies-table">
              <table className="table">
                <thead>
                  <tr>
                    <th style={{ width: '20%' }}>Actions</th>
                    <th style={{ width: '80%' }}>Strategy</th>
                  </tr>
                </thead>
                <tbody>
                  {paginatedStrategies.length === 0 ? (
                    <tr>
                      <td colSpan="2" className="empty-state">
                        No strategies found
                      </td>
                    </tr>
                  ) : (
                    paginatedStrategies.map((strategy) => {
                      const isExpanded = expandedRows.has(strategy.id);
                      return (
                        <React.Fragment key={strategy.id}>
                          <tr>
                            <td>
                              <div className="action-buttons">
                                <button
                                  className="btn-action btn-expand"
                                  onClick={() => toggleRow(strategy.id)}
                                  title={isExpanded ? 'Collapse' : 'Expand'}
                                >
                                  {isExpanded ? '▼' : '▶'}
                                </button>
                                <button
                                  className="btn-action btn-edit"
                                  onClick={() => handleEdit(strategy.id)}
                                  title="Edit"
                                >
                                  <i className="material-icons" style={{ fontSize: '16px' }}>edit</i>
                                </button>
                                <button
                                  className="btn-action btn-remove"
                                  onClick={() => {
                                    if (window.confirm('Are you sure you want to delete this strategy?')) {
                                      // Handle delete here if needed
                                      console.log('Delete strategy:', strategy.id);
                                    }
                                  }}
                                  title="Delete"
                                >
                                  <i className="material-icons" style={{ fontSize: '16px' }}>delete</i>
                                </button>
                              </div>
                            </td>
                            <td>
                              <button
                                className="strategy-name"
                                onClick={() => toggleRow(strategy.id)}
                              >
                                {strategy.name}
                              </button>
                            </td>
                          </tr>
                          {isExpanded && (
                            <tr className="strategy-details-row">
                              <td colSpan="2">
                                <div className="strategy-details">
                                  <div className="strategy-details-header">
                                    <h5 className="strategy-details-title">Strategy Detail</h5>
                                  </div>
                                  <div className="strategy-details-content">
                                    <div className="details-grid">
                                      <div className="detail-item">
                                        <span className="detail-label">Strat Type:</span>
                                        <span className="detail-value">{strategy.strat_type || strategy.strategy_type || strategy.symbol || '-'}</span>
                                      </div>
                                      <div className="detail-item">
                                        <span className="detail-label">Days to Expiry:</span>
                                        <span className="detail-value">{strategy.days_to_expiry || '-'}</span>
                                      </div>
                                      <div className="detail-item">
                                        <span className="detail-label">Strike Offset:</span>
                                        <span className="detail-value">{strategy.strike_offset || '-'}</span>
                                      </div>
                                      <div className="detail-item">
                                        <span className="detail-label">Position Size:</span>
                                        <span className="detail-value">{strategy.position_size || 1}</span>
                                      </div>
                                      <div className="detail-item">
                                        <span className="detail-label">Position Add:</span>
                                        <span className="detail-value">{strategy.position_add || 0}</span>
                                      </div>
                                      <div className="detail-item">
                                        <span className="detail-label">Take Profit:</span>
                                        <span className="detail-value">{strategy.take_profit || 'None'}</span>
                                      </div>
                                      <div className="detail-item">
                                        <span className="detail-label">Stop Loss:</span>
                                        <span className="detail-value">{strategy.stop_loss || 'None'}</span>
                                      </div>
                                      <div className="detail-item">
                                        <span className="detail-label">Trim:</span>
                                        <span className="detail-value">{strategy.trim || 'All'}</span>
                                      </div>
                                      <div className="detail-item">
                                        <span className="detail-label">TPSL Unit:</span>
                                        <span className="detail-value">{strategy.tpsl_units || 'Tick'}</span>
                                      </div>
                                      <div className="detail-item">
                                        <span className="detail-label">Directional Strategy:</span>
                                        <span className="detail-value">{strategy.directional_strategy || 'No'}</span>
                                      </div>
                                    </div>
                                    <div className="logs-section">
                                      <h6 className="logs-title">Logs</h6>
                                      <div className="no-logs">No Logs available.</div>
                                    </div>
                                  </div>
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
            {totalPages > 0 && (
              <div className="pagination-container">
                <nav aria-label="pagination">
                  <ul className="pagination">
                    <li className={`page-item ${currentPage === 1 ? 'disabled' : ''}`}>
                      <button
                        className="page-link"
                        onClick={() => setCurrentPage(1)}
                        disabled={currentPage === 1}
                        aria-label="First"
                      >
                        <span aria-hidden="true">«</span>
                        <span className="sr-only">First</span>
                      </button>
                    </li>
                    <li className={`page-item ${currentPage === 1 ? 'disabled' : ''}`}>
                      <button
                        className="page-link"
                        onClick={() => setCurrentPage((prev) => Math.max(1, prev - 1))}
                        disabled={currentPage === 1}
                        aria-label="Previous"
                      >
                        <span aria-hidden="true">‹</span>
                        <span className="sr-only">Previous</span>
                      </button>
                    </li>
                    {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                      <li key={page} className={`page-item ${currentPage === page ? 'active' : ''}`}>
                        <button
                          className="page-link"
                          onClick={() => setCurrentPage(page)}
                        >
                          {page}
                        </button>
                      </li>
                    ))}
                    <li className={`page-item ${currentPage === totalPages ? 'disabled' : ''}`}>
                      <button
                        className="page-link"
                        onClick={() => setCurrentPage((prev) => Math.min(totalPages, prev + 1))}
                        disabled={currentPage === totalPages}
                        aria-label="Next"
                      >
                        <span aria-hidden="true">›</span>
                        <span className="sr-only">Next</span>
                      </button>
                    </li>
                    <li className={`page-item ${currentPage === totalPages ? 'disabled' : ''}`}>
                      <button
                        className="page-link"
                        onClick={() => setCurrentPage(totalPages)}
                        disabled={currentPage === totalPages}
                        aria-label="Last"
                      >
                        <span aria-hidden="true">»</span>
                        <span className="sr-only">Last</span>
                      </button>
                    </li>
                  </ul>
                </nav>
              </div>
            )}
          </>
        )}
      </div>
    </Layout>
  );
};

export default MyTrader;

