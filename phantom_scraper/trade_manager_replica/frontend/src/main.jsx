// ALL IMPORTS MUST BE AT TOP - ES6 module requirement
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

console.log('🚀 main.jsx loaded');

// Global error handler
window.addEventListener('error', (event) => {
  console.error('❌ Global error:', event.error);
  const root = document.getElementById('root');
  if (root) {
    root.innerHTML = `
      <div style="padding: 20px; color: white; font-family: Arial; background: #1e1e2f; min-height: 100vh;">
        <h1 style="color: red;">❌ JavaScript Error</h1>
        <p><strong>${event.error?.message || 'Unknown error'}</strong></p>
        <pre style="background: #2a2a3d; padding: 10px; overflow: auto; color: #fff; max-height: 400px;">${event.error?.stack || 'No stack trace'}</pre>
        <button onclick="location.reload()" style="padding: 10px 20px; margin-top: 20px; background: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer;">Reload Page</button>
      </div>
    `;
  }
});

// React error boundary
window.addEventListener('unhandledrejection', (event) => {
  console.error('❌ Unhandled promise rejection:', event.reason);
  const root = document.getElementById('root');
  if (root) {
    root.innerHTML = `
      <div style="padding: 20px; color: white; font-family: Arial; background: #1e1e2f; min-height: 100vh;">
        <h1 style="color: red;">❌ Promise Rejection</h1>
        <p><strong>${event.reason?.message || String(event.reason)}</strong></p>
        <button onclick="location.reload()" style="padding: 10px 20px; margin-top: 20px; background: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer;">Reload Page</button>
      </div>
    `;
  }
});

// Initialize and render the app
try {
  const rootEl = document.getElementById('root');
  if (!rootEl) {
    throw new Error('Root element not found!');
  }
  
  const root = createRoot(rootEl);
  root.render(
    <StrictMode>
      <App />
    </StrictMode>
  );
  console.log('✅ App rendered successfully');
} catch (error) {
  console.error('❌ React app failed to mount:', error);
  const rootEl = document.getElementById('root');
  if (rootEl) {
    rootEl.innerHTML = `
      <div style="padding: 20px; color: white; font-family: Arial; background: #1e1e2f; min-height: 100vh;">
        <h1 style="color: red;">❌ Error Loading App</h1>
        <p><strong>${error.message}</strong></p>
        <pre style="background: #2a2a3d; padding: 10px; overflow: auto; color: #fff; max-height: 400px;">${error.stack}</pre>
        <button onclick="location.reload()" style="padding: 10px 20px; margin-top: 20px; background: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer;">Reload Page</button>
      </div>
    `;
  }
}
