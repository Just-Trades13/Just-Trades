/**
 * SIMPLE TEST APP - Minimal version to test React rendering
 */
import React from 'react';

function AppSimple() {
  return (
    <div style={{ padding: '50px', color: 'white', fontFamily: 'Arial', background: '#1e1e2f', minHeight: '100vh' }}>
      <h1>✅ React is Working!</h1>
      <p>If you see this, React is rendering correctly.</p>
      <div style={{ background: '#2a2a3d', padding: '20px', borderRadius: '5px', marginTop: '20px' }}>
        <h2>Test Results:</h2>
        <ul>
          <li>✅ React imports work</li>
          <li>✅ React renders</li>
          <li>✅ JSX works</li>
        </ul>
      </div>
      <button 
        onClick={() => alert('React event handlers work!')}
        style={{ padding: '10px 20px', marginTop: '20px', background: '#007bff', color: 'white', border: 'none', borderRadius: '5px', cursor: 'pointer' }}
      >
        Test Button
      </button>
    </div>
  );
}

export default AppSimple;

