import os
import re
import time
import json
import hashlib
import secrets
import requests
import asyncio
import logging
from telethon import TelegramClient, events, errors
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- CONFIGURATION ---
API_ID = int(os.getenv('TELEGRAM_API_ID'))
API_HASH = os.getenv('TELEGRAM_API_HASH')
raw_channels = os.getenv('TELEGRAM_CHANNEL_USERNAME', 'me')
TARGET_CHANNELS = [int(c.strip()) if c.strip().lstrip('-').isdigit() else c.strip() for c in raw_channels.split(',')]

BITUNIX_KEY = os.getenv('BITUNIX_API_KEY')
BITUNIX_SECRET = os.getenv('BITUNIX_API_SECRET')
BASE_URL = "https://fapi.bitunix.com"

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class BitunixTrader:
    def __init__(self, key, secret):
        self.key = key
        self.secret = secret

    def _generate_sign(self, nonce, timestamp, query_str="", body_str=""):
        digest_input = f"{nonce}{timestamp}{self.key}{query_str}{body_str}"
        first_hash = hashlib.sha256(digest_input.encode('utf-8')).hexdigest()
        sign_input = f"{first_hash}{self.secret}"
        return hashlib.sha256(sign_input.encode('utf-8')).hexdigest()

    def get_account_info(self):
        endpoint = "/api/v1/futures/account"
        timestamp = str(int(time.time() * 1000))
        nonce = secrets.token_hex(16)
        params = {"marginCoin": "USDT"}
        query_str = "marginCoinUSDT"
        
        headers = {
            "api-key": self.key, "nonce": nonce, "timestamp": timestamp,
            "sign": self._generate_sign(nonce, timestamp, query_str=query_str),
            "Content-Type": "application/json"
        }
        try:
            response = requests.get(BASE_URL + endpoint, headers=headers, params=params, timeout=10)
            data = response.json()
            return float(data.get('data', {}).get('available', 0.0)) if data.get('code') == 0 else 0.0
        except Exception:
            return 0.0

    def close_ticker_positions(self, symbol):
        """Closes all existing positions for a specific ticker before opening a new one."""
        endpoint = "/api/v1/futures/trade/close_all_position"
        timestamp = str(int(time.time() * 1000))
        nonce = secrets.token_hex(16)
        
        # Format required by Bitunix: {"symbol":"BTCUSDT"}
        body_data = {"symbol": symbol.replace(".P", "")}
        body_str = json.dumps(body_data, separators=(',', ':'), sort_keys=True)

        headers = {
            "api-key": self.key, 
            "nonce": nonce, 
            "timestamp": timestamp,
            "sign": self._generate_sign(nonce, timestamp, body_str=body_str),
            "Content-Type": "application/json"
        }

        try:
            logging.info(f"🔄 Closing all existing positions for {symbol}...")
            response = requests.post(BASE_URL + endpoint, headers=headers, data=body_str, timeout=15)
            result = response.json()
            logging.info(f"📥 Close Response: {json.dumps(result)}")
            return result
        except Exception as e:
            logging.error(f"Failed to close positions: {e}")
            return None

    def place_market_order(self, symbol, side, qty, sl, tp):
        endpoint = "/api/v1/futures/trade/place_order"
        timestamp = str(int(time.time() * 1000))
        nonce = secrets.token_hex(16)

        order_data = {
            "orderType": "MARKET", "price": "0", "qty": str(qty),
            "side": side, "tpPrice": str(tp), "slPrice": str(sl),
            "symbol": symbol.replace(".P", ""), "tradeSide": "OPEN"
        }

        body_str = json.dumps(order_data, separators=(',', ':'), sort_keys=True)
        headers = {
            "api-key": self.key, "nonce": nonce, "timestamp": timestamp,
            "sign": self._generate_sign(nonce, timestamp, body_str=body_str),
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(BASE_URL + endpoint, headers=headers, data=body_str, timeout=15)
            result = response.json()
            logging.info(f"📥 Response: {json.dumps(result)}")
            return result
        except Exception as e:
            logging.error(f"Order failed: {e}")
            return None

async def run_bot():
    trader = BitunixTrader(BITUNIX_KEY, BITUNIX_SECRET)
    client = TelegramClient('bitunix_trader_session', API_ID, API_HASH, auto_reconnect=True)

    @client.on(events.NewMessage(chats=TARGET_CHANNELS))
    async def handle_new_signal(event):
        text = event.raw_text
        if not text or not any(p in text for p in ["BTCUSDT", "ETHUSDT"]):
            return

        # 1. Improved Extraction using specific Regex patterns
        try:
            # Extract Symbol (e.g., ETHUSDT)
            symbol_match = re.search(r"交易品種:\s*([A-Z]+)", text)
            # Extract Side (Look for Long/Short or Chinese characters)
            side_match = re.search(r"方向:\s*.*(做多|做空|Long|Short)", text)
            # Extract Entry Price
            entry_match = re.search(r"入場價格:\s*([\d.]+)", text)
            # Extract SL
            sl_match = re.search(r"止損.*:\s*([\d.]+)", text)
            # Extract TP (Takes the first TP value in a range like 1910.60 - 1759.32)
            tp_match = re.search(r"止盈.*:\s*([\d.]+)", text)
            # Extract Leverage (Look for number before 'x')
            lev_match = re.search(r"建議槓桿:\s*([\d.]+)x", text)

            # Validation: Ensure all critical data points exist
            if not all([symbol_match, side_match, entry_match, sl_match, tp_match]):
                logging.info("Message received but did not match expected trading format.")
                return

            symbol = symbol_match.group(1).replace(".P", "")
            raw_side = side_match.group(1)
            side = "BUY" if raw_side in ["做多", "Long"] else "SELL"
            entry_price = float(entry_match.group(1))
            sl = sl_match.group(1)
            tp = tp_match.group(1)
            leverage = float(lev_match.group(1)) if lev_match else 1.0 # Default to 1x if not found

            logging.info(f"✅ Parsed Signal: {symbol} {side} | Entry: {entry_price} | Lev: {leverage}x")

            # 2. Close existing positions for this ticker first
            trader.close_ticker_positions(symbol)
            await asyncio.sleep(0.5)

            # 3. Get balance and calculate Qty
            current_bal = trader.get_account_info()
            if current_bal < 2.0: 
                logging.warning(f"Balance too low ({current_bal} USDT).")
                return

            # Qty Logic: (Balance * Leverage) / Entry Price
            qty_val = (current_bal * leverage) / entry_price
            qty_str = f"{qty_val:.4f}"

            # 4. Place Order
            logging.info(f"🚀 Executing {side} on {symbol} with {leverage}x leverage (Qty: {qty_str})")
            trader.place_market_order(symbol, side, qty_str, sl, tp)
        
        except Exception as e:
            logging.error(f"Parsing error: {e}")

    retry_delay = 5
    while True:
        try:
            logging.info("🔗 Connecting to Telegram...")
            await client.start()
            
            balance = trader.get_account_info()
            logging.info(f"✅ Live! Balance: {balance} USDT")

            await client.run_until_disconnected()
            
        except (ConnectionError, OSError, asyncio.CancelledError) as e:
            logging.error(f"📡 Network issue ({type(e).__name__}). Retrying in {retry_delay}s...")
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 60)
        except Exception as e:
            logging.critical(f"🔥 Unexpected error: {e}")
            await asyncio.sleep(10)
        finally:
            retry_delay = 5

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        pass