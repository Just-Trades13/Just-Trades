/**
 * Login Page
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import './Login.css';

const Login = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      // TODO: Get reCAPTCHA token from reCAPTCHA widget
      // For now, use placeholder token
      const captchaToken = 'test-captcha-token-placeholder';
      
      const result = await login(username, password, captchaToken);
      if (result.success) {
        // Small delay to ensure state is updated before navigation
        setTimeout(() => {
          navigate('/dashboard');
        }, 100);
      } else {
        setError(result.error || 'Login failed');
        setLoading(false);
      }
    } catch {
      setError('An error occurred. Please try again.');
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-modal-overlay">
        <div className="login-modal-content">
          <div className="login-form-container">
            <h2>Sign In</h2>
            <form onSubmit={handleSubmit}>
              {error && <div className="login-disabled-reason">{error}</div>}
              <div className="login-form-group">
                <label htmlFor="username">User Name or Email</label>
                <input
                  type="text"
                  id="username"
                  value={username.toUpperCase()}
                  onChange={(e) => setUsername(e.target.value.toUpperCase())}
                  required
                  autoFocus
                />
              </div>
              <div className="login-form-group">
                <label htmlFor="password">Password</label>
                <div className="login-password-container">
                  <input
                    type="password"
                    id="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                </div>
              </div>
              <div className="login-form-group remember-me">
                <label className="login-checkbox-label">
                  <input type="checkbox" id="rememberMe" />
                  <span className="login-checkmark"></span>
                  Remember Me
                </label>
              </div>
              <div className="login-reg-but-container">
                {!username.trim() && (
                  <div className="login-disabled-reason">❌ User Name or Email is required</div>
                )}
                {!password && (
                  <div className="login-disabled-reason">❌ Password is required</div>
                )}
                <button
                  type="submit"
                  className="login-login-btn"
                  disabled={loading || !username.trim() || !password}
                  style={{
                    opacity: (loading || !username.trim() || !password) ? 0.5 : 1,
                    cursor: (loading || !username.trim() || !password) ? 'not-allowed' : 'pointer'
                  }}
                >
                  {loading ? 'Logging in...' : 'Login'}
                </button>
              </div>
            </form>
            <div className="login-forgot-password">
              <button className="login-forgot-password-link">
                Forgot password?
              </button>
            </div>
            <div className="login-signup-prompt">
              <p>Don't have an account? <button className="login-signup-link">Sign Up</button></p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;
