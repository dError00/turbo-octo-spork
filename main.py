import os
import json
import time
import hmac
import hashlib
import base64
import requests
import logging
import threading
import websocket
import schedule
from datetime import datetime
from flask import Flask, render_template_string
from dotenv import load_dotenv

# ======================================
# Logging configuration
# ======================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ======================================
# Load environment variables
# ======================================
load_dotenv()

class KrakenConfig:
    def __init__(self):
        self.api_key = os.getenv("KRAKEN_API_KEY")
        self.api_secret = os.getenv("KRAKEN_API_SECRET")
        self.base_url = "https://api.kraken.com"
        self.ws_url = "wss://ws.kraken.com/"
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.sandbox_mode = True  # Set False for real trading

# ======================================
# Kraken API wrapper
# ======================================
class KrakenAPI:
    def __init__(self, config: KrakenConfig):
        self.config = config
        self.session = requests.Session()

    def _sign(self, uri_path, data):
        postdata = urllib.parse.urlencode(data)
        encoded = (str(data['nonce']) + postdata).encode()
        message = uri_path.encode() + hashlib.sha256(encoded).digest()
        mac = hmac.new(base64.b64decode(self.config.api_secret), message, hashlib.sha512)
        return base64.b64encode(mac.digest()).decode()

    def private_request(self, method, data=None):
        if data is None:
            data = {}
        data['nonce'] = int(time.time() * 1000)
        headers = {
            'API-Key': self.config.api_key,
            'API-Sign': self._sign(f"/0/private/{method}", data)
        }
        url = f"{self.config.base_url}/0/private/{method}"
        resp = self.session.post(url, headers=headers, data=data)
        return resp.json()

    def public_request(self, method, params=None):
        url = f"{self.config.base_url}/0/public/{method}"
        resp = self.session.get(url, params=params)
        return resp.json()

    def get_balance(self):
        return self.private_request("Balance")

    def place_order(self, pair, side, volume, ordertype="market"):
        if self.config.sandbox_mode:
            logger.info(f"[SANDBOX] Placing {side} order for {volume} {pair}")
            return {"txid": [f"sandbox_{int(time.time())}"]}
        data = {
            "pair": pair,
            "type": side,
            "ordertype": ordertype,
            "volume": volume
        }
        return self.private_request("AddOrder", data)

# ======================================
# Strategy engine
# ======================================
class StrategyEngine:
    def __init__(self):
        self.last_price = None

    def generate_signal(self, price):
        if self.last_price is None:
            self.last_price = price
            return None
        signal = None
        if price > self.last_price * 1.002:
            signal = "buy"
        elif price < self.last_price * 0.998:
            signal = "sell"
        self.last_price = price
        return signal

# ======================================
# Telegram alert system
# ======================================
class TelegramBot:
    def __init__(self, config: KrakenConfig):
        self.token = config.telegram_token
        self.chat_id = config.telegram_chat_id

    def send_message(self, text):
        if not self.token or not self.chat_id:
            logger.warning("Telegram not configured.")
            return
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        requests.post(url, data={"chat_id": self.chat_id, "text": text})

# ======================================
# WebSocket listener
# ======================================
class KrakenWS:
    def __init__(self, config: KrakenConfig, strategy: StrategyEngine, api: KrakenAPI, bot: TelegramBot):
        self.config = config
        self.strategy = strategy
        self.api = api
        self.bot = bot

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
                price = float(data[1][0][0])
                signal = self.strategy.generate_signal(price)
                if signal:
                    logger.info(f"Signal: {signal.upper()} at {price}")
                    self.bot.send_message(f"Signal: {signal.upper()} at {price}")
                    if not self.config.sandbox_mode:
                        self.api.place_order("XBTEUR", signal, 0.001)
        except Exception as e:
            logger.error(f"Error parsing message: {e}")

    def on_open(self, ws):
        logger.info("WebSocket connection opened.")
        subscribe_data = {
            "event": "subscribe",
            "pair": ["XBT/EUR"],
            "subscription": {"name": "ticker"}
        }
        ws.send(json.dumps(subscribe_data))

    def run(self):
        ws = websocket.WebSocketApp(self.config.ws_url,
                                    on_message=self.on_message,
                                    on_open=self.on_open)
        ws.run_forever()

# ======================================
# Flask Dashboard
# ======================================
app = Flask(__name__)
latest_signals = []

@app.route("/")
def dashboard():
    return render_template_string("""
        <html>
        <head><title>Kraken Bot Dashboard</title></head>
        <body>
            <h1>Latest Signals</h1>
            <ul>
                {% for s in signals %}
                    <li>{{ s }}</li>
                {% endfor %}
            </ul>
        </body>
        </html>
    """, signals=latest_signals)

# ======================================
# Main entry
# ======================================
if __name__ == "__main__":
    cfg = KrakenConfig()
    api = KrakenAPI(cfg)
    strategy = StrategyEngine()
    telegram = TelegramBot(cfg)
    ws_client = KrakenWS(cfg, strategy, api, telegram)

    threading.Thread(target=ws_client.run, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)
