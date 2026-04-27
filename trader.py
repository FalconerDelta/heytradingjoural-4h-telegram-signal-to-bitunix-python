import os
import re
import time
import json
import hashlib
import requests
from telethon import TelegramClient, events
from dotenv import load_dotenv

# Load credentials from .env
load_dotenv()

# --- CONFIG ---
API_ID = int(os.getenv('TELEGRAM_API_ID'))
API_HASH = os.getenv('TELEGRAM_API_HASH')
CHANNEL_USERNAME = os.getenv('TELEGRAM_CHANNEL_USERNAME')

BITUNIX_KEY = os.getenv('BITUNIX_API_KEY')
BITUNIX_SECRET = os.getenv('BITUNIX_API_SECRET')
BASE_URL = "https://fapi.bitunix.com"

class BitunixTrader:
    def __init__(self, key, secret):
        self.key = key
        self.secret = secret

    def _generate_sign(self, nonce, timestamp, body_str):
        # Bitunix Official Signature: SHA256(apiKey + nonce + timestamp + body + apiSecret)
        payload_str = f"{self.key}{nonce}{timestamp}{body_str}{self.secret}"
        return hashlib.sha256(payload_str.encode('utf-8')).hexdigest()

    def place_order(self, symbol, direction, price, tp, sl):
        endpoint = "/api/v1/futures/trade/place_order"
        timestamp = str(int(time.time() * 1000))
        nonce = os.urandom(8).hex()
        
        # Per Documentation: 
        # side: "BUY" or "SELL" (String)
        # open: 1 (Open), 2 (Close) (Integer)
        # type: 1 (Limit), 2 (Market) (Integer)
        side_string = "BUY" if "做多" in direction else "SELL"
        
        data = {
            "symbol": symbol.replace(".P", ""),
            "side": side_string, 
            "type": 1,           # 1 = Limit Order
            "price": str(price),
            "vol": "1",          # Number of contracts
            "open": 1,           # 1 = Open position
            "stopLoss": str(sl),
            "takeProfit": str(tp)
        }

        # Body must be minified for signature verification
        body_str = json.dumps(data, separators=(',', ':'))
        
        headers = {
            "api-key": self.key,
            "nonce": nonce,
            "timestamp": timestamp,
            "sign": self._generate_sign(nonce, timestamp, body_str),
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(BASE_URL + endpoint, headers=headers, data=body_str)
            return response.json()
        except Exception as e:
            return {"error": str(e)}

# --- TELEGRAM MONITOR ---
trader = BitunixTrader(BITUNIX_KEY, BITUNIX_SECRET)
client = TelegramClient('bitunix_session', API_ID, API_HASH)

@client.on(events.NewMessage(chats=CHANNEL_USERNAME))
async def handle_new_signal(event):
    text = event.raw_text
    
    # Filter for BTC and ETH only
    if not any(x in text for x in ["BTCUSDT", "ETHUSDT"]):
        return

    try:
        # Parsing using regex based on your provided sample
        symbol = re.search(r"(BTC|ETH)USDT", text).group(0)
        direction = "做多" if "做多" in text else "做空"
        entry = re.search(r"入場價格: ([\d.]+)", text).group(1)
        sl = re.search(r"止損.*: ([\d.]+)", text).group(1)
        # Grab only the first TP value before the hyphen
        tp = re.search(r"止盈.*: ([\d.]+)", text).group(1)

        print(f"✅ Found Signal: {symbol} {direction} @ {entry}")
        
        resp = trader.place_order(symbol, direction, entry, tp, sl)
        print(f"📊 Bitunix Response: {json.dumps(resp)}")

    except Exception as e:
        print(f"❌ Error parsing signal: {e}")

print("🚀 Bot started. Monitoring Telegram for BTC/ETH signals...")
client.start()
client.run_until_disconnected()