import os
import sys
import time
import logging
import json
from datetime import datetime
from threading import Thread

# Simple imports - no fancy characters

try:
from flask import Flask, jsonify
import requests
IMPORTS_OK = True
except ImportError:
print(“Installing dependencies…”)
os.system(“pip install flask requests”)
try:
from flask import Flask, jsonify
import requests
IMPORTS_OK = True
except:
IMPORTS_OK = False

# Setup logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(**name**)

# Flask app

app = Flask(**name**)

# Global state

bot_running = False
trades = []
current_position = None
total_pnl = 0.0
current_price = 45000.0

class KrakenAPI:
def **init**(self):
self.last_price = 45000.0

```
def get_price(self):
    if not IMPORTS_OK:
        # Simulate price if imports failed
        import random
        change = random.uniform(-100, 100)
        self.last_price = max(30000, self.last_price + change)
        return self.last_price
        
    try:
        url = "https://api.kraken.com/0/public/Ticker?pair=XBTUSD"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get('result') and data['result'].get('XXBTZUSD'):
            price = float(data['result']['XXBTZUSD']['c'][0])
            self.last_price = price
            return price
        else:
            return self.last_price
            
    except Exception as e:
        logger.error(f"Price fetch error: {e}")
        # Return last known price with small random change
        import random
        change = random.uniform(-50, 50)
        self.last_price = max(30000, self.last_price + change)
        return self.last_price
```

class TradingStrategy:
def **init**(self):
self.prices = []

```
def add_price(self, price):
    self.prices.append(price)
    if len(self.prices) > 50:
        self.prices.pop(0)

def should_buy(self):
    if len(self.prices) < 20:
        return False, "Not enough data"
        
    current = self.prices[-1]
    sma20 = sum(self.prices[-20:]) / 20
    
    if current > sma20:
        return True, f"Price ${current:.0f} > SMA ${sma20:.0f}"
    return False, "No buy signal"

def should_sell(self):
    if len(self.prices) < 10:
        return False, "Not enough data"
        
    # Simple: sell if price dropped 2% from recent high
    recent_high = max(self.prices[-10:])
    current = self.prices[-1]
    
    if current < recent_high * 0.98:
        return True, "Price down 2% from recent high"
    return False, "Hold position"
```

# Initialize

api = KrakenAPI()
strategy = TradingStrategy()

def trading_loop():
global bot_running, current_position, trades, total_pnl, current_price

```
logger.info("Trading started")

while bot_running:
    try:
        # Get price
        current_price = api.get_price()
        strategy.add_price(current_price)
        
        logger.info(f"BTC: ${current_price:.2f}")
        
        if not current_position:
            should_buy, reason = strategy.should_buy()
            if should_buy:
                logger.info(f"BUY: {reason}")
                current_position = {
                    'type': 'LONG',
                    'entry_price': current_price,
                    'entry_time': datetime.now(),
                    'quantity': 0.001
                }
                
        else:
            should_sell, reason = strategy.should_sell()
            if should_sell:
                logger.info(f"SELL: {reason}")
                
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
                current_position = None
                
                logger.info(f"Trade completed: ${pnl:.2f}")
        
        time.sleep(60)  # Wait 1 minute
        
    except Exception as e:
        logger.error(f"Trading error: {e}")
        time.sleep(30)
```

@app.route(’/’)
def home():
return ‘’’<!DOCTYPE html>

