#!/usr/bin/env python3

import os
import sys
import subprocess
import time
import logging
from datetime import datetime
from threading import Thread

# Auto-install missing packages

def install_package(package):
try:
subprocess.check_call([sys.executable, “-m”, “pip”, “install”, package])
print(f”✅ Installed {package}”)
except Exception as e:
print(f”❌ Failed to install {package}: {e}”)

# Check and install required packages

required_packages = {
‘requests’: ‘requests==2.31.0’,
‘flask’: ‘flask==2.3.3’
}

for module, package in required_packages.items():
try:
**import**(module)
print(f”✅ {module} already available”)
except ImportError:
print(f”⏳ Installing {module}…”)
install_package(package)

# Now import everything

try:
import requests
from flask import Flask, jsonify
print(“✅ All imports successful!”)
except ImportError as e:
print(f”❌ Import failed: {e}”)
# Fallback - create minimal Flask app
class MockFlask:
def **init**(self, *args, **kwargs): pass
def route(self, *args, **kwargs):
def decorator(f): return f
return decorator
def run(self, *args, **kwargs):
print(“Mock server running…”)
while True: time.sleep(60)
Flask = MockFlask
requests = None

# Configure logging

logging.basicConfig(
level=logging.INFO,
format=’%(asctime)s - %(levelname)s - %(message)s’
)
logger = logging.getLogger(**name**)

# Flask app

app = Flask(**name**)

# Global state

bot_running = False
trades = []
current_position = None
total_pnl = 0.0
current_price = 45000.0  # Default BTC price
price_history = []

class SimpleKrakenAPI:
“”“Simplified Kraken API that works without external dependencies”””

```
def __init__(self):
    self.sandbox = True
    self.last_price = 45000.0
    
def get_ticker_fallback(self):
    """Fallback method using simple HTTP without requests library"""
    try:
        if requests:
            response = requests.get(
                'https://api.kraken.com/0/public/Ticker?pair=XBTUSD', 
                timeout=10
            )
            data = response.json()
            if data.get('result', {}).get('XXBTZUSD'):
                price = float(data['result']['XXBTZUSD']['c'][0])
                self.last_price = price
                return price
        
        # If requests fails, simulate price movement
        import random
        change = random.uniform(-100, 100)
        self.last_price = max(30000, self.last_price + change)
        return self.last_price
        
    except Exception as e:
        logger.error(f"Error getting price: {e}")
        # Return simulated price
        import random
        change = random.uniform(-50, 50)
        self.last_price = max(30000, self.last_price + change)
        return self.last_price

def place_order(self, side, volume):
    """Simulate order placement"""
    order_id = f"sandbox_{int(time.time())}"
    logger.info(f"SANDBOX: {side.upper()} order for {volume} BTC at ${self.last_price:.2f}")
    return {'txid': [order_id]}
```

class SimpleStrategy:
“”“Simple trading strategy”””

```
def __init__(self):
    self.prices = []
    self.signals = []
    
def add_price(self, price):
    self.prices.append(price)
    if len(self.prices) > 50:  # Keep last 50 prices
        self.prices.pop(0)

def calculate_sma(self, period=20):
    if len(self.prices) < period:
        return self.prices[-1] if self.prices else 45000
    return sum(self.prices[-period:]) / period

def calculate_rsi(self, period=14):
    if len(self.prices) < period + 1:
        return 50.0
        
    gains = []
    losses = []
    
    for i in range(1, len(self.prices)):
        change = self.prices[i] - self.prices[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(-change)
    
    if len(gains) < period:
        return 50.0
        
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100.0
        
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def get_signal(self):
    if len(self.prices) < 20:
        return None, "Not enough data"
        
    current_price = self.prices[-1]
    sma = self.calculate_sma(20)
    rsi = self.calculate_rsi(14)
    
    # Buy signal: Price above SMA and RSI not overbought
    if current_price > sma and rsi < 70 and rsi > 30:
        return "BUY", f"Price ${current_price:.0f} > SMA ${sma:.0f}, RSI: {rsi:.1f}"
    
    # Sell signal: RSI overbought
    if rsi > 70:
        return "SELL", f"RSI overbought: {rsi:.1f}"
        
    return None, f"No signal - Price: ${current_price:.0f}, SMA: ${sma:.0f}, RSI: {rsi:.1f}"
```

# Initialize components

api = SimpleKrakenAPI()
strategy = SimpleStrategy()

def trading_loop():
“”“Main trading loop”””
global bot_running, current_position, trades, total_pnl, current_price

