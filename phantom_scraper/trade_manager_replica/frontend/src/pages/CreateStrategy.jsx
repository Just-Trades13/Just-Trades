/**
 * Create/Edit Strategy Page
 */

import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { strategiesAPI, tradesAPI } from '../services/api';
import Layout from '../components/Layout';
import './CreateStrategy.css';

const CreateStrategy = () => {
  const { id } = useParams();
  const isEdit = !!id;
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    strat_type: 'Stock',
    directional_strategy: '',
    position_size: 1,
    position_add: 1,
    take_profit: null,
    stop_loss: null,
    tpsl_units: 'Ticks',
    symbol: '',
    recording_enabled: true,
    demo_account_id: null,
    active: true,
  });
  const [tickers, setTickers] = useState([]);
  const [timeframes] = useState([]);

  useEffect(() => {
    if (isEdit && id) {
      loadStrategy();
    }
    loadTickersAndTimeframes();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]); // Only re-run when id changes

  const loadStrategy = async () => {
    try {
      // Load strategy data
    } catch (error) {
      console.error('Failed to load strategy:', error);
    }
  };

  const loadTickersAndTimeframes = async () => {
    try {
      const [tickersRes, timeframesRes] = await Promise.all([
        tradesAPI.getTickers(),
        tradesAPI.getTimeframes(),
      ]);
      setTickers(tickersRes.data.tickers || []);
      setTimeframes(timeframesRes.data.timeframes || []);
    } catch (error) {
      console.error('Failed to load tickers/timeframes:', error);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      // Transform form data to match API structure
      const apiData = {
        Strat_Name: formData.name,
        Strat_Type: formData.strat_type || 'Stock',
        Days2Expo: 0,
        Strike_Offset: 0,
        Stoploss: formData.stop_loss || 0,
        Position_Size: formData.position_size || 1,
        Position_Add: formData.position_add || 1,
        TakeProfit: formData.take_profit ? [formData.take_profit] : [0],
        Trim: [0],
        TradeTrim: 0,
        TPSL_Units: formData.tpsl_units || 'Ticks',
        DirStrat: formData.directional_strategy || '',
        Description: '',
        Discord_Channel: '',
        AlgoDriven: false,
        Private: false,
        Enabled: formData.active !== false,
        SubTicker: 'ALL',
        PremiumFilter: 0,
        SubTimeFrame: 'ALL',
        Accounts: { '1': { 'TM': ['', '', ''] } },
        TimeFilter: {
          start1: null,
          stop1: null,
          start2: null,
          stop2: null
        },
        SLTP_Data: {
          avgdn: 0,
          avgdnAmnt: 1,
          avgdnType: 'Ticks',
          SL_Type: 'Fixed',
          SL_Units: formData.tpsl_units || 'Ticks',
          Trim_Units: 'Contracts'
        },
        Recorder: formData.recording_enabled !== false,
        Manual: false,
        Delay_Add: 1,
        Maxcons: 0,
        Linked_Strat: '',
        Alternate_Name: '',
        Inverse: false,
        IgnoreAlgoSpecs: false,
        Leverage: 1
      };

      if (isEdit) {
        // For edit, use update endpoint with id
        await strategiesAPI.update({ id: parseInt(id), ...apiData });
      } else {
        await strategiesAPI.create(apiData);
      }
      navigate('/recorders');
    } catch (error) {
      console.error('Failed to save strategy:', error);
      alert(error.response?.data?.error || 'Failed to save strategy');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <div className="create-strategy-container">
        <h2>{isEdit ? 'EDIT STRATEGY' : 'CREATE STRATEGY'}</h2>
        <form onSubmit={handleSubmit} className="strategy-form">
          <div className="form-section">
            <h3>BASIC INFORMATION</h3>
            <div className="form-group">
              <label>
                Strategy Name
                <span className="required">*</span>
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
                placeholder="Enter strategy name"
              />
            </div>
            <div className="form-group">
              <label>Strategy Type</label>
              <select
                value={formData.strat_type}
                onChange={(e) => setFormData({ ...formData, strat_type: e.target.value })}
              >
                <option value="Stock">Stock</option>
              </select>
            </div>
            <div className="form-group">
              <label>Symbol</label>
              <select
                value={formData.symbol}
                onChange={(e) => setFormData({ ...formData, symbol: e.target.value })}
              >
                <option value="">Select Symbol</option>
                {tickers.map((ticker) => (
                  <option key={ticker} value={ticker}>
                    {ticker}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="form-section">
            <h3>POSITION SETTINGS</h3>
            <div className="form-group">
              <label>Initial Position Size</label>
              <input
                type="number"
                min="1"
                value={formData.position_size}
                onChange={(e) => setFormData({ ...formData, position_size: parseInt(e.target.value) || 1 })}
              />
            </div>
            <div className="form-group">
              <label>Add Position Size</label>
              <input
                type="number"
                min="1"
                value={formData.position_add}
                onChange={(e) => setFormData({ ...formData, position_add: parseInt(e.target.value) || 1 })}
              />
            </div>
          </div>

          <div className="form-section">
            <h3>STOP LOSS / TAKE PROFIT</h3>
            <div className="form-group">
              <label>Take Profit</label>
              <input
                type="number"
                step="0.01"
                value={formData.take_profit || ''}
                onChange={(e) => setFormData({ ...formData, take_profit: e.target.value ? parseFloat(e.target.value) : null })}
                placeholder="Enter take profit value"
              />
            </div>
            <div className="form-group">
              <label>Stop Loss</label>
              <input
                type="number"
                step="0.01"
                value={formData.stop_loss || ''}
                onChange={(e) => setFormData({ ...formData, stop_loss: e.target.value ? parseFloat(e.target.value) : null })}
                placeholder="Enter stop loss value"
              />
            </div>
            <div className="form-group">
              <label>TP/SL Unit</label>
              <select
                value={formData.tpsl_units}
                onChange={(e) => setFormData({ ...formData, tpsl_units: e.target.value })}
              >
                <option value="Ticks">Ticks</option>
                <option value="Percent">Percent</option>
                <option value="Dollars">Dollars</option>
              </select>
            </div>
          </div>

          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => navigate('/recorders')}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Saving...' : isEdit ? 'Update Strategy' : 'Create Strategy'}
            </button>
          </div>
        </form>
      </div>
    </Layout>
  );
};

export default CreateStrategy;

