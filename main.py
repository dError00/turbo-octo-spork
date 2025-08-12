import os
import asyncio
import logging
import json
import time
import hashlib
import hmac
import base64
import urllib.parse
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request
from threading import Thread
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from collections import deque
import websockets

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Enums and Data Classes
class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"

class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"

class PositionType(Enum):
    NONE = 0
    LONG = 1
    SHORT = -1

@dataclass
class KrakenConfig:
    api_key: str
    api_secret: str
    trading_pair: str = "XBTUSD"
    base_url: str = "https://api.kraken.com"
    websocket_url: str = "wss://ws.kraken.com"
    sandbox: bool = True

@dataclass
class Position:
    entry_time: datetime
    entry_price: float
    position_type: PositionType
    quantity: float
    order_id: str = None

# Kraken API Client
class KrakenAPI:
    def __init__(self, config: KrakenConfig):
        self.config = config
        self.session = requests.Session()
        
    def _get_kraken_signature(self, urlpath: str, data: dict, secret: str) -> str:
        postdata = urllib.parse.urlencode(data)
        encoded = (str(data['nonce']) + postdata).encode()
        message = urlpath.encode() + hashlib.sha256(encoded).digest()
        
        mac = hmac.new(base64.b64decode(secret), message, hashlib.sha512)
        sigdigest = base64.b64encode(mac.digest())
        return sigdigest.decode()
    
    def _make_request(self, endpoint: str, data: dict = None, private: bool = False) -> dict:
        url = f"{self.config.base_url}{endpoint}"
        
        if private:
            if not data:
                data = {}
            data['nonce'] = str(int(1000*time.time()))
            
            headers = {
                'API-Key': self.config.api_key,
                'API-Sign': self._get_kraken_signature(endpoint, data, self.config.api_secret)
            }
            
            response = self.session.post(url, headers=headers, data=data)
        else:
            response = self.session.get(url, params=data)
        
        try:
            result = response.json()
            if result.get('error'):
                logger.error(f"Kraken API error: {result['error']}")
                return None
            return result.get('result', {})
        except Exception as e:
            logger.error(f"Failed to parse response: {e}")
            return None
    
    def get_account_balance(self) -> dict:
        return self._make_request('/0/private/Balance', private=True)
    
    def place_order(self, order_type: OrderType, side: OrderSide, volume: float, 
                   price: float = None, pair: str = None) -> dict:
        pair = pair or self.config.trading_pair
        
        data = {
            'pair': pair,
            'type': side.value,
            'ordertype': order_type.value,
            'volume': str(volume)
        }
        
        if order_type == OrderType.LIMIT and price:
            data['price'] = str(price)
        
        if self.config.sandbox:
            logger.info(f"SANDBOX MODE: Would place {side.value} order: {data}")
            return {'txid': [f'sandbox_{int(time.time())}']}
        
        return self._make_request('/0/private/AddOrder', data, private=True)

# WebSocket Client
class KrakenWebSocket:
    def __init__(self, config: KrakenConfig, callback):
        self.config = config
        self.callback = callback
        self.websocket = None
        self.running = False
        
    async def connect(self):
        try:
            self.websocket = await websockets.connect(self.config.websocket_url)
            self.running = True
            
            subscribe_msg = {
                "event": "subscribe",
                "pair": [self.config.trading_pair],
                "subscription": {
                    "name": "ohlc",
                    "interval": 1
                }
            }
            await self.websocket.send(json.dumps(subscribe_msg))
            
            logger.info("Connected to Kraken WebSocket")
            
            async for message in self.websocket:
                if self.running:
                    await self.handle_message(message)
                else:
                    break
                    
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            self.running = False
    
    async def handle_message(self, message: str):
        try:
            data = json.loads(message)
            
            if isinstance(data, dict):
                return
            
            if len(data) >= 2 and isinstance(data[1], dict):
                if len(data[1]) > 5:  # OHLC data has multiple fields
                    await self.callback('ohlc', {
                        'pair': data[3] if len(data) > 3 else 'XBTUSD',
                        'time': float(data[1][1]),
                        'open': float(data[1][2]),
                        'high': float(data[1][3]),
                        'low': float(data[1][4]),
                        'close': float(data[1][5]),
                        'volume': float(data[1][7]) if len(data[1]) > 7 else 1.0
                    })
                    
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    async def disconnect(self):
        self.running = False
        if self.websocket:
            await self.websocket.close()

# Strategy Engine
class StrategyEngine:
    def __init__(self, 
                 rsi_period: int = 14,
                 rsi_overbought: float = 70.0,
                 rsi_oversold: float = 30.0,
                 trauma_period: int = 20,
                 lookback_period: int = 100):
        
        self.rsi_period = rsi_period
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold
        self.trauma_period = trauma_period
        self.lookback_period = lookback_period
        
        self.ohlc_data = deque(maxlen=lookback_period)
        self.last_signal = None
        self.last_signal_time = None
        
    def add_ohlc_data(self, data: dict):
        self.ohlc_data.append({
            'timestamp': datetime.fromtimestamp(data['time']),
            'open': data['open'],
            'high': data['high'],
            'low': data['low'],
            'close': data['close'],
            'volume': data['volume']
        })
    
    def calculate_rsi(self, prices: List[float], period: int = None) -> float:
        if period is None:
            period = self.rsi_period
            
        if len(prices) < period + 1:
            return 50.0
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_trauma(self, data: List[dict], period: int = None) -> float:
        if period is None:
            period = self.trauma_period
            
        if len(data) < period:
            return data[-1]['close'] if data else 0
        
        recent_data = data[-period:]
        closes = [d['close'] for d in recent_data]
        highs = [d['high'] for d in recent_data]
        lows = [d['low'] for d in recent_data]
        
        sma = np.mean(closes)
        
        true_ranges = []
        for i in range(1, len(recent_data)):
            tr1 = highs[i] - lows[i]
            tr2 = abs(highs[i] - closes[i-1])
            tr3 = abs(lows[i] - closes[i-1])
            true_ranges.append(max(tr1, tr2, tr3))
        
        if true_ranges:
            avg_tr = np.mean(true_ranges)
            trauma = sma - (avg_tr * 0.5)
        else:
            trauma = sma
        
        return trauma
    
    def detect_breakout(self, data: List[dict], lookback: int = 20) -> int:
        if len(data) < lookback:
            return 0
        
        recent_data = data[-lookback:]
        current = data[-1]
        
        highs = [d['high'] for d in recent_data[:-1]]
        lows = [d['low'] for d in recent_data[:-1]]
        volumes = [d['volume'] for d in recent_data]
        
        resistance = max(highs) if highs else current['high']
        support = min(lows) if lows else current['low']
        avg_volume = np.mean(volumes[:-1]) if len(volumes) > 1 else volumes[0]
        
        if (current['close'] > resistance and 
            current['volume'] > avg_volume * 1.2):
            return 1
        elif (current['close'] < support and 
              current['volume'] > avg_volume * 1.2):
            return -1
        
        return 0
    
    def generate_signal(self) -> Tuple[Optional[str], str]:
        if len(self.ohlc_data) < max(self.rsi_period, self.trauma_period) + 1:
            return None, "Not enough data"
        
        data_list = list(self.ohlc_data)
        current_price = data_list[-1]['close']
        
        closes = [d['close'] for d in data_list]
        rsi = self.calculate_rsi(closes)
        trauma = self.calculate_trauma(data_list)
        breakout = self.detect_breakout(data_list)
        
        signal = None
        reason = ""
        
        if current_price > trauma and breakout == 1:
            signal = "BUY"
            reason = f"Price ${current_price:.2f} > Trauma ${trauma:.2f} + Bullish breakout (RSI: {rsi:.1f})"
        elif current_price < trauma and breakout == -1:
            signal = "SELL"
            reason = f"Price ${current_price:.2f} < Trauma ${trauma:.2f} + Bearish breakout (RSI: {rsi:.1f})"
        elif self.last_signal:
            if self.last_signal == "BUY" and rsi > self.rsi_overbought:
                signal = "EXIT_LONG"
                reason = f"RSI overbought: {rsi:.1f} > {self.rsi_overbought}"
            elif self.last_signal == "SELL" and rsi < self.rsi_oversold:
                signal = "EXIT_SHORT"
                reason = f"RSI oversold: {rsi:.1f} < {self.rsi_oversold}"
        
        if signal in ["BUY", "SELL"]:
            self.last_signal = signal
            self.last_signal_time = datetime.now()
        elif signal and signal.startswith("EXIT"):
            self.last_signal = None
            self.last_signal_time = None
        
        return signal, reason