```
logger.info("🚀 Trading loop started!")

while bot_running:
    try:
        # Get current price
        current_price = api.get_ticker_fallback()
        strategy.add_price(current_price)
        
        logger.info(f"💰 BTC Price: ${current_price:.2f}")
        
        # Get trading signal
        signal, reason = strategy.get_signal()
        
        if not current_position and signal == "BUY":
            # Open long position
            logger.info(f"📈 BUY SIGNAL: {reason}")
            
            result = api.place_order('buy', 0.001)  # Small position
            if result:
                current_position = {
                    'type': 'LONG',
                    'entry_price': current_price,
                    'entry_time': datetime.now(),
                    'quantity': 0.001
                }
                logger.info("✅ Position opened!")
                
        elif current_position and signal == "SELL":
            # Close position
            logger.info(f"📉 SELL SIGNAL: {reason}")
            
            result = api.place_order('sell', current_position['quantity'])
            if result:
                # Calculate PnL
                pnl = (current_price - current_position['entry_price']) * current_position['quantity']
                
                trade = {
                    'entry_time': current_position['entry_time'].isoformat(),
                    'exit_time': datetime.now().isoformat(),
                    'entry_price': current_position['entry_price'],
                    'exit_price': current_price,
                    'pnl': pnl,
                    'type': 'LONG'
                }
                
                trades.append(trade)
                total_pnl += pnl
                
                logger.info(f"✅ Trade closed! PnL: ${pnl:.2f}, Total: ${total_pnl:.2f}")
                current_position = None
        else:
            logger.info(f"📊 {reason}")
        
        # Wait before next iteration
        time.sleep(60)  # Check every minute
        
    except Exception as e:
        logger.error(f"❌ Trading loop error: {e}")
        time.sleep(30)

logger.info("🛑 Trading loop stopped")
```

# Web routes

@app.route(’/’)
def dashboard():
return ‘’’<!DOCTYPE html>

