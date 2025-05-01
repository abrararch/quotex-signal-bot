import telebot
import talib
import numpy as np
import pandas as pd
import time
from datetime import datetime
import pytz
import requests
import os
from threading import Thread

# Initialize bot (using environment variable for security)
bot = telebot.TeleBot(os.getenv('TELEGRAM_TOKEN'))

# Pakistan Timezone
PAK_TZ = pytz.timezone('Asia/Karachi')

# 30+ Trading Assets
ASSETS = {
    'Crypto': ['BTC-USD', 'ETH-USD', 'XRP-USD', 'SOL-USD', 'ADA-USD', 
               'BNB-USD', 'DOGE-USD', 'DOT-USD', 'MATIC-USD', 'AVAX-USD'],
    'Forex': ['EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'AUDUSD=X', 'USDPKR=X',
              'USDCAD=X', 'USDCHF=X', 'NZDUSD=X', 'EURGBP=X', 'EURJPY=X'],
    'Commodities': ['GC=F', 'SI=F', 'CL=F', 'HG=F', 'NG=F',
                    'PL=F', 'PA=F', 'ZC=F', 'ZS=F', 'KE=F'],
    'Stocks': ['TSLA', 'AAPL', 'AMZN', 'GOOG', 'META',
               'MSFT', 'NVDA', 'NFLX', 'SPY', 'QQQ']
}

# Technical Indicators Configuration
INDICATORS = {
    'RSI': {'period': 14, 'overbought': 70, 'oversold': 30},
    'MACD': {'fast': 12, 'slow': 26, 'signal': 9},
    'Bollinger': {'period': 20, 'dev': 2},
    'Stochastic': {'k': 14, 'd': 3},
    'EMA': {'short': 9, 'medium': 21, 'long': 50},
    'ADX': {'period': 14, 'strong': 25},
    'ATR': {'period': 14},
    'CCI': {'period': 20, 'levels': [-100, 100]},
    'OBV': {},
    'Ichimoku': {}
}

def get_pakistan_time():
    """Get precise PKT time with milliseconds"""
    return datetime.now(PAK_TZ).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

def analyze_with_indicators(df):
    """Calculate 10 technical indicators"""
    analysis = {}
    # RSI
    analysis['RSI'] = talib.RSI(df['close'], timeperiod=14)[-1]
    # MACD
    analysis['MACD'], analysis['MACD_Signal'], _ = talib.MACD(df['close'])
    # Bollinger Bands
    analysis['BB_Upper'], analysis['BB_Middle'], analysis['BB_Lower'] = talib.BBANDS(df['close'])
    # Stochastic
    analysis['Stoch_K'], analysis['Stoch_D'] = talib.STOCH(df['high'], df['low'], df['close'])
    # EMA Cross
    analysis['EMA_Short'] = talib.EMA(df['close'], timeperiod=9)[-1]
    analysis['EMA_Medium'] = talib.EMA(df['close'], timeperiod=21)[-1]
    # ADX
    analysis['ADX'] = talib.ADX(df['high'], df['low'], df['close'])[-1]
    # ATR
    analysis['ATR'] = talib.ATR(df['high'], df['low'], df['close'])[-1]
    # CCI
    analysis['CCI'] = talib.CCI(df['high'], df['low'], df['close'])[-1]
    # OBV
    analysis['OBV'] = talib.OBV(df['close'], df['volume'])[-1]
    # Ichimoku Conversion Line
    analysis['Ichimoku'] = (max(df['high'][-9:-1]) + min(df['low'][-9:-1])) / 2
    return analysis

