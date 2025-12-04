/**
 * Trade Manager WebSocket Inspector
 * 
 * Instructions:
 * 1. Open Trade Manager in your browser
 * 2. Open DevTools (F12)
 * 3. Go to Console tab
 * 4. Paste this entire script
 * 5. Press Enter
 * 6. Use the app and watch the console output
 * 
 * This will show you:
 * - WebSocket connection URL
 * - All WebSocket messages
 * - Message types and data
 * - Connection/disconnection events
 */

(function() {
    console.log('🔍 Trade Manager WebSocket Inspector Started');
    console.log('='.repeat(60));
    
    // Store original WebSocket
    const OriginalWebSocket = window.WebSocket;
    const OriginalSocketIO = window.io;
    
    // Track connections
    const connections = [];
    
    // Intercept WebSocket
    window.WebSocket = function(url, protocols) {
        console.log('📡 WebSocket Connection Detected!');
        console.log('   URL:', url);
        console.log('   Protocols:', protocols);
        console.log('');
        
        const ws = new OriginalWebSocket(url, protocols);
        connections.push({ url, ws, messages: [] });
        
        ws.addEventListener('open', () => {
            console.log('✅ WebSocket Connected:', url);
            console.log('');
        });
        
        ws.addEventListener('message', (event) => {
            console.log('📨 WebSocket Message Received:');
            console.log('   URL:', url);
            try {
                const data = JSON.parse(event.data);
                console.log('   Type:', data.type || 'unknown');
                console.log('   Data:', JSON.stringify(data, null, 2));
            } catch (e) {
                console.log('   Raw Data:', event.data);
            }
            console.log('');
        });
        
        ws.addEventListener('error', (error) => {
            console.error('❌ WebSocket Error:', error);
            console.log('');
        });
        
        ws.addEventListener('close', () => {
            console.log('🔌 WebSocket Closed:', url);
            console.log('');
        });
        
        return ws;
    };
    
    // Intercept Socket.IO if it exists
    if (OriginalSocketIO) {
        window.io = function(url, options) {
            console.log('📡 Socket.IO Connection Detected!');
            console.log('   URL:', url || 'default');
            console.log('   Options:', options);
            console.log('');
            
            const socket = OriginalSocketIO(url, options);
            
            socket.on('connect', () => {
                console.log('✅ Socket.IO Connected');
                console.log('');
            });
            
            socket.onAny((eventName, ...args) => {
                console.log('📨 Socket.IO Event:', eventName);
                console.log('   Data:', JSON.stringify(args, null, 2));
                console.log('');
            });
            
            socket.on('disconnect', () => {
                console.log('🔌 Socket.IO Disconnected');
                console.log('');
            });
            
            return socket;
        };
    }
    
    // Monitor network tab
    console.log('💡 Tips:');
    console.log('   1. Check DevTools → Network → WS filter for WebSocket connections');
    console.log('   2. Use the app normally - all WebSocket activity will be logged');
    console.log('   3. Look for message patterns and types');
    console.log('   4. Note the WebSocket URL (e.g., wss://trademanagergroup.com:5000/ws)');
    console.log('');
    console.log('📊 Summary will be available in window.websocketConnections');
    console.log('='.repeat(60));
    
    // Store connections globally
    window.websocketConnections = connections;
    
    // Return summary function
    window.getWebSocketSummary = function() {
        console.log('📊 WebSocket Connection Summary:');
        console.log('='.repeat(60));
        connections.forEach((conn, index) => {
            console.log(`Connection ${index + 1}:`);
            console.log('   URL:', conn.url);
            console.log('   Messages:', conn.messages.length);
            console.log('');
        });
    };
    
    return 'WebSocket Inspector Active - Use the app and watch console output';
})();