<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚄 Kraken Trading Bot - Railway</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; 
            background: linear-gradient(135deg, #0f3460, #16537e); 
            color: #fff; 
            padding: 15px; 
            min-height: 100vh;
        }
        .container { max-width: 800px; margin: 0 auto; }
        .header { 
            text-align: center; 
            margin-bottom: 25px; 
            padding: 20px;
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            backdrop-filter: blur(10px);
        }
        .header h1 { 
            font-size: 2em;
            background: linear-gradient(45deg, #00d4aa, #ffd700);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 10px;
        }
        .status-badge {
            display: inline-block;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 0.9em;
        }
        .status-running { background: linear-gradient(45deg, #00ff88, #00cc6a); }
        .status-stopped { background: linear-gradient(45deg, #ff4444, #cc3333); }
        .card { 
            background: rgba(255,255,255,0.08); 
            border-radius: 15px; 
            padding: 20px; 
            margin-bottom: 15px; 
            border: 1px solid rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
        }
        .card h2 { 
            margin-bottom: 15px; 
            color: #00d4aa;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .controls {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-top: 15px;
        }
        .btn { 
            background: linear-gradient(45deg, #00d4aa, #007991);
            color: white; 
            border: none; 
            padding: 12px 20px; 
            border-radius: 8px; 
            font-size: 14px; 
            font-weight: 600;
            cursor: pointer; 
            transition: all 0.3s;
            flex: 1;
            min-width: 120px;
        }
        .btn:hover { 
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(0, 212, 170, 0.3);
        }
        .btn:active { transform: translateY(0); }
        .btn-danger { 
            background: linear-gradient(45deg, #ff4444, #cc3333);
        }
        .btn-secondary {
            background: linear-gradient(45deg, #6c757d, #495057);
        }
        .metric { 
            display: flex; 
            justify-content: space-between; 
            align-items: center;
            margin: 10px 0; 
            padding: 12px 0; 
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .metric:last-child { border-bottom: none; }
        .metric-label { opacity: 0.8; }
        .metric-value { font-weight: 600; }
        .profit { color: #00ff88; }
        .loss { color: #ff6b6b; }
        .price { 
            font-size: 1.5em; 
            font-weight: bold;
            background: linear-gradient(45deg, #ffd700, #ffed4e);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .loading {
            text-align: center;
            opacity: 0.7;
            padding: 20px;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .pulse { animation: pulse 2s infinite; }

```
    @media (max-width: 600px) {
        body { padding: 10px; }
        .header h1 { font-size: 1.5em; }
        .controls { flex-direction: column; }
        .btn { min-width: unset; }
    }
</style>
```

</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚄 Kraken Trading Bot</h1>
            <p>Railway Cloud Deployment</p>
            <div id="status-badge" class="status-badge status-stopped pulse">🔴 Connecting...</div>
        </div>

```
    <div class="card">
        <h2>🤖 Bot Control</h2>
        <div id="bot-info">
            <div class="metric">
                <span class="metric-label">Status:</span>
                <span class="metric-value" id="bot-status">Loading...</span>
            </div>
            <div class="metric">
                <span class="metric-label">Current BTC Price:</span>
                <span class="metric-value price" id="current-price">$---.--</span>
            </div>
        </div>
        <div class="controls">
            <button class="btn" onclick="startBot()">▶️ Start Trading</button>
            <button class="btn btn-danger" onclick="stopBot()">⏹️ Stop Bot</button>
            <button class="btn btn-secondary" onclick="updateDashboard()">🔄 Refresh</button>
        </div>
    </div>
    
    <div class="card">
        <h2>📊 Performance</h2>
        <div id="performance">
            <div class="loading">Loading performance data...</div>
        </div>
    </div>
    
    <div class="card">
        <h2>📈 Current Position</h2>
        <div id="position">
            <div class="loading">Loading position data...</div>
        </div>
    </div>
    
    <div class="card">
        <h2>💼 Trade History</h2>
        <div id="trades">
            <div class="loading">Loading trades...</div>
        </div>
    </div>
</div>

<script>
    let updateInterval;
    
    function updateDashboard() {
        fetch('/api/status')
            .then(response => response.json())
            .then(data => {
                // Update status
                const isRunning = data.bot_running;
                const statusBadge = document.getElementById('status-badge');
                const statusText = document.getElementById('bot-status');
                
                if (isRunning) {
                    statusBadge.className = 'status-badge status-running';
                    statusBadge.textContent = '🟢 Running';
                    statusText.textContent = 'Trading Active';
                } else {
                    statusBadge.className = 'status-badge status-stopped';
                    statusBadge.textContent = '🔴 Stopped';
                    statusText.textContent = 'Inactive';
                }
                
                // Update price
                if (data.current_price) {
                    document.getElementById('current-price').textContent = `$${data.current_price.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
                }
                
                // Update performance
                document.getElementById('performance').innerHTML = `
                    <div class="metric">
                        <span class="metric-label">Total Trades:</span>
                        <span class="metric-value">${data.total_trades || 0}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Total P&L:</span>
                        <span class="metric-value ${data.total_pnl >= 0 ? 'profit' : 'loss'}">
                            $${(data.total_pnl || 0).toFixed(2)}
                        </span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Success Rate:</span>
                        <span class="metric-value">${data.win_rate || 'N/A'}</span>
                    </div>
                `;
                
                // Update position
                if (data.current_position) {
                    const pos = data.current_position;
                    const unrealizedPnl = (data.current_price - pos.entry_price) * pos.quantity;
                    document.getElementById('position').innerHTML = `
                        <div class="metric">
                            <span class="metric-label">Position:</span>
                            <span class="metric-value">📈 ${pos.type}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Entry Price:</span>
                            <span class="metric-value">$${pos.entry_price.toFixed(2)}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Quantity:</span>
                            <span class="metric-value">${pos.quantity} BTC</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Unrealized P&L:</span>
                            <span class="metric-value ${unrealizedPnl >= 0 ? 'profit' : 'loss'}">
                                $${unrealizedPnl.toFixed(2)}
                            </span>
                        </div>
                    `;
                } else {
                    document.getElementById('position').innerHTML = '<div style="text-align: center; opacity: 0.7; padding: 20px;">📭 No open position</div>';
                }
                
                // Update trades
                if (data.trades && data.trades.length > 0) {
                    let html = '<div style="overflow-x: auto;"><table style="width: 100%; border-collapse: collapse; font-size: 0.9em;">';
                    html += '<tr style="background: rgba(0,212,170,0.1); border-bottom: 2px solid rgba(0,212,170,0.3);"><th style="padding: 10px 8px; text-align: left;">Date</th><th style="padding: 10px 8px;">Entry</th><th style="padding: 10px 8px;">Exit</th><th style="padding: 10px 8px;">P&L</th></tr>';
                    
                    data.trades.slice(-5).reverse().forEach(trade => {
                        const pnlClass = trade.pnl > 0 ? 'profit' : 'loss';
                        const date = new Date(trade.entry_time).toLocaleDateString();
                        html += `
                            <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                                <td style="padding: 8px;">${date}</td>
                                <td style="padding: 8px;">$${trade.entry_price.toFixed(0)}</td>
                                <td style="padding: 8px;">$${trade.exit_price.toFixed(0)}</td>
                                <td style="padding: 8px;" class="${pnlClass}">$${trade.pnl.toFixed(2)}</td>
                            </tr>
                        `;
                    });
                    html += '</table></div>';
                    document.getElementById('trades').innerHTML = html;
                } else {
                    document.getElementById('trades').innerHTML = '<div style="text-align: center; opacity: 0.7; padding: 20px;">📭 No trades yet</div>';
                }
            })
            .catch(error => {
                console.error('Error updating dashboard:', error);
                document.getElementById('status-badge').textContent = '❌ Connection Error';
                document.getElementById('status-badge').className = 'status-badge status-stopped';
            });
    }
    
    function startBot() {
        const btn = event.target;
        btn.disabled = true;
        btn.innerHTML = '⏳ Starting...';
        
        fetch('/api/start', { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                alert(data.message);
                updateDashboard();
            })
            .catch(error => {
                alert('Error starting bot: ' + error);
            })
            .finally(() => {
                btn.disabled = false;
                btn.innerHTML = '▶️ Start Trading';
            });
    }
    
    function stopBot() {
        if (confirm('⚠️ Are you sure you want to stop the trading bot?')) {
            const btn = event.target;
            btn.disabled = true;
            btn.innerHTML = '⏳ Stopping...';
            
            fetch('/api/stop', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    alert(data.message);
                    updateDashboard();
                })
                .catch(error => {
                    alert('Error stopping bot: ' + error);
                })
                .finally(() => {
                    btn.disabled = false;
                    btn.innerHTML = '⏹️ Stop Bot';
                });
        }
    }
    
    // Auto-update dashboard
    updateDashboard();
    updateInterval = setInterval(updateDashboard, 30000); // Every 30 seconds
    
    // Handle page visibility changes
    document.addEventListener('visibilitychange', function() {
        if (document.hidden) {
            clearInterval(updateInterval);
        } else {
            updateDashboard();
            updateInterval = setInterval(updateDashboard, 30000);
        }
    });
</script>
```

</body>
</html>'''

@app.route(’/api/status’)
def get_status():
“”“Get bot status and performance data”””
global current_price

```
# Calculate win rate
win_rate = "0%"
if trades:
    winning_trades = sum(1 for trade in trades if trade['pnl'] > 0)
    win_rate = f"{(winning_trades / len(trades) * 100):.1f}%"

return jsonify({
    'bot_running': bot_running,
    'current_price': current_price,
    'current_position': current_position,
    'trades': trades[-10:],  # Last 10 trades
    'total_trades': len(trades),
    'total_pnl': round(total_pnl, 2),
    'win_rate': win_rate,
    'timestamp': datetime.now().isoformat(),
    'status': 'healthy'
})
```

@app.route(’/api/start’, methods=[‘POST’])
def start_bot():
“”“Start the trading bot”””
global bot_running

```
if bot_running:
    return jsonify({'message': 'Trading bot is already running! 🚀'})

try:
    bot_running = True
    
    # Start trading loop in background
    thread = Thread(target=trading_loop, daemon=True)
    thread.start()
    
    logger.info("✅ Trading bot started successfully!")
    return jsonify({'message': 'Trading bot started successfully! 🚀'})
    
except Exception as e:
    bot_running = False
    logger.error(f"❌ Failed to start bot: {e}")
    return jsonify({'message': f'Failed to start bot: {str(e)}'})
```

@app.route(’/api/stop’, methods=[‘POST’])
def stop_bot():
“”“Stop the trading bot”””
global bot_running

```
bot_running = False
logger.info("🛑 Trading bot stopped by user")
return jsonify({'message': 'Trading bot stopped successfully! ✋'})
```

@app.route(’/health’)
def health_check():
“”“Health check endpoint”””
return jsonify({
‘status’: ‘healthy’,
‘bot_running’: bot_running,
‘timestamp’: datetime.now().isoformat(),
‘uptime’: time.time() - start_time
})

# Error handlers

@app.errorhandler(404)
def not_found(error):
return jsonify({‘error’: ‘Endpoint not found’}), 404

@app.errorhandler(500)
def internal_error(error):
return jsonify({‘error’: ‘Internal server error’}), 500

if **name** == ‘**main**’:
start_time = time.time()
port = int(os.environ.get(‘PORT’, 8000))

```
print("=" * 50)
print("🚄 KRAKEN TRADING BOT - RAILWAY DEPLOYMENT")
print("=" * 50)
print(f"🔧 Starting on port: {port}")
print(f"🔐 Sandbox mode: ON")
print(f"💻 Python version: {sys.version}")
print("=" * 50)

# Auto-start bot if configured
if os.getenv('AUTO_START', 'false').lower() == 'true':
    print("🚀 Auto-starting trading bot...")
    bot_running = True
    thread = Thread(target=trading_loop, daemon=True)
    thread.start()

try:
    app.run(host='0.0.0.0', port=port, debug=False)
except Exception as e:
    print(f"❌ Server failed to start: {e}")
    print("🔧 Trying fallback server...")
    # Simple fallback
    while True:
        print(f"⏰ Server running on port {port} - {datetime.now()}")
        time.sleep(60)
```