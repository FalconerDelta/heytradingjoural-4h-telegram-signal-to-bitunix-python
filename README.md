# 🤖 Bitunix Telegram Signal Trader

An automated trading bot designed to listen to specific Telegram channels, parse trading signals for **BTC** and **ETH**, and execute high-speed futures orders on the **Bitunix** exchange.

## ✨ Features

* **Real-time Monitoring**: Uses the Telethon library to listen for new messages instantly.
* **Intelligent Parsing**: Robust regex patterns to extract Symbol, Side (Long/Short), Entry Price, Stop Loss, Take Profit, and Leverage from formatted Chinese/English signals.
* **Auto-Position Management**: Automatically closes existing positions for a specific ticker before opening a new one to prevent hedging conflicts.
* **Dynamic Risk Management**: Automatically calculates position quantity based on your available USDT balance and suggested leverage.
* **Resilient Connectivity**: Built-in auto-reconnect logic to handle Telegram network interruptions.

## 🚀 How it Works

### 1. Signal Recognition
The bot monitors targeted channels for messages containing "BTCUSDT" or "ETHUSDT". It is optimized for signals formatted like this:
>💎 交易品種: ETHUSDT.P 方向: 做多 (Long 🟢)
>📊 當前 ATR: ##.## 🌊 ADX 強度: ##.##
>📉 RSI: ##.#
>💰 入場價格: ####.##
>🛑 止損 (2x ATR): ####.##
>🎯 止盈 (2-4x ATR): ####.## - ####.##
>⚡️ 建議槓桿: #x
>📦 倉位價值: ###.# U
>🕒 時間: 2026-##-## 00:00:00

### 2. Execution Logic
* **Step 1**: Validates the signal and extracts variables.
* **Step 2**: Calls the Bitunix API to close any open positions for that specific symbol.
* **Step 3**: Checks current account balance.
* **Step 4**: Calculates quantity ($Qty = \frac{Balance \times Leverage}{Entry Price}$) and places a Market Order with attached SL and TP.

## ⚠️ Disclaimer

This bot is for educational purposes only. Trading futures involves significant risk. The authors are not responsible for any financial losses incurred while using this software. Always test with small amounts or on a paper trading account first.
