/**
 * Main App Component
 * Sets up routing and authentication
 */

import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { wsService } from './services/websocket';

// Pages
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import MyRecorders from './pages/MyRecorders';
import CreateStrategy from './pages/CreateStrategy';
import AccountManagement from './pages/AccountManagement';
import MyTrader from './pages/MyTrader';
import ControlCenter from './pages/ControlCenter';
import Settings from './pages/Settings';

// Protected Route Component - BYPASSED FOR NOW
const ProtectedRoute = ({ children }) => {
  // BYPASS AUTH - Just show content
  console.log('ProtectedRoute: Bypassing auth, showing content');
  return children;
};

// App Routes
const AppRoutes = () => {
  const { authenticated } = useAuth();

  // Connect WebSocket when authenticated (only once)
  useEffect(() => {
    if (authenticated && !wsService.isConnected()) {
      wsService.connect();
    } else if (!authenticated && wsService.isConnected()) {
      wsService.disconnect();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authenticated]); // Only re-run when authenticated changes

  return (
    <Routes>
      <Route
        path="/login"
        element={<Navigate to="/dashboard" replace />}
      />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/recorders"
        element={
          <ProtectedRoute>
            <MyRecorders />
          </ProtectedRoute>
        }
      />
      <Route
        path="/recorders/create"
        element={
          <ProtectedRoute>
            <CreateStrategy />
          </ProtectedRoute>
        }
      />
      <Route
        path="/recorders/edit/:id"
        element={
          <ProtectedRoute>
            <CreateStrategy />
          </ProtectedRoute>
        }
      />
      <Route
        path="/trader/accounts"
        element={
          <ProtectedRoute>
            <AccountManagement />
          </ProtectedRoute>
        }
      />
      <Route
        path="/trader/accounts/add"
        element={
          <ProtectedRoute>
            <AccountManagement />
          </ProtectedRoute>
        }
      />
      <Route
        path="/trader/strategies"
        element={
          <ProtectedRoute>
            <MyTrader />
          </ProtectedRoute>
        }
      />
      <Route
        path="/trader/control-center"
        element={
          <ProtectedRoute>
            <ControlCenter />
          </ProtectedRoute>
        }
      />
      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            <Settings />
          </ProtectedRoute>
        }
      />
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
};

// Main App
function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
