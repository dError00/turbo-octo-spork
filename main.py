# ===== FILE 4: main.py (SIMPLIFIED & WORKING VERSION) =====

import os
import time
import logging
import hashlib
import hmac
import base64
import urllib.parse
from datetime import datetime
from threading import Thread
from flask import Flask, jsonify, render_template_string

try:
    import requests
except ImportError:
    print("Installing requests...")
    os.system("pip install requests")
    import requests

try:
    import pandas as pd
    import numpy as np
except ImportError:
    print("Installing pandas and numpy...")
    os.system("pip install pandas numpy")
    import pandas as pd
    import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)

# Global variables
bot_running = False
trades = []
current_position = None
total_pnl = 0.0

class KrakenAPI:
    def __init__(self, api_key=None, api_secret=None, sandbox=True):
        self.api_key = api_key or os.getenv('KRAKEN_API_KEY', '')
        self.api_secret = api_secret or os.getenv('KRAKEN_API_SECRET', '')
        self.sandbox = sandbox
        self.base_url = "https://api.kraken.com"
        
    def get_ticker(self, pair="XBTUSD"):
        """Get current price"""
        try:
            url = f"{self.base_url}/0/public/Ticker"
            response = requests.get(url, params={'pair': pair}, timeout=10)
            data = response.json()
            
            if data.get('error'):
                logger.error(f"Kraken error: {data['error']}")
                return None
                
            result = data.get('result', {})
            pair_data = result.get(pair, {})
            
            if pair_data:
                return {
                    'price': float(pair_data['c'][0]),  # Last trade price
                    'bid': float(pair_data['b'][0]),
                    'ask': float(pair_data['a'][0])
                }
            return None
            
        except Exception as e:
            logger.error(f"Error getting ticker: {e}")
            return None
    
    def place_order(self, side, volume, pair="XBTUSD"):
        """Place a market order"""
        if self.sandbox:
            logger.info(f"SANDBOX: Would place {side} order for {volume} {pair}")
            return {'txid': [f'sandbox_{int(time.time())}']}
        
        # Real order placement would go here
        logger.info(f"LIVE TRADING DISABLED - Would place {side} order")
        return {'txid': [f'demo_{int(time.time())}']}

