// API base URL - using relative path since API is served from same server
const API_BASE_URL = '';  // Using relative path since API is served from same server

// DOM Elements
const settingsDrawer = document.getElementById('settings-drawer');
const settingsOverlay = document.getElementById('settings-overlay');
const settingsBtn = document.getElementById('settings-btn');
const closeSettingsBtn = document.getElementById('close-settings-btn');
const saveConfigBtn = document.getElementById('save-config-btn');
const targetSpreadInput = document.getElementById('target-spread');
const orderSizeInput = document.getElementById('order-size');
const maxInventoryInput = document.getElementById('max-inventory');
const configToast = document.getElementById('config-toast');
const toastMessage = document.getElementById('toast-message');

// Toggle settings drawer
function toggleSettingsDrawer() {
    settingsDrawer.classList.toggle('open');
    settingsOverlay.classList.toggle('show');
    
    // Load current configuration when opening
    if (settingsDrawer.classList.contains('open')) {
        loadCurrentConfig();
    }
}

// Close settings drawer
function closeSettingsDrawer() {
    settingsDrawer.classList.remove('open');
    settingsOverlay.classList.remove('show');
}

// Load current configuration from API
async function loadCurrentConfig() {
    try {
        const response = await fetch(`${API_BASE_URL}/config`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const configs = await response.json();

        // Map config values to form fields
        configs.forEach(config => {
            switch(config.param_name) {
                case 'target_spread':
                    // Convert decimal to basis points (multiply by 10000)
                    targetSpreadInput.value = (parseFloat(config.param_value) * 10000).toFixed(2);
                    break;
                case 'max_order_size':
                    orderSizeInput.value = parseFloat(config.param_value);
                    break;
                case 'max_exposure':
                    maxInventoryInput.value = parseFloat(config.param_value);
                    break;
            }
        });
    } catch (error) {
        console.error('Error loading configuration:', error);
        showToast('Error loading configuration', 'bg-danger');
    }
}

// Save configuration to API
async function saveConfiguration() {
    const targetSpread = parseFloat(targetSpreadInput.value);
    const orderSize = parseFloat(orderSizeInput.value);
    const maxInventory = parseFloat(maxInventoryInput.value);

    // Validate inputs
    if (isNaN(targetSpread) || isNaN(orderSize) || isNaN(maxInventory)) {
        showToast('Please fill in all fields with valid numbers', 'bg-danger');
        return;
    }

    // Prepare configuration updates
    const configUpdates = [
        {
            param_name: 'target_spread',
            param_value: (targetSpread / 10000).toString(), // Convert basis points back to decimal
            description: 'Target spread for market making (in decimal)'
        },
        {
            param_name: 'max_order_size',
            param_value: orderSize.toString(),
            description: 'Maximum order size in USD'
        },
        {
            param_name: 'max_exposure',
            param_value: maxInventory.toString(),
            description: 'Maximum exposure per market in USD'
        }
    ];

    try {
        // Send updates to API one by one using PATCH method
        for (const config of configUpdates) {
            const response = await fetch(`${API_BASE_URL}/config`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(config)
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            if (!result.success) {
                throw new Error(result.message || 'Failed to update configuration');
            }
        }

        showToast('Configuration updated successfully!', 'bg-success');
        closeSettingsDrawer();
    } catch (error) {
        console.error('Error saving configuration:', error);
        showToast('Error saving configuration: ' + error.message, 'bg-danger');
    }
}

// Show toast notification
function showToast(message, className = 'bg-success') {
    toastMessage.textContent = message;
    configToast.className = `toast ${className}`;
    
    // Create Bootstrap toast instance and show it
    const bsToast = new bootstrap.Toast(configToast, { delay: 5000 });
    bsToast.show();
}

// Event Listeners
settingsBtn.addEventListener('click', toggleSettingsDrawer);
closeSettingsBtn.addEventListener('click', closeSettingsDrawer);
settingsOverlay.addEventListener('click', closeSettingsDrawer);

saveConfigBtn.addEventListener('click', saveConfiguration);

// Allow closing drawer with Escape key
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape' && settingsDrawer.classList.contains('open')) {
        closeSettingsDrawer();
    }
});

// Load initial data when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Load initial stats
    loadStats();
    loadOrders();
    loadSpreads();
    
    // Set up refresh button
    document.getElementById('refresh-btn').addEventListener('click', function() {
        loadStats();
        loadOrders();
        loadSpreads();
    });
    
    // Set up pause/resume button
    document.getElementById('pause-resume-btn').addEventListener('click', togglePauseResume);
    
    // Set up panic sell button
    document.getElementById('panic-sell-btn').addEventListener('click', triggerPanicSell);
});

// Load stats from API
async function loadStats() {
    try {
        const response = await fetch(`${API_BASE_URL}/stats`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const stats = await response.json();
        
        document.getElementById('pnl-value').textContent = `$${stats.pnl.toFixed(2)}`;
        document.getElementById('exposure-value').textContent = `$${stats.open_exposure.toFixed(2)}`;
        
        // Calculate win rate percentage
        const winRate = (stats.win_loss_ratio / (1 + stats.win_loss_ratio)) * 100;
        document.getElementById('win-rate-value').textContent = `${winRate.toFixed(1)}%`;
        
        document.getElementById('total-trades-value').textContent = stats.total_trades;
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// Load live orders from API
async function loadOrders() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/orders/live`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const orders = await response.json();
        
        const tbody = document.getElementById('orders-table-body');
        tbody.innerHTML = '';
        
        orders.forEach(order => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${order.order_id}</td>
                <td>${order.market_id}</td>
                <td><span class="badge bg-${order.side.toLowerCase() === 'buy' ? 'success' : 'danger'}">${order.side.toUpperCase()}</span></td>
                <td>$${parseFloat(order.price).toFixed(4)}</td>
                <td>${parseFloat(order.size).toFixed(4)}</td>
                <td><span class="badge bg-${getStatusClass(order.status)}">${order.status.replace('_', ' ').toUpperCase()}</span></td>
                <td>
                    <button class="btn btn-sm btn-outline-danger" onclick="cancelOrder('${order.order_id}')">
                        Cancel
                    </button>
                </td>
            `;
            tbody.appendChild(row);
        });
    } catch (error) {
        console.error('Error loading orders:', error);
    }
}

// Helper function to get status badge class
function getStatusClass(status) {
    switch(status) {
        case 'open':
            return 'primary';
        case 'filled':
            return 'success';
        case 'cancelled':
            return 'secondary';
        case 'partially_filled':
            return 'warning';
        default:
            return 'secondary';
    }
}

// Cancel an order
async function cancelOrder(orderId) {
    if (!confirm(`Are you sure you want to cancel order ${orderId}?`)) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/orders/${orderId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        if (result.success) {
            showToast(`Order ${orderId} cancelled successfully`, 'bg-success');
            loadOrders(); // Refresh orders list
        } else {
            throw new Error(result.message);
        }
    } catch (error) {
        console.error('Error cancelling order:', error);
        showToast(`Error cancelling order: ${error.message}`, 'bg-danger');
    }
}

// Load market spreads from API
async function loadSpreads() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/market/spread`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const spreads = await response.json();
        
        const tbody = document.getElementById('spreads-table-body');
        tbody.innerHTML = '';
        
        spreads.forEach(spread => {
            // Calculate spread percentage
            const spreadPercent = ((spread.ask_price - spread.bid_price) / spread.fair_price) * 100;
            
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${spread.market_id}</td>
                <td>$${parseFloat(spread.bid_price).toFixed(4)}</td>
                <td>$${parseFloat(spread.ask_price).toFixed(4)}</td>
                <td>$${parseFloat(spread.fair_price).toFixed(4)}</td>
                <td>$${parseFloat(spread.spread_width).toFixed(4)}</td>
                <td>${spreadPercent.toFixed(2)}%</td>
            `;
            tbody.appendChild(row);
        });
    } catch (error) {
        console.error('Error loading spreads:', error);
    }
}

// Toggle bot pause/resume
async function togglePauseResume() {
    const currentState = document.getElementById('pause-resume-text').textContent;
    const action = currentState === 'Pause' ? 'pause' : 'resume';
    
    try {
        const response = await fetch(`${API_BASE_URL}/control`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ action: action })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        if (result.success) {
            // Update button text and icon
            if (action === 'pause') {
                document.getElementById('pause-resume-text').textContent = 'Resume';
                document.querySelector('#pause-resume-btn i').className = 'fas fa-play';
            } else {
                document.getElementById('pause-resume-text').textContent = 'Pause';
                document.querySelector('#pause-resume-btn i').className = 'fas fa-pause';
            }
            
            showToast(`Bot ${action}d successfully`, 'bg-success');
        } else {
            throw new Error(result.message);
        }
    } catch (error) {
        console.error(`Error ${action}ing bot:`, error);
        showToast(`Error ${action}ing bot: ${error.message}`, 'bg-danger');
    }
}

// Trigger panic sell
async function triggerPanicSell() {
    if (!confirm('Are you sure you want to trigger a panic sell? This will liquidate all positions.')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/control`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ action: 'panic_sell' })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        if (result.success) {
            showToast('Panic sell initiated successfully', 'bg-warning');
        } else {
            throw new Error(result.message);
        }
    } catch (error) {
        console.error('Error triggering panic sell:', error);
        showToast(`Error triggering panic sell: ${error.message}`, 'bg-danger');
    }
}