/**
 * Settings Page
 */

import { useState, useEffect } from 'react';
import { profilesAPI } from '../services/api';
import Layout from '../components/Layout';
import './Settings.css';

const Settings = () => {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [formData, setFormData] = useState({
    username: '',
    newPassword: '',
    confirmPassword: '',
    push_notifications_enabled: false,
    discord_dms_enabled: false,
  });
  const [passwordStrength, setPasswordStrength] = useState(0);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  useEffect(() => {
    loadProfile();
  }, []);

  const loadProfile = async () => {
    try {
      setLoading(true);
      const response = await profilesAPI.getDetails();
      setProfile(response.data);
      setFormData({
        username: response.data.username || '',
        push_notifications_enabled: response.data.push_notifications_enabled || false,
        discord_dms_enabled: response.data.discord_dms_enabled || false,
      });
    } catch (error) {
      console.error('Failed to load profile:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDiscordConnect = async () => {
    try {
      window.location.href = '/api/discord/oauth/connect/';
    } catch (error) {
      console.error('Failed to connect Discord:', error);
    }
  };

  const handleTogglePush = async () => {
    try {
      await profilesAPI.togglePushNotification();
      setFormData({ ...formData, push_notifications_enabled: !formData.push_notifications_enabled });
    } catch (error) {
      console.error('Failed to toggle push notifications:', error);
    }
  };

  const handleToggleDiscord = async () => {
    try {
      await profilesAPI.toggleDiscordDM();
      setFormData({ ...formData, discord_dms_enabled: !formData.discord_dms_enabled });
    } catch (error) {
      console.error('Failed to toggle Discord DMs:', error);
    }
  };

  const handleSignOut = async () => {
    try {
      // TODO: Implement sign out API call
      window.location.href = '/login';
    } catch (error) {
      console.error('Failed to sign out:', error);
    }
  };

  const handleChangeUsername = async () => {
    if (!formData.username) return;
    try {
      await profilesAPI.updateUsername(formData.username);
      alert('Username updated successfully');
    } catch (error) {
      console.error('Failed to update username:', error);
      alert('Failed to update username');
    }
  };

  const handleChangePassword = async () => {
    if (formData.newPassword !== formData.confirmPassword) {
      alert('Passwords do not match');
      return;
    }
    if (formData.newPassword.length < 8) {
      alert('Password must be at least 8 characters');
      return;
    }
    try {
      // TODO: Implement change password API call
      alert('Password changed successfully');
      setFormData({ ...formData, newPassword: '', confirmPassword: '' });
      setPasswordStrength(0);
    } catch (error) {
      console.error('Failed to change password:', error);
      alert('Failed to change password');
    }
  };

  const calculatePasswordStrength = (password) => {
    let strength = 0;
    if (password.length >= 8) strength += 25;
    if (password.match(/[a-z]/)) strength += 25;
    if (password.match(/[A-Z]/)) strength += 25;
    if (password.match(/[0-9]/)) strength += 25;
    return Math.min(strength, 100);
  };

  useEffect(() => {
    if (formData.newPassword) {
      const strength = calculatePasswordStrength(formData.newPassword);
      setPasswordStrength(strength);
    } else {
      setPasswordStrength(0);
    }
  }, [formData.newPassword]);

  const getPasswordStrengthClass = () => {
    if (passwordStrength < 50) return 'bg-danger';
    if (passwordStrength < 75) return 'bg-warning';
    return 'bg-success';
  };

  return (
    <Layout>
      <div className="settings-container">
        {loading ? (
          <div className="loading">Loading...</div>
        ) : (
          <div className="settings-content">
            {/* Notification Settings */}
            <div className="row">
              <div className="col-12 col-md-6">
                <div className="card">
                  <div className="card-body">
                    <h4 className="card-title">Push Notifications</h4>
                    <button
                      type="button"
                      className={`btn ${formData.push_notifications_enabled ? 'btn-danger' : 'btn-primary'}`}
                      onClick={handleTogglePush}
                    >
                      {formData.push_notifications_enabled ? 'Disable Push Notifications' : 'Enable Push Notifications'}
                    </button>
                  </div>
                </div>
              </div>
              <div className="col-12 col-md-6">
                <div className="card">
                  <div className="card-body">
                    <h4 className="card-title">Discord DMs</h4>
                    <button
                      type="button"
                      className={`btn ${formData.discord_dms_enabled ? 'btn-danger' : 'btn-primary'}`}
                      onClick={handleToggleDiscord}
                    >
                      {formData.discord_dms_enabled ? 'Disable Discord DMs' : 'Enable Discord DMs'}
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Discord Integration & Sign Out */}
            <div className="row">
              <div className="col-6">
                <div className="card">
                  <div className="card-body">
                    <div className="discord-login">
                      {profile?.discord_user_id ? (
                        <a href="#" className="discord-link" onClick={(e) => { e.preventDefault(); }}>
                          <img
                            src="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHZpZXdCb3g9IjAgMCAyMCAyMCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTE2Ljk0MjYgNC4yOTQ5M0MxNS4zNDU0IDMuNTQ0OTMgMTMuNzQ4MiAzLjAwNDkzIDEyLjA1MSAyLjY2NDkzTDEyIDIuNjU0OTNWMTcuMzQ1QzE0LjA0NTUgMTcuMDA1IDE2LjA0NTUgMTYuMzQ1IDE3Ljk0MjYgMTUuNTk1QzE3Ljk0MjYgMTUuNTk1IDE3Ljk0MjYgMTUuNTk1IDE3Ljk0MjYgMTUuNTk1VjQuMjk0OTNaIiBmaWxsPSIjNTg2NUYyIi8+CjxwYXRoIGQ9Ik0zLjA1NzQxIDQuMjk0OTNDNC42NTQ2MSAzLjU0NDkzIDYuMjUxODEgMy4wMDQ5MyA3Ljk0OTE5IDIuNjY0OTNMNy45OTk5OSAyLjY1NDkzVjE3LjM0NUM1Ljk1NDQ1IDE3LjAwNSA0LjA1NDQ1IDE2LjM0NSAyLjA1NzQxIDE1LjU5NUMxLjA1NzQxIDE1LjU5NSAxLjA1NzQxIDE1LjU5NSAxLjA1NzQxIDE1LjU5NVY0LjI5NDkzWiIgZmlsbD0iIzU4NjVGMiIvPgo8L3N2Zz4K"
                            alt="Discord"
                            style={{ width: '20px', marginRight: '10px' }}
                          />
                          Discord Linked
                        </a>
                      ) : (
                        <a href="#" className="discord-link" onClick={(e) => { e.preventDefault(); handleDiscordConnect(); }}>
                          <img
                            src="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHZpZXdCb3g9IjAgMCAyMCAyMCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTE2Ljk0MjYgNC4yOTQ5M0MxNS4zNDU0IDMuNTQ0OTMgMTMuNzQ4MiAzLjAwNDkzIDEyLjA1MSAyLjY2NDkzTDEyIDIuNjU0OTNWMTcuMzQ1QzE0LjA0NTUgMTcuMDA1IDE2LjA0NTUgMTYuMzQ1IDE3Ljk0MjYgMTUuNTk1QzE3Ljk0MjYgMTUuNTk1IDE3Ljk0MjYgMTUuNTk1IDE3Ljk0MjYgMTUuNTk1VjQuMjk0OTNaIiBmaWxsPSIjNTg2NUYyIi8+CjxwYXRoIGQ9Ik0zLjA1NzQxIDQuMjk0OTNDNC42NTQ2MSAzLjU0NDkzIDYuMjUxODEgMy4wMDQ5MyA3Ljk0OTE5IDIuNjY0OTNMNy45OTk5OSAyLjY1NDkzVjE3LjM0NUM1Ljk1NDQ1IDE3LjAwNSA0LjA1NDQ1IDE2LjM0NSAyLjA1NzQxIDE1LjU5NUMxLjA1NzQxIDE1LjU5NSAxLjA1NzQxIDE1LjU5NSAxLjA1NzQxIDE1LjU5NVY0LjI5NDkzWiIgZmlsbD0iIzU4NjVGMiIvPgo8L3N2Zz4K"
                            alt="Discord"
                            style={{ width: '20px', marginRight: '10px' }}
                          />
                          Link Discord
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              </div>
              <div className="col-6">
                <div className="card">
                  <div className="card-body">
                    <a href="#" className="sign-out-link" onClick={(e) => { e.preventDefault(); handleSignOut(); }}>
                      Sign Out
                    </a>
                  </div>
                </div>
              </div>
            </div>

            {/* Username Change */}
            <div className="row align-items-center mt-4">
              <div className="col-sm-12 col-md-4 col-lg-3">
                <div className="form-group">
                  <label htmlFor="username" className="form-label">Change Your Username</label>
                  <input
                    name="username"
                    id="username"
                    placeholder="Enter new username"
                    type="text"
                    className="form-control"
                    value={formData.username}
                    onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                    style={{ width: '90%' }}
                  />
                </div>
              </div>
              <div className="mt-4 mt-md-3 col-sm-12 col-md-2">
                <button
                  type="button"
                  className="btn btn-info"
                  onClick={handleChangeUsername}
                  style={{ width: '80%' }}
                >
                  Update
                </button>
              </div>
            </div>

            {/* Password Change */}
            <div className="row align-items-center mt-4">
              <div className="col-sm-12 col-md-4 col-lg-3">
                <div className="form-group">
                  <label htmlFor="newPassword">New Password</label>
                  <div className="position-relative">
                    <input
                      id="newPassword"
                      placeholder="New password"
                      type={showNewPassword ? 'text' : 'password'}
                      className="form-control"
                      value={formData.newPassword}
                      onChange={(e) => setFormData({ ...formData, newPassword: e.target.value })}
                    />
                    <span
                      className="password-toggle"
                      onClick={() => setShowNewPassword(!showNewPassword)}
                    >
                      {showNewPassword ? '🙈' : '👁️'}
                    </span>
                  </div>
                  <div className="progress mt-2" style={{ height: '5px' }}>
                    <div
                      className={`progress-bar ${getPasswordStrengthClass()}`}
                      role="progressbar"
                      style={{ width: `${passwordStrength}%` }}
                    />
                  </div>
                </div>
              </div>
              <div className="col-sm-12 col-md-4 col-lg-3">
                <div className="form-group">
                  <label htmlFor="confirmPassword">Confirm Password</label>
                  <div className="position-relative">
                    <input
                      id="confirmPassword"
                      placeholder="Confirm new password"
                      type={showConfirmPassword ? 'text' : 'password'}
                      className="form-control"
                      value={formData.confirmPassword}
                      onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
                    />
                    <span
                      className="password-toggle"
                      onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    >
                      {showConfirmPassword ? '🙈' : '👁️'}
                    </span>
                  </div>
                </div>
              </div>
              <div className="mt-4 mt-md-3 col-sm-12 col-md-2">
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={handleChangePassword}
                  style={{ width: '80%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                >
                  Change Password
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default Settings;