# Main Trading Bot
class KrakenTradingBot:
    def __init__(self, config: KrakenConfig, strategy_params: dict = None):
        self.config = config
        self.api = KrakenAPI(config)
        self.websocket = None
        self.strategy = StrategyEngine(**(strategy_params or {}))
        
        self.current_position: Optional[Position] = None
        self.running = False
        self.trade_size = float(os.getenv('TRADE_SIZE', 0.01))
        self.min_time_between_signals = 300
        
        self.trades = []
        self.total_pnl = 0.0
        
    async def websocket_callback(self, data_type: str, data: dict):
        try:
            if data_type == 'ohlc':
                self.strategy.add_ohlc_data(data)
                signal, reason = self.strategy.generate_signal()
                
                if signal:
                    logger.info(f"Signal generated: {signal} - {reason}")
                    await self.handle_signal(signal, reason, data['close'])
                    
        except Exception as e:
            logger.error(f"Error in websocket callback: {e}")
    
    async def handle_signal(self, signal: str, reason: str, current_price: float):
        try:
            if (self.strategy.last_signal_time and 
                (datetime.now() - self.strategy.last_signal_time).total_seconds() < self.min_time_between_signals):
                return
            
            if signal == "BUY" and not self.current_position:
                await self.open_long_position(current_price, reason)
            elif signal == "SELL" and not self.current_position:
                await self.open_short_position(current_price, reason)
            elif signal == "EXIT_LONG" and self.current_position and self.current_position.position_type == PositionType.LONG:
                await self.close_position(current_price, reason)
            elif signal == "EXIT_SHORT" and self.current_position and self.current_position.position_type == PositionType.SHORT:
                await self.close_position(current_price, reason)
                
        except Exception as e:
            logger.error(f"Error handling signal: {e}")
    
    async def open_long_position(self, price: float, reason: str):
        logger.info(f"Opening LONG position at ${price:.2f} - {reason}")
        
        result = self.api.place_order(
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            volume=self.trade_size
        )
        
        if result and 'txid' in result:
            self.current_position = Position(
                entry_time=datetime.now(),
                entry_price=price,
                position_type=PositionType.LONG,
                quantity=self.trade_size,
                order_id=result['txid'][0]
            )
            logger.info(f"Long position opened: {result['txid'][0]}")
            send_telegram_message(f"🟢 LONG opened at ${price:.2f}\n{reason}")
        else:
            logger.error("Failed to open long position")
    
    async def open_short_position(self, price: float, reason: str):
        logger.info(f"Opening SHORT position at ${price:.2f} - {reason}")
        
        result = self.api.place_order(
            order_type=OrderType.MARKET,
            side=OrderSide.SELL,
            volume=self.trade_size
        )
        
        if result and 'txid' in result:
            self.current_position = Position(
                entry_time=datetime.now(),
                entry_price=price,
                position_type=PositionType.SHORT,
                quantity=self.trade_size,
                order_id=result['txid'][0]
            )
            logger.info(f"Short position opened: {result['txid'][0]}")
            send_telegram_message(f"🔴 SHORT opened at ${price:.2f}\n{reason}")
        else:
            logger.error("Failed to open short position")
    
    async def close_position(self, price: float, reason: str):
        if not self.current_position:
            return
        
        logger.info(f"Closing {self.current_position.position_type.name} position at ${price:.2f} - {reason}")
        
        side = OrderSide.SELL if self.current_position.position_type == PositionType.LONG else OrderSide.BUY
        
        result = self.api.place_order(
            order_type=OrderType.MARKET,
            side=side,
            volume=self.current_position.quantity
        )
        
        if result and 'txid' in result:
            if self.current_position.position_type == PositionType.LONG:
                pnl = (price - self.current_position.entry_price) * self.current_position.quantity
            else:
                pnl = (self.current_position.entry_price - price) * self.current_position.quantity
            
            trade = {
                'entry_time': self.current_position.entry_time,
                'exit_time': datetime.now(),
                'entry_price': self.current_position.entry_price,
                'exit_price': price,
                'position_type': self.current_position.position_type.name,
                'quantity': self.current_position.quantity,
                'pnl': pnl,
                'reason': reason,
                'entry_order_id': self.current_position.order_id,
                'exit_order_id': result['txid'][0]
            }
            
            self.trades.append(trade)
            self.total_pnl += pnl
            
            logger.info(f"Position closed. PnL: ${pnl:.2f} | Total PnL: ${self.total_pnl:.2f}")
            send_telegram_message(f"✅ Position closed: ${pnl:+.2f}\nTotal PnL: ${self.total_pnl:+.2f}")
            self.current_position = None
        else:
            logger.error("Failed to close position")
    
    def get_performance_summary(self) -> dict:
        if not self.trades:
            return {"message": "No trades executed yet"}
        
        profitable_trades = [t for t in self.trades if t['pnl'] > 0]
        
        return {
            'total_trades': len(self.trades),
            'profitable_trades': len(profitable_trades),
            'losing_trades': len(self.trades) - len(profitable_trades),
            'win_rate': f"{(len(profitable_trades) / len(self.trades) * 100):.1f}%",
            'total_pnl': f"${self.total_pnl:.2f}",
            'average_pnl': f"${np.mean([t['pnl'] for t in self.trades]):.2f}",
            'best_trade': f"${max([t['pnl'] for t in self.trades]):.2f}",
            'worst_trade': f"${min([t['pnl'] for t in self.trades]):.2f}",
            'current_position': self.current_position.position_type.name if self.current_position else "None"
        }
    
    async def start(self):
        logger.info("Starting Kraken Trading Bot...")
        
        balance = self.api.get_account_balance()
        if balance:
            logger.info(f"Account balance: {balance}")
        
        self.websocket = KrakenWebSocket(self.config, self.websocket_callback)
        self.running = True
        
        try:
            await self.websocket.connect()
        except Exception as e:
            logger.error(f"Bot error: {e}")
        finally:
            await self.stop()
    
    async def stop(self):
        logger.info("Stopping trading bot...")
        self.running = False
        
        if self.websocket:
            await self.websocket.disconnect()