# Simple strategy
class SimpleStrategy:
    def __init__(self):
        self.prices = []
        self.rsi_period = 14
        self.last_signal_time = 0
        
    def add_price(self, price):
        self.prices.append(price)
        if len(self.prices) > 100:  # Keep only last 100 prices
            self.prices.pop(0)
    
    def calculate_rsi(self):
        if len(self.prices) < self.rsi_period + 1:
            return 50.0
            
        deltas = [self.prices[i] - self.prices[i-1] for i in range(1, len(self.prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains[-self.rsi_period:]) / self.rsi_period
        avg_loss = sum(losses[-self.rsi_period:]) / self.rsi_period
        
        if avg_loss == 0:
            return 100.0
            
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def should_buy(self):
        if len(self.prices) < 20:
            return False, "Not enough data"
            
        current_price = self.prices[-1]
        sma_20 = sum(self.prices[-20:]) / 20
        rsi = self.calculate_rsi()
        
        # Simple strategy: Buy when price > SMA and RSI < 70
        if current_price > sma_20 and rsi < 70 and rsi > 30:
            return True, f"Price ${current_price:.2f} > SMA ${sma_20:.2f}, RSI: {rsi:.1f}"
        
        return False, f"No buy signal. Price: ${current_price:.2f}, SMA: ${sma_20:.2f}, RSI: {rsi:.1f}"
    
    def should_sell(self):
        if len(self.prices) < 20:
            return False, "Not enough data"
            
        rsi = self.calculate_rsi()
        
        # Simple exit: Sell when RSI > 70
        if rsi > 70:
            return True, f"RSI overbought: {rsi:.1f}"
            
        return False, f"Hold position. RSI: {rsi:.1f}"

# Trading bot
api = KrakenAPI(sandbox=True)
strategy = SimpleStrategy()

def trading_loop():
    """Main trading loop"""
    global bot_running, current_position, trades, total_pnl
    
    while bot_running:
        try:
            # Get current price
            ticker = api.get_ticker()
            if not ticker:
                logger.error("Failed to get ticker data")
                time.sleep(30)
                continue
                
            current_price = ticker['price']
            strategy.add_price(current_price)
            
            logger.info(f"Current BTC price: ${current_price:.2f}")
            
            # Check for signals
            if not current_position:
                # Look for buy signal
                should_buy, reason = strategy.should_buy()
                if should_buy:
                    logger.info(f"BUY SIGNAL: {reason}")
                    
                    # Place buy order
                    result = api.place_order('buy', 0.01)  # 0.01 BTC
                    if result and 'txid' in result:
                        current_position = {
                            'type': 'LONG',
                            'entry_price': current_price,
                            'entry_time': datetime.now(),
                            'quantity': 0.01,
                            'order_id': result['txid'][0]
                        }
                        logger.info(f"Position opened: {current_position}")
                        
            else:
                # Look for sell signal
                should_sell, reason = strategy.should_sell()
                if should_sell:
                    logger.info(f"SELL SIGNAL: {reason}")
                    
                    # Close position
                    result = api.place_order('sell', current_position['quantity'])
                    if result and 'txid' in result:
                        # Calculate PnL
                        pnl = (current_price - current_position['entry_price']) * current_position['quantity']
                        
                        # Record trade
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
                        
                        logger.info(f"Trade closed: PnL ${pnl:.2f}, Total PnL: ${total_pnl:.2f}")
                        current_position = None
            
            time.sleep(60)  # Wait 1 minute before next check
            
        except Exception as e:
            logger.error(f"Error in trading loop: {e}")
            time.sleep(30)

# Web routes
@app.route('/')
def dashboard():
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚄 Kraken Trading Bot</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; 
            background: linear-gradient(135deg, #1a1a2e, #16213e); 
            color: #fff; 
            padding: 20px; 
            min-height: 100vh;
        }
        .header { text-align: center; margin-bottom: 30px; }
        .header h1 { 
            background: linear-gradient(45deg, #00d4aa, #007991);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .card { 
            background: rgba(45, 45, 45, 0.95); 
            border-radius: 16px; 
            padding: 24px; 
            margin-bottom: 20px; 
            border: 1px solid rgba(0, 212, 170, 0.2);
        }
        .status-indicator { 
            width: 12px; 
            height: 12px; 
            border-radius: 50%; 
            display: inline-block; 
            margin-right: 8px; 
            animation: pulse 2s infinite;
        }
        .status-running { background: #00ff88; }
        .status-stopped { background: #ff4444; }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        .btn { 
            background: linear-gradient(45deg, #00d4aa, #007991);
            color: white; 
            border: none; 
            padding: 12px 24px; 
            border-radius: 8px; 
            font-size: 16px; 
            cursor: pointer; 
            margin: 5px;
            transition: all 0.3s;
        }
        .btn:hover { 
            transform: translateY(-2px);
            box-shadow: 0 4px 20px rgba(0, 212, 170, 0.4);
        }
        .btn-danger { 
            background: linear-gradient(45deg, #ff4444, #cc3333);
        }
        .metric { 
            display: flex; 
            justify-content: space-between; 
            margin: 12px 0; 
            padding: 12px 0; 
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .metric:last-child { border-bottom: none; }
        .profit { color: #00ff88; font-weight: 600; }
        .loss { color: #ff4444; font-weight: 600; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🚄 Kraken Trading Bot</h1>
        <p>Railway Deployment - WORKING!</p>
    </div>
    
    <div class="card">
        <h2>🤖 Bot Status</h2>
        <p id="bot-status">
            <span class="status-indicator status-stopped"></span>
            Loading...
        </p>
        <div style="margin-top: 20px;">
            <button class="btn" onclick="startBot()">▶️ Start Bot</button>
            <button class="btn btn-danger" onclick="stopBot()">⏹️ Stop Bot</button>
            <button class="btn" onclick="updateDashboard()" style="background: rgba(255,255,255,0.1);">🔄 Refresh</button>
        </div>
    </div>
    
    <div class="card">
        <h2>📊 Performance</h2>
        <div id="performance">Loading...</div>
    </div>
    
    <div class="card">
        <h2>📈 Current Position</h2>
        <div id="position">Loading...</div>
    </div>
    
    <div class="card">
        <h2>📊 Recent Trades</h2>
        <div id="trades">Loading...</div>
    </div>
    
    <script>
        function updateDashboard() {
            fetch('/api/status')
                .then(response => response.json())
                .then(data => {
                    const isRunning = data.bot_running;
                    document.getElementById('bot-status').innerHTML = `
                        <span class="status-indicator ${isRunning ? 'status-running' : 'status-stopped'}"></span>
                        ${isRunning ? '🟢 Running' : '🔴 Stopped'}
                    `;
                    
                    document.getElementById('performance').innerHTML = `
                        <div class="metric"><span>Total Trades:</span><span><strong>${data.total_trades}</strong></span></div>
                        <div class="metric"><span>Total PnL:</span><span class="${data.total_pnl >= 0 ? 'profit' : 'loss'}"><strong>$${data.total_pnl.toFixed(2)}</strong></span></div>
                        <div class="metric"><span>Current Price:</span><span><strong>$${data.current_price || 'N/A'}</strong></span></div>
                    `;
                    
                    if (data.current_position) {
                        document.getElementById('position').innerHTML = `
                            <div class="metric"><span>Type:</span><span><strong>📈 ${data.current_position.type}</strong></span></div>
                            <div class="metric"><span>Entry Price:</span><span><strong>$${data.current_position.entry_price.toFixed(2)}</strong></span></div>
                            <div class="metric"><span>Quantity:</span><span><strong>${data.current_position.quantity}</strong></span></div>
                        `;
                    } else {
                        document.getElementById('position').innerHTML = '<p>📭 No open position</p>';
                    }
                    
                    if (data.trades && data.trades.length > 0) {
                        let html = '<div style="overflow-x: auto;"><table style="width: 100%; border-collapse: collapse;">';
                        html += '<tr style="background: rgba(0,212,170,0.1);"><th style="padding: 8px;">Date</th><th style="padding: 8px;">Type</th><th style="padding: 8px;">PnL</th></tr>';
                        data.trades.slice(-5).reverse().forEach(trade => {
                            const pnlClass = trade.pnl > 0 ? 'profit' : 'loss';
                            html += `<tr><td style="padding: 8px;">${new Date(trade.entry_time).toLocaleDateString()}</td><td style="padding: 8px;">📈 ${trade.type}</td><td style="padding: 8px;" class="${pnlClass}">$${trade.pnl.toFixed(2)}</td></tr>`;
                        });
                        html += '</table></div>';
                        document.getElementById('trades').innerHTML = html;
                    } else {
                        document.getElementById('trades').innerHTML = '<p>📭 No trades yet</p>';
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    document.getElementById('bot-status').innerHTML = '<span class="status-indicator status-stopped"></span>❌ Error';
                });
        }
        
        function startBot() {
            fetch('/api/start', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    alert(data.message);
                    updateDashboard();
                });
        }
        
        function stopBot() {
            if (confirm('Stop the bot?')) {
                fetch('/api/stop', { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        alert(data.message);
                        updateDashboard();
                    });
            }
        }
        
        // Auto-update every 30 seconds
        updateDashboard();
        setInterval(updateDashboard, 30000);
    </script>
</body>
</html>
    ''')

@app.route('/api/status')
def get_status():
    ticker = api.get_ticker()
    current_price = ticker['price'] if ticker else None
    
    return jsonify({
        'bot_running': bot_running,
        'current_price': current_price,
        'current_position': current_position,
        'trades': trades[-10:],  # Last 10 trades
        'total_trades': len(trades),
        'total_pnl': total_pnl,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/start', methods=['POST'])
def start_bot():
    global bot_running
    
    if bot_running:
        return jsonify({'message': 'Bot is already running'})
    
    bot_running = True
    
    # Start trading loop in background thread
    thread = Thread(target=trading_loop, daemon=True)
    thread.start()
    
    logger.info("Bot started successfully")
    return jsonify({'message': 'Bot started successfully!'})

@app.route('/api/stop', methods=['POST'])
def stop_bot():
    global bot_running
    
    bot_running = False
    logger.info("Bot stopped")
    return jsonify({'message': 'Bot stopped successfully!'})

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    logger.info(f"Starting bot on port {port}")
    
    # Auto-start bot if configured
    if os.getenv('AUTO_START', 'false').lower() == 'true':
        logger.info("Auto-starting bot...")
        bot_running = True
        thread = Thread(target=trading_loop, daemon=True)
        thread.start()
    
    app.run(host='0.0.0.0', port=port, debug=False)
