/**
 * Fetch MD Access Token functionality for Account Management
 * This enables WebSocket connections for real-time position tracking
 */

// Fetch MD Access Token for WebSocket
function fetchMdToken(accountId) {
    // Check if account has stored credentials
    fetch(`/api/accounts/${accountId}`)
        .then(response => response.json())
        .then(account => {
            if (account.username && account.password) {
                // Use stored credentials
                fetchMdTokenWithCredentials(accountId, null, null);
            } else {
                // Prompt for credentials
                const username = prompt('Enter Tradovate username/email:');
                if (!username) return;
                
                const password = prompt('Enter Tradovate password:');
                if (!password) return;
                
                fetchMdTokenWithCredentials(accountId, username, password);
            }
        })
        .catch(error => {
            console.error('Error fetching account:', error);
            // If API fails, prompt for credentials directly
            const username = prompt('Enter Tradovate username/email:');
            if (!username) return;
            
            const password = prompt('Enter Tradovate password:');
            if (!password) return;
            
            fetchMdTokenWithCredentials(accountId, username, password);
        });
}

function fetchMdTokenWithCredentials(accountId, username, password) {
    const button = event.target.closest('button');
    if (button) {
        const originalText = button.innerHTML;
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Fetching...';
        
        const resetButton = () => {
            button.disabled = false;
            button.innerHTML = originalText;
        };
        
        const payload = {};
        if (username && password) {
            payload.username = username;
            payload.password = password;
            payload.use_stored = false;
        } else {
            payload.use_stored = true;
        }
        
        fetch(`/api/accounts/${accountId}/fetch-md-token`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        })
        .then(response => response.json())
        .then(data => {
            resetButton();
            
            if (data.success) {
                alert('✅ MD Access Token fetched and stored successfully!\n\nWebSocket connections will now work properly for real-time position tracking.');
                // Optionally reload accounts to show updated status
                if (typeof loadAccounts === 'function') {
                    loadAccounts();
                }
            } else {
                alert('❌ Failed to fetch MD Token:\n' + data.error + (data.details ? '\n\nDetails: ' + data.details : ''));
            }
        })
        .catch(error => {
            resetButton();
            alert('Error fetching MD Token: ' + error.message);
        });
    } else {
        // Fallback if button not found
        const payload = {};
        if (username && password) {
            payload.username = username;
            payload.password = password;
            payload.use_stored = false;
        } else {
            payload.use_stored = true;
        }
        
        fetch(`/api/accounts/${accountId}/fetch-md-token`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('✅ MD Access Token fetched and stored successfully!\n\nWebSocket connections will now work properly for real-time position tracking.');
            } else {
                alert('❌ Failed to fetch MD Token:\n' + data.error + (data.details ? '\n\nDetails: ' + data.details : ''));
            }
        })
        .catch(error => {
            alert('Error fetching MD Token: ' + error.message);
        });
    }
}

