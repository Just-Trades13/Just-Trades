# Add MD Token Button to Account Management

## Instructions to Add "Fetch MD Token" Button

Since `account_management.html` is protected, add this functionality manually:

### Step 1: Add Button in Account Actions

In the account card HTML (around line 1612-1619), add a new button after the "Test" button:

```html
<div class="account-actions">
    <button class="btn-test" onclick="testAccountConnection(${account.id})">
        <i class="fas fa-plug"></i> Test
    </button>
    <button class="btn-md-token" onclick="fetchMdToken(${account.id})" title="Fetch MD Access Token for WebSocket">
        <i class="fas fa-wifi"></i> Fetch MD Token
    </button>
    <button class="btn-delete" onclick="deleteAccount(${account.id})">
        <i class="fas fa-trash"></i>
    </button>
</div>
```

### Step 2: Add JavaScript Function

Add this function after `testAccountConnection` (around line 1643):

```javascript
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
    const originalText = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Fetching...';
    
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
        button.disabled = false;
        button.innerHTML = originalText;
        
        if (data.success) {
            alert('✅ MD Access Token fetched and stored successfully!\n\nWebSocket connections will now work properly for real-time position tracking.');
            // Optionally reload accounts to show updated status
            // loadAccounts();
        } else {
            alert('❌ Failed to fetch MD Token:\n' + data.error + (data.details ? '\n\nDetails: ' + data.details : ''));
        }
    })
    .catch(error => {
        button.disabled = false;
        button.innerHTML = originalText;
        alert('Error fetching MD Token: ' + error.message);
    });
}
```

### Step 3: Add CSS Style (Optional)

Add this CSS for the button styling:

```css
.btn-md-token {
    background: linear-gradient(135deg, rgba(45, 212, 191, 0.2), rgba(25, 184, 255, 0.2));
    border: 1px solid rgba(45, 212, 191, 0.3);
    color: #2dd4bf;
    padding: 8px 16px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 0.875rem;
    transition: all 0.2s;
}

.btn-md-token:hover {
    background: linear-gradient(135deg, rgba(45, 212, 191, 0.3), rgba(25, 184, 255, 0.3));
    border-color: rgba(45, 212, 191, 0.5);
    transform: translateY(-1px);
}

.btn-md-token:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}
```

## Alternative: Quick Implementation Script

If you want to add this automatically, you can run this script (but account_management.html is protected, so manual addition is required):

```bash
# This would add the functionality, but file is protected
# You'll need to manually add the code above
```