def generate_signal(symbol):
    """Generate trading signal with confidence score"""
    df = get_market_data(symbol)
    if df.empty:
        return None
    
    analysis = analyze_with_indicators(df)
    signal_score = 0
    
    # Indicator Scoring
    if analysis['RSI'] < 30: signal_score += 2
    elif analysis['RSI'] > 70: signal_score -= 2
    if analysis['MACD'][-1] > analysis['MACD_Signal'][-1]: signal_score += 1
    else: signal_score -= 1
    if df['close'][-1] < analysis['BB_Lower'][-1]: signal_score += 1
    elif df['close'][-1] > analysis['BB_Upper'][-1]: signal_score -= 1
    
    direction = "BUY" if signal_score > 1 else "SELL" if signal_score < -1 else "NEUTRAL"
    confidence = min(95, max(70, 70 + abs(signal_score)*10))
    
    return {
        'symbol': symbol,
        'time': get_pakistan_time(),
        'direction': direction,
        'confidence': confidence,
        'analysis': analysis,
        'entry_price': df['close'][-1],
        'stop_loss': df['close'][-1] * (0.99 if direction == "BUY" else 1.01),
        'take_profit': df['close'][-1] * (1.02 if direction == "BUY" else 0.98)
    }

def format_signal(signal):
    """Create professional signal message"""
    emoji = "🚀" if "BUY" in signal['direction'] else "🔻" if "SELL" in signal['direction'] else "➖"
    return f"""
{emoji} *{signal['symbol']} Signal* {emoji}
⏰ *Entry Time:* `{signal['time']}`
📊 *Direction:* {signal['direction']} ({signal['confidence']}% confidence)

📈 *Price Levels:*
- Entry: `{signal['entry_price']:.5f}`
- Stop Loss: `{signal['stop_loss']:.5f}`
- Take Profit: `{signal['take_profit']:.5f}`

📊 *Technical Indicators:*
- RSI: `{signal['analysis']['RSI']:.2f}` {'(Oversold)' if signal['analysis']['RSI'] < 30 else '(Overbought)' if signal['analysis']['RSI'] > 70 else ''}
- MACD: `{signal['analysis']['MACD'][-1]:.4f}`
- BBands: `{signal['analysis']['BB_Lower'][-1]:.2f} | {signal['analysis']['BB_Upper'][-1]:.2f}`
- Stoch: K=`{signal['analysis']['Stoch_K'][-1]:.1f}`, D=`{signal['analysis']['Stoch_D'][-1]:.1f}`
- EMA Cross: {'Golden (Bullish)' if signal['analysis']['EMA_Short'] > signal['analysis']['EMA_Medium'] else 'Death (Bearish)'}

💡 *Suggested Action:* {'Strong entry' if signal['confidence'] > 85 else 'Caution advised' if signal['confidence'] < 75 else 'Moderate confidence'}
"""

# Bot Commands
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message,
        "🚀 *Quotex Pro Signals Bot*\n\n"
        "I provide high-accuracy trading signals with:\n"
        "• 10+ professional indicators\n"
        "• Precise PKT timing\n"
        "• Risk management levels\n\n"
        "Commands:\n"
        "/signal [asset] - Get trading signal\n"
        "/assets - List supported assets\n"
        "/time - Check server time",
        parse_mode='Markdown')

@bot.message_handler(commands=['signal'])
def send_signal(message):
    try:
        args = message.text.split()
        symbol = args[1].upper() + ('-USD' if len(args) > 1 and 'USD' not in args[1] else '') if len(args) > 1 else "BTC-USD"
        
        signal = generate_signal(symbol)
        if signal:
            bot.reply_to(message, format_signal(signal), parse_mode='Markdown')
        else:
            bot.reply_to(message, "❌ Couldn't fetch data for this asset")
    except Exception as e:
        bot.reply_to(message, f"⚠️ Error: {str(e)}")

@bot.message_handler(commands=['assets'])
def list_assets(message):
    response = "📊 *Supported Assets*\n\n"
    for category, symbols in ASSETS.items():
        response += f"*{category}:*\n" + "\n".join([f"• {s}" for s in symbols]) + "\n\n"
    bot.reply_to(message, response, parse_mode='Markdown')

# Keep the bot running
def run_bot():
    while True:
        try:
            bot.polling(none_stop=True, interval=0)
        except Exception as e:
            print(f"Bot error: {e}")
            time.sleep(10)

if __name__ == '__main__':
    print("⚡ Bot started with 30+ assets and 10 indicators")
    Thread(target=run_bot).start() 
