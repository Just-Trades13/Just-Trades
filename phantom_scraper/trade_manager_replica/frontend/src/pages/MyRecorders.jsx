/**
 * My Recorders Page
 * Manage demo account strategies (for recording/backtesting)
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { strategiesAPI, recorderAPI } from '../services/api';
import Layout from '../components/Layout';
import './MyRecorders.css';

const MyRecorders = () => {
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
      const response = await strategiesAPI.getAll();
      setStrategies(response.data.strategies || []);
    } catch (error) {
      console.error('Failed to load strategies:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    navigate('/recorders/create');
  };

  const handleEdit = (id) => {
    navigate(`/recorders/edit/${id}`);
  };

  const handleDelete = async (id) => {
    if (window.confirm('Are you sure you want to delete this strategy?')) {
      try {
        await strategiesAPI.delete(id);
        loadStrategies();
      } catch (error) {
        console.error('Failed to delete strategy:', error);
      }
    }
  };

  const handleStartRecording = async (strategyId) => {
    try {
      await recorderAPI.start(strategyId);
      loadStrategies();
    } catch (error) {
      console.error('Failed to start recording:', error);
    }
  };

  const handleStopRecording = async (strategyId) => {
    try {
      await recorderAPI.stop(strategyId);
      loadStrategies();
    } catch (error) {
      console.error('Failed to stop recording:', error);
    }
  };

  const filteredStrategies = strategies.filter((strategy) =>
    strategy.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const toggleRow = (id) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedRows(newExpanded);
  };

  // Pagination
  const totalPages = Math.ceil(filteredStrategies.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const paginatedStrategies = filteredStrategies.slice(startIndex, startIndex + itemsPerPage);

  return (
    <Layout>
      <div className="recorders-container">
        <div className="recorders-header">
          <h2>MY RECORDERS</h2>
          <button className="btn btn-primary" onClick={handleCreate}>
            Create Strategy
          </button>
        </div>

        <div className="recorders-search">
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
                    <th style={{ width: '20%' }}>ACTIONS</th>
                    <th style={{ width: '80%' }}>STRATEGY</th>
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
                    paginatedStrategies.map((strategy) => (
                      <tr key={strategy.id}>
                        <td>
                          <div className="action-buttons">
                            <button
                              className="btn-action btn-edit"
                              onClick={() => handleEdit(strategy.id)}
                              title="Edit"
                            >
                              <span className="tim-icons">edit</span>
                            </button>
                            <button
                              className="btn-action btn-refresh"
                              onClick={() => loadStrategies()}
                              title="Refresh"
                            >
                              <span className="tim-icons">refresh</span>
                            </button>
                            <button
                              className="btn-action btn-remove"
                              onClick={() => handleDelete(strategy.id)}
                              title="Delete"
                            >
                              <span className="tim-icons">close</span>
                            </button>
                          </div>
                        </td>
                        <td>
                          <a
                            href="#"
                            className="strategy-name-link"
                            onClick={(e) => {
                              e.preventDefault();
                              handleEdit(strategy.id);
                            }}
                          >
                            {strategy.name}
                          </a>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            {totalPages > 0 && (
              <div className="pagination-container">
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
              </div>
            )}
          </>
        )}
      </div>
    </Layout>
  );
};

export default MyRecorders;

