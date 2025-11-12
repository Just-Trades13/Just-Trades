/**
 * Account Management Page
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { accountsAPI } from '../services/api';
import Layout from '../components/Layout';
import './AccountManagement.css';

const AccountManagement = () => {
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedAccounts, setSelectedAccounts] = useState(new Set());
  const navigate = useNavigate();

  useEffect(() => {
    loadAccounts();
  }, []);

  const loadAccounts = async () => {
    try {
      setLoading(true);
      const response = await accountsAPI.getAll();
      setAccounts(response.data.accounts || []);
    } catch (error) {
      console.error('Failed to load accounts:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAddAccount = () => {
    navigate('/trader/accounts/add');
  };

  const handleDelete = async (id) => {
    if (window.confirm('Are you sure you want to delete this account?')) {
      try {
        await accountsAPI.delete(id);
        loadAccounts();
      } catch (error) {
        console.error('Failed to delete account:', error);
      }
    }
  };

  const handleBulkDelete = async () => {
    if (selectedAccounts.size === 0) return;
    if (window.confirm(`Are you sure you want to delete ${selectedAccounts.size} account(s)?`)) {
      try {
        await Promise.all(Array.from(selectedAccounts).map(id => accountsAPI.delete(id)));
        setSelectedAccounts(new Set());
        loadAccounts();
      } catch (error) {
        console.error('Failed to delete accounts:', error);
      }
    }
  };

  const handleClearTrades = async () => {
    if (selectedAccounts.size === 0) return;
    if (window.confirm(`Clear trades for ${selectedAccounts.size} account(s)?`)) {
      // TODO: Implement clear trades API call
      console.log('Clear trades for:', Array.from(selectedAccounts));
    }
  };

  const toggleAccountSelection = (id) => {
    const newSelected = new Set(selectedAccounts);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedAccounts(newSelected);
  };

  const filteredAccounts = accounts.filter((account) =>
    account.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    account.username?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <Layout>
      <div className="account-management-container">
        <div className="account-header">
          <div>
            <h2>ACCOUNT MANAGEMENT</h2>
            {accounts.length > 0 && (
              <p>Account {accounts.length} Used / Unlimited</p>
            )}
          </div>
          <button className="btn btn-primary" onClick={handleAddAccount}>
            + Add Account
          </button>
        </div>

        <div className="account-actions-bar">
          <input
            type="text"
            placeholder="Search accounts..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="account-search-input"
          />
          <button
            className="btn btn-bulk-delete"
            onClick={handleBulkDelete}
            disabled={selectedAccounts.size === 0}
          >
            Bulk Delete
          </button>
          <button
            className="btn btn-bulk-clear"
            onClick={handleClearTrades}
            disabled={selectedAccounts.size === 0}
          >
            Clear Trades
          </button>
        </div>

        {loading ? (
          <div className="loading">Loading...</div>
        ) : filteredAccounts.length === 0 ? (
          <div className="empty-state">
            No accounts found
          </div>
        ) : (
          <div className="accounts-grid">
            {filteredAccounts.map((account) => (
              <div key={account.id} className="account-card">
                <div className="account-card-header">
                  <div className="account-card-title-section">
                    <input
                      type="checkbox"
                      className="account-checkbox"
                      checked={selectedAccounts.has(account.id)}
                      onChange={() => toggleAccountSelection(account.id)}
                    />
                    <h3>{account.name || account.username}</h3>
                  </div>
                  <span className={`status-badge ${account.disabled ? 'disabled' : 'active'}`}>
                    {account.disabled ? 'Disabled' : 'Active'}
                  </span>
                </div>
                <div className="account-card-body">
                  <p><strong>Platform:</strong> {account.platform || 'Tradovate'}</p>
                  <p><strong>Username:</strong> {account.username}</p>
                  <p><strong>Status:</strong> {account.status || 'N/A'}</p>
                </div>
                <div className="account-card-actions">
                  <button className="btn btn-action-primary">Edit Account Credentials</button>
                  <button className="btn btn-action-secondary">Refresh SubAccount</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Layout>
  );
};

export default AccountManagement;