# Telegram Integration
def send_telegram_message(message):
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        return
    
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': message
        }
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")

# Flask Web App
app = Flask(__name__)
trading_bot = None
bot_thread = None

@app.route('/')
def dashboard():
    return '''<!DOCTYPE html>
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
        .header { 
            text-align: center; 
            margin-bottom: 30px; 
            background: linear-gradient(45deg, #00d4aa, #007991);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .card { 
            background: rgba(45, 45, 45, 0.95); 
            border-radius: 16px; 
            padding: 24px; 
            margin-bottom: 20px; 
            border: 1px solid rgba(0, 212, 170, 0.2);
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
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
            font-weight: 600;
        }
        .btn:hover { 
            transform: translateY(-2px);
            box-shadow: 0 4px 20px rgba(0, 212, 170, 0.4);
        }
        .btn-danger { 
            background: linear-gradient(45deg, #ff4444, #cc3333);
        }
        .btn-danger:hover { 
            box-shadow: 0 4px 20px rgba(255, 68, 68, 0.4);
        }
        .metric { 
            display: flex; 
            justify-content: space-between; 
            margin: 12px 0; 
            padding: 12px 0; 
            border-bottom: 1px solid rgba(255,255,255,0.1);
            transition: background 0.3s;
        }
        .metric:hover {
            background: rgba(0, 212, 170, 0.05);
            border-radius: 8px;
            padding: 12px;
            margin: 12px -12px;
        }
        .metric:last-child { border-bottom: none; }
        .profit { color: #00ff88; font-weight: 600; }
        .loss { color: #ff4444; font-weight: 600; }
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid rgba(0,212,170,0.3);
            border-radius: 50%;
            border-top-color: #00d4aa;
            animation: spin 1s ease-in-out infinite;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        @media (max-width: 768px) { 
            body { padding: 10px; }
            .card { padding: 16px; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🚄 Kraken Trading Bot</h1>
        <p>Railway Deployment Dashboard</p>
    </div>
    
    <div class="card">
        <h2>🤖 Bot Status</h2>
        <p id="bot-status"><span class="loading"></span> Connecting...</p>
        <div style="margin-top: 20px;">
            <button class="btn" onclick="startBot()">▶️ Start Bot</button>
            <button class="btn btn-danger" onclick="stopBot()">⏹️ Stop Bot</button>
            <button class="btn" onclick="updateDashboard()" style="background: rgba(255,255,255,0.1);">🔄 Refresh</button>
        </div>
    </div>
    
    <div class="card">
        <h2>📊 Performance Summary</h2>
        <div id="performance-metrics"><span class="loading"></span> Loading performance data...</div>
    </div>
    
    <div class="card">
        <h2>📈 Current Position</h2>
        <div id="current-position"><span class="loading"></span> Loading position data...</div>
    </div>
    
    <div class="card">
        <h2>💼 Recent Trades</h2>
        <div id="recent-trades"><span class="loading"></span> Loading trades...</div>
    </div>
    
    <script>
        let updateInterval;
        let isConnected = false;
        
        function updateDashboard() {
            fetch('/api/status')
                .then(response => response.json())
                .then(data => {
                    isConnected = true;
                    updateStatus(data);
                    updatePerformance(data.performance);
                    updatePosition(data.current_position);
                })
                .catch(error => {
                    isConnected = false;
                    console.error('Error:', error);
                    document.getElementById('bot-status').innerHTML = 
                        '<span class="status-indicator status-stopped"></span>❌ Connection Error';
                });
            
            fetch('/api/trades')
                .then(response => response.json())
                .then(data => updateTrades(data))
                .catch(error => console.error('Trades error:', error));
        }
        
        function updateStatus(data) {
            const statusEl = document.getElementById('bot-status');
            const isRunning = data.status === 'Running';
            const emoji = isRunning ? '🟢' : '🔴';
            
            statusEl.innerHTML = `
                <span class="status-indicator ${isRunning ? 'status-running' : 'status-stopped'}"></span>
                ${emoji} ${data.status || 'Unknown'}
                <small style="display: block; margin-top: 8px; opacity: 0.7;">
                    Last update: ${new Date().toLocaleTimeString()}
                </small>
            `;
        }
        
        function updatePerformance(performance) {
            const perfEl = document.getElementById('performance-metrics');
            
            if (!performance || performance.message) {
                perfEl.innerHTML = '<p>📭 No performance data available</p>';
                return;
            }
            
            const totalPnl = parseFloat(performance.total_pnl.replace('$', ''));
            const winRate = parseFloat(performance.win_rate.replace('%', ''));
            
            perfEl.innerHTML = `
                <div class="metric">
                    <span>📊 Total Trades:</span>
                    <span><strong>${performance.total_trades || 0}</strong></span>
                </div>
                <div class="metric">
                    <span>🎯 Win Rate:</span>
                    <span><strong style="color: ${winRate >= 50 ? '#00ff88' : '#ff4444'}">${performance.win_rate || '0%'}</strong></span>
                </div>
                <div class="metric">
                    <span>💰 Total PnL:</span>
                    <span class="${totalPnl >= 0 ? 'profit' : 'loss'}">
                        <strong>${performance.total_pnl || '$0.00'}</strong>
                    </span>
                </div>
                <div class="metric">
                    <span>🚀 Best Trade:</span>
                    <span class="profit"><strong>${performance.best_trade || '$0.00'}</strong></span>
                </div>
                <div class="metric">
                    <span>📉 Worst Trade:</span>
                    <span class="loss"><strong>${performance.worst_trade || '$0.00'}</strong></span>
                </div>
            `;
        }
        
        function updatePosition(position) {
            const posEl = document.getElementById('current-position');
            
            if (!position) {
                posEl.innerHTML = '<p>📭 No open position</p>';
                return;
            }
            
            const positionEmoji = position.type === 'LONG' ? '📈' : '📉';
            const positionColor = position.type === 'LONG' ? '#00ff88' : '#ff4444';
            
            posEl.innerHTML = `
                <div class="metric">
                    <span>📊 Position Type:</span>
                    <span style="color: ${positionColor}"><strong>${positionEmoji} ${position.type}</strong></span>
                </div>
                <div class="metric">
                    <span>💵 Entry Price:</span>
                    <span><strong>$${position.entry_price.toFixed(2)}</strong></span>
                </div>
                <div class="metric">
                    <span>📦 Quantity:</span>
                    <span><strong>${position.quantity}</strong></span>
                </div>
                <div class="metric">
                    <span>⏰ Entry Time:</span>
                    <span><strong>${new Date(position.entry_time).toLocaleString()}</strong></span>
                </div>
            `;
        }
        
        function updateTrades(trades) {
            const tradesEl = document.getElementById('recent-trades');
            
            if (!trades || trades.length === 0) {
                tradesEl.innerHTML = '<p>📭 No trades yet</p>';
                return;
            }
            
            let html = '<div style="overflow-x: auto;">';
            html += '<table style="width: 100%; border-collapse: collapse; margin-top: 15px;">';
            html += '<thead><tr style="background: rgba(0,212,170,0.1);">';
            html += '<th style="padding: 12px 8px; border-bottom: 2px solid rgba(0,212,170,0.3);">📅 Date</th>';
            html += '<th style="padding: 12px 8px; border-bottom: 2px solid rgba(0,212,170,0.3);">📊 Type</th>';
            html += '<th style="padding: 12px 8px; border-bottom: 2px solid rgba(0,212,170,0.3);">📈 Entry</th>';
            html += '<th style="padding: 12px 8px; border-bottom: 2px solid rgba(0,212,170,0.3);">📉 Exit</th>';
            html += '<th style="padding: 12px 8px; border-bottom: 2px solid rgba(0,212,170,0.3);">💰 PnL</th>';
            html += '</tr></thead><tbody>';
            
            trades.slice(-10).reverse().forEach(trade => {
                const pnlClass = trade.pnl > 0 ? 'profit' : 'loss';
                const typeEmoji = trade.type === 'LONG' ? '📈' : '📉';
                const pnlEmoji = trade.pnl > 0 ? '🟢' : '🔴';
                
                html += `
                    <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                        <td style="padding: 12px 8px;">${new Date(trade.entry_time).toLocaleDateString()}</td>
                        <td style="padding: 12px 8px;">${typeEmoji} ${trade.type}</td>
                        <td style="padding: 12px 8px;">$${trade.entry_price.toFixed(2)}</td>
                        <td style="padding: 12px 8px;">$${trade.exit_price.toFixed(2)}</td>
                        <td style="padding: 12px 8px;" class="${pnlClass}">${pnlEmoji} $${trade.pnl.toFixed(2)}</td>
                    </tr>
                `;
            });
            
            html += '</tbody></table></div>';
            tradesEl.innerHTML = html;
        }
        
        function startBot() {
            const btn = event.target;
            btn.disabled = true;
            btn.innerHTML = '⏳ Starting...';
            
            fetch('/api/start', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    alert(data.message || data.error);
                    updateDashboard();
                })
                .finally(() => {
                    btn.disabled = false;
                    btn.innerHTML = '▶️ Start Bot';
                });
        }
        
        function stopBot() {
            if (confirm('⚠️ Are you sure you want to stop the bot?')) {
                const btn = event.target;
                btn.disabled = true;
                btn.innerHTML = '⏳ Stopping...';
                
                fetch('/api/stop', { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        alert(data.message || data.error);
                        updateDashboard();
                    })
                    .finally(() => {
                        btn.disabled = false;
                        btn.innerHTML = '⏹️ Stop Bot';
                    });
            }
        }
        
        // Connection indicator
        function updateConnectionStatus() {
            const statusIndicator = document.querySelector('.status-indicator');
            if (statusIndicator) {
                statusIndicator.style.opacity = isConnected ? '1' : '0.3';
            }
        }
        
        // Initial load and set up auto-refresh
        updateDashboard();
        updateInterval = setInterval(() => {
            updateDashboard();
            updateConnectionStatus();
        }, 10000);
        
        // Page visibility handling
        document.addEventListener('visibilitychange', function() {
            if (document.hidden) {
                clearInterval(updateInterval);
            } else {
                updateDashboard();
                updateInterval = setInterval(updateDashboard, 10000);
            }
        });
        
        // Auto-refresh indicator
        let refreshCounter = 10;
        setInterval(() => {
            const refreshBtn = document.querySelector('[onclick="updateDashboard()"]');
            if (refreshBtn && !document.hidden) {
                refreshCounter--;
                if (refreshCounter <= 0) {
                    refreshCounter = 10;
                    refreshBtn.innerHTML = '🔄 Refreshing...';
                    setTimeout(() => {
                        refreshBtn.innerHTML = '🔄 Refresh';
                    }, 1000);
                }
            }
        }, 1000);
    </script>
</body>
</html>'''

@app.route('/api/status')
def get_status():
    global trading_bot
    
    if not trading_bot:
        return jsonify({'status': 'Bot not started'})
    
    try:
        performance = trading_bot.get_performance_summary()
        current_position = None
        
        if trading_bot.current_position:
            current_position = {
                'type': trading_bot.current_position.position_type