<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kraken Trading Bot</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            background: #1a1a2e; 
            color: white; 
            padding: 20px; 
            margin: 0;
        }
        .container { max-width: 800px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 30px; }
        .header h1 { color: #00d4aa; margin-bottom: 10px; }
        .card { 
            background: #2d2d2d; 
            padding: 20px; 
            margin: 15px 0; 
            border-radius: 10px; 
            border: 1px solid #444;
        }
        .status { 
            padding: 8px 16px; 
            border-radius: 20px; 
            display: inline-block; 
            font-weight: bold; 
            margin: 10px 0;
        }
        .running { background: #28a745; }
        .stopped { background: #dc3545; }
        .btn { 
            background: #007bff; 
            color: white; 
            border: none; 
            padding: 10px 20px; 
            border-radius: 5px; 
            cursor: pointer; 
            margin: 5px;
            font-size: 14px;
        }
        .btn:hover { background: #0056b3; }
        .btn-danger { background: #dc3545; }
        .btn-danger:hover { background: #c82333; }
        .price { font-size: 24px; color: #ffd700; font-weight: bold; }
        .profit { color: #28a745; }
        .loss { color: #dc3545; }
        .metric { 
            display: flex; 
            justify-content: space-between; 
            margin: 10px 0; 
            padding: 10px 0; 
            border-bottom: 1px solid #444;
        }
        .metric:last-child { border-bottom: none; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 8px; text-align: left; border-bottom: 1px solid #444; }
        th { background: #333; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Kraken Trading Bot</h1>
            <p>Railway Cloud Deployment</p>
        </div>

```
    <div class="card">
        <h2>Bot Status</h2>
        <div id="status" class="status stopped">Stopped</div>
        <div class="price" id="price">$0.00</div>
        <br>
        <button class="btn" onclick="startBot()">Start Bot</button>
        <button class="btn btn-danger" onclick="stopBot()">Stop Bot</button>
        <button class="btn" onclick="refresh()">Refresh</button>
    </div>
    
    <div class="card">
        <h2>Performance</h2>
        <div id="performance">Loading...</div>
    </div>
    
    <div class="card">
        <h2>Current Position</h2>
        <div id="position">No position</div>
    </div>
    
    <div class="card">
        <h2>Recent Trades</h2>
        <div id="trades">No trades yet</div>
    </div>
</div>

<script>
    function refresh() {
        fetch('/api/status')
            .then(r => r.json())
            .then(data => {
                // Update status
                const status = document.getElementById('status');
                if (data.bot_running) {
                    status.textContent = 'Running';
                    status.className = 'status running';
                } else {
                    status.textContent = 'Stopped';
                    status.className = 'status stopped';
                }
                
                // Update price
                document.getElementById('price').textContent = '$' + (data.current_price || 0).toLocaleString();
                
                // Update performance
                document.getElementById('performance').innerHTML = 
                    '<div class="metric"><span>Total Trades:</span><span>' + (data.total_trades || 0) + '</span></div>' +
                    '<div class="metric"><span>Total P&L:</span><span class="' + (data.total_pnl >= 0 ? 'profit' : 'loss') + '">$' + (data.total_pnl || 0).toFixed(2) + '</span></div>';
                
                // Update position
                if (data.current_position) {
                    const pos = data.current_position;
                    document.getElementById('position').innerHTML = 
                        '<div class="metric"><span>Type:</span><span>' + pos.type + '</span></div>' +
                        '<div class="metric"><span>Entry Price:</span><span>$' + pos.entry_price.toFixed(2) + '</span></div>' +
                        '<div class="metric"><span>Quantity:</span><span>' + pos.quantity + '</span></div>';
                } else {
                    document.getElementById('position').innerHTML = 'No position';
                }
                
                // Update trades
                if (data.trades && data.trades.length > 0) {
                    let html = '<table><tr><th>Date</th><th>Entry</th><th>Exit</th><th>P&L</th></tr>';
                    data.trades.slice(-5).reverse().forEach(trade => {
                        const date = new Date(trade.entry_time).toLocaleDateString();
                        const pnlClass = trade.pnl > 0 ? 'profit' : 'loss';
                        html += '<tr><td>' + date + '</td><td>$' + trade.entry_price.toFixed(0) + '</td><td>$' + trade.exit_price.toFixed(0) + '</td><td class="' + pnlClass + '">$' + trade.pnl.toFixed(2) + '</td></tr>';
                    });
                    html += '</table>';
                    document.getElementById('trades').innerHTML = html;
                } else {
                    document.getElementById('trades').innerHTML = 'No trades yet';
                }
            })
            .catch(e => {
                console.error('Error:', e);
                document.getElementById('status').textContent = 'Error';
            });
    }
    
    function startBot() {
        fetch('/api/start', { method: 'POST' })
            .then(r => r.json())
            .then(data => {
                alert(data.message);
                refresh();
            });
    }
    
    function stopBot() {
        fetch('/api/stop', { method: 'POST' })
            .then(r => r.json())
            .then(data => {
                alert(data.message);
                refresh();
            });
    }
    
    // Auto refresh
    refresh();
    setInterval(refresh, 30000);
</script>
```

</body>
</html>'''

@app.route(’/api/status’)
def status():
return jsonify({
‘bot_running’: bot_running,
‘current_price’: current_price,
‘current_position’: current_position,
‘trades’: trades[-10:],
‘total_trades’: len(trades),
‘total_pnl’: round(total_pnl, 2),
‘timestamp’: datetime.now().isoformat()
})

@app.route(’/api/start’, methods=[‘POST’])
def start():
global bot_running

```
if bot_running:
    return jsonify({'message': 'Bot already running'})

bot_running = True
thread = Thread(target=trading_loop, daemon=True)
thread.start()

return jsonify({'message': 'Bot started successfully!'})
```

@app.route(’/api/stop’, methods=[‘POST’])
def stop():
global bot_running
bot_running = False
return jsonify({‘message’: ‘Bot stopped’})

@app.route(’/health’)
def health():
return jsonify({‘status’: ‘ok’})

if **name** == ‘**main**’:
port = int(os.environ.get(‘PORT’, 8000))

```
print("Starting Kraken Trading Bot")
print(f"Port: {port}")
print(f"Imports OK: {IMPORTS_OK}")

app.run(host='0.0.0.0', port=port, debug=False)
```