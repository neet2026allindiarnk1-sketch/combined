import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import ta
import asyncio
import json
import warnings
warnings.filterwarnings('ignore')

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8141895800:AAHt5iQwiMf2jHNPwGnXgVi4SI76879nhmQ"
YOUR_TELEGRAM_ID = 5531217637  # Your user ID for auto signals

# ==================== VIRTUAL ACCOUNT ====================
class VirtualAccount:
    def __init__(self):
        self.balance = 100.0
        self.initial_balance = 100.0
        self.lot_size = 0.02
        self.active_trades = []
        self.closed_trades = []
        self.total_pnl = 0
        
    def open_trade(self, signal):
        trade = {
            'id': len(self.closed_trades) + len(self.active_trades) + 1,
            'type': signal['direction'],
            'entry': signal['entry'],
            'sl': signal['sl'],
            'tp1': signal['tp1'],
            'tp2': signal['tp2'],
            'tp3': signal['tp3'],
            'lot_size': self.lot_size,
            'open_time': datetime.now(),
            'tp1_hit': False,
            'tp2_hit': False,
            'pnl': 0
        }
        self.active_trades.append(trade)
        return trade
    
    def check_trades(self, current_price):
        updates = []
        for trade in self.active_trades[:]:
            if trade['type'] == 'BUY':
                # Check SL
                if current_price <= trade['sl']:
                    pnl = (trade['sl'] - trade['entry']) * 100 * self.lot_size
                    self.balance += pnl
                    trade['pnl'] = pnl
                    self.active_trades.remove(trade)
                    self.closed_trades.append(trade)
                    updates.append(f"🔴 SL HIT! Trade #{trade['id']} Loss: ${abs(pnl):.2f}")
                # Check TPs
                elif current_price >= trade['tp3']:
                    if not trade['tp2_hit']:
                        trade['tp2_hit'] = True
                        updates.append(f"✅ TP3 HIT! Trade #{trade['id']}")
                    pnl = (trade['tp3'] - trade['entry']) * 100 * self.lot_size
                    self.balance += pnl
                    trade['pnl'] = pnl
                    self.active_trades.remove(trade)
                    self.closed_trades.append(trade)
                    updates.append(f"🎯 CLOSED at TP3! Profit: ${pnl:.2f}")
                elif current_price >= trade['tp2'] and not trade['tp2_hit']:
                    trade['tp2_hit'] = True
                    pnl = (current_price - trade['entry']) * 100 * self.lot_size
                    updates.append(f"✅ TP2 HIT! Trade #{trade['id']} Running profit: ${pnl:.2f}")
                elif current_price >= trade['tp1'] and not trade['tp1_hit']:
                    trade['tp1_hit'] = True
                    pnl = (current_price - trade['entry']) * 100 * self.lot_size
                    updates.append(f"✅ TP1 HIT! Trade #{trade['id']} Running profit: ${pnl:.2f}")
            else:  # SELL
                # Similar logic for SELL trades
                if current_price >= trade['sl']:
                    pnl = (trade['entry'] - trade['sl']) * 100 * self.lot_size
                    self.balance += pnl
                    trade['pnl'] = pnl
                    self.active_trades.remove(trade)
                    self.closed_trades.append(trade)
                    updates.append(f"🔴 SL HIT! Trade #{trade['id']} Loss: ${abs(pnl):.2f}")
                # Check TPs for SELL...
                
        # Check account status
        if self.balance <= 20:
            updates.append(f"⚠️ ACCOUNT CRITICAL! Balance: ${self.balance:.2f}")
        elif self.balance <= 0:
            updates.append(f"💀 ACCOUNT WIPED!")
            
        return updates

# ==================== AUTO SIGNAL SENDER ====================
class AutoSignalSender:
    def __init__(self, application):
        self.app = application
        self.account = VirtualAccount()
        self.running = False
        self.last_signal_time = {}
        
    async def monitor_markets(self):
        """Continuous market monitoring"""
        self.running = True
        logger.info("Auto signal monitoring started...")
        
        while self.running:
            try:
                # Check different timeframes
                await self.check_timeframe('M5', 300)    # Every 5 mins
                await self.check_timeframe('M15', 900)   # Every 15 mins
                await self.check_timeframe('H1', 3600)   # Every hour
                
                # Check active trades
                await self.monitor_trades()
                
                # Wait 60 seconds before next check
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                await asyncio.sleep(60)
    
    async def check_timeframe(self, tf, cooldown):
        """Check specific timeframe for signals"""
        try:
            # Check cooldown
            last_time = self.last_signal_time.get(tf, 0)
            if datetime.now().timestamp() - last_time < cooldown:
                return
                
            # Get current price
            ticker = yf.Ticker("GC=F")
            hist = ticker.history(period='1d', interval='1m')
            if hist.empty:
                return
            current_price = hist['Close'].iloc[-1]
            
            # Get data based on timeframe
            if tf == 'M5':
                data = ticker.history(period='1d', interval='5m')
            elif tf == 'M15':
                data = ticker.history(period='2d', interval='15m')
            elif tf == 'H1':
                data = ticker.history(period='5d', interval='1h')
            else:
                return
                
            if data.empty or len(data) < 50:
                return
                
            # Calculate indicators
            signal = await self.detect_signal(data, current_price, tf)
            
            if signal:
                await self.send_signal(signal, tf)
                self.last_signal_time[tf] = datetime.now().timestamp()
                
        except Exception as e:
            logger.error(f"Timeframe check error: {e}")
    
    async def detect_signal(self, df, current_price, timeframe):
        """Balanced signal detection - not too strict"""
        try:
            # Calculate indicators
            df['EMA_9'] = ta.trend.EMAIndicator(df['Close'], window=9).ema_indicator()
            df['EMA_21'] = ta.trend.EMAIndicator(df['Close'], window=21).ema_indicator()
            df['EMA_50'] = ta.trend.EMAIndicator(df['Close'], window=50).ema_indicator()
            df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
            df['ATR'] = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close']).average_true_range()
            
            # MACD
            macd = ta.trend.MACD(df['Close'])
            df['MACD'] = macd.macd()
            df['MACD_signal'] = macd.macd_signal()
            
            # Stochastic
            stoch = ta.momentum.StochasticOscillator(df['High'], df['Low'], df['Close'])
            df['Stoch_K'] = stoch.stoch()
            
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            buy_score = 0
            sell_score = 0
            reasons = []
            
            # 1. Trend Check (not too strict)
            if current_price > latest['EMA_9'] and latest['EMA_9'] > latest['EMA_21']:
                buy_score += 2
                reasons.append("📈 Bullish trend")
            elif current_price < latest['EMA_9'] and latest['EMA_9'] < latest['EMA_21']:
                sell_score += 2
                reasons.append("📉 Bearish trend")
            
            # 2. RSI (balanced approach)
            if latest['RSI'] < 35:
                buy_score += 2
                reasons.append(f"🟢 RSI Oversold ({latest['RSI']:.0f})")
            elif latest['RSI'] > 65:
                sell_score += 2
                reasons.append(f"🔴 RSI Overbought ({latest['RSI']:.0f})")
            elif 35 <= latest['RSI'] <= 50:
                buy_score += 1
            elif 50 < latest['RSI'] <= 65:
                sell_score += 1
            
            # 3. MACD
            if latest['MACD'] > latest['MACD_signal'] and latest['MACD'] > prev['MACD']:
                buy_score += 1
                reasons.append("📊 MACD Bullish")
            elif latest['MACD'] < latest['MACD_signal'] and latest['MACD'] < prev['MACD']:
                sell_score += 1
                reasons.append("📊 MACD Bearish")
            
            # 4. Stochastic
            if latest['Stoch_K'] < 30:
                buy_score += 1
                reasons.append("📊 Stoch Oversold")
            elif latest['Stoch_K'] > 70:
                sell_score += 1
                reasons.append("📊 Stoch Overbought")
            
            # 5. EMA Cross
            if prev['EMA_9'] <= prev['EMA_21'] and latest['EMA_9'] > latest['EMA_21']:
                buy_score += 2
                reasons.append("🎯 Golden Cross")
            elif prev['EMA_9'] >= prev['EMA_21'] and latest['EMA_9'] < latest['EMA_21']:
                sell_score += 2
                reasons.append("🎯 Death Cross")
            
            # REASONABLE minimum score (not too strict)
            min_score = 4  # Reduced from 5-6
            
            if buy_score >= min_score and buy_score > sell_score:
                direction = "BUY"
                total_score = buy_score
            elif sell_score >= min_score and sell_score > buy_score:
                direction = "SELL"
                total_score = sell_score
            else:
                return None
            
            # Calculate confidence
            confidence = min((total_score / 8) * 100, 85)
            
            # Accept decent confidence (not ultra high)
            if confidence < 50:  # Reduced from 60
                return None
            
            # Calculate targets with REASONABLE stops
            atr = latest['ATR']
            
            if direction == "BUY":
                entry = current_price
                sl = entry - (atr * 2.5)    # Reasonable stop
                tp1 = entry + (atr * 3)
                tp2 = entry + (atr * 5)
                tp3 = entry + (atr * 7)
            else:
                entry = current_price
                sl = entry + (atr * 2.5)
                tp1 = entry - (atr * 3)
                tp2 = entry - (atr * 5)
                tp3 = entry - (atr * 7)
            
            return {
                'direction': direction,
                'entry': entry,
                'sl': sl,
                'tp1': tp1,
                'tp2': tp2,
                'tp3': tp3,
                'confidence': confidence,
                'score': total_score,
                'reasons': reasons,
                'atr': atr,
                'rsi': latest['RSI'],
                'timeframe': timeframe
            }
            
        except Exception as e:
            logger.error(f"Signal detection error: {e}")
            return None
    
    async def send_signal(self, signal, timeframe):
        """Send signal to user"""
        try:
            # Open virtual trade
            trade = self.account.open_trade(signal)
            
            # Calculate pips
            pips_sl = abs(signal['entry'] - signal['sl']) * 100
            pips_tp1 = abs(signal['tp1'] - signal['entry']) * 100
            pips_tp2 = abs(signal['tp2'] - signal['entry']) * 100
            pips_tp3 = abs(signal['tp3'] - signal['entry']) * 100
            
            message = f"""
🔔 *AUTO SIGNAL DETECTED!*

📊 *{timeframe} {signal['direction']} Signal*
🎯 Confidence: {signal['confidence']:.0f}%
📈 Score: {signal['score']}/8

═══════════════════
📍 Entry: ${signal['entry']:.2f}
🛑 SL: ${signal['sl']:.2f} ({pips_sl:.0f} pips)
🎯 TP1: ${signal['tp1']:.2f} ({pips_tp1:.0f} pips)
🎯 TP2: ${signal['tp2']:.2f} ({pips_tp2:.0f} pips)
🎯 TP3: ${signal['tp3']:.2f} ({pips_tp3:.0f} pips)

📊 *Reasons:*
{chr(10).join(signal['reasons'])}

💼 *Virtual Trade #{trade['id']} Opened*
💰 Account: ${self.account.balance:.2f}
📦 Lot Size: {self.account.lot_size}

_Auto-tracking active_
"""
            
            await self.app.bot.send_message(
                chat_id=YOUR_TELEGRAM_ID,
                text=message,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Send signal error: {e}")
    
    async def monitor_trades(self):
        """Monitor active trades"""
        try:
            if not self.account.active_trades:
                return
                
            # Get current price
            ticker = yf.Ticker("GC=F")
            hist = ticker.history(period='1d', interval='1m')
            if hist.empty:
                return
            current_price = hist['Close'].iloc[-1]
            
            # Check trades
            updates = self.account.check_trades(current_price)
            
            for update in updates:
                await self.app.bot.send_message(
                    chat_id=YOUR_TELEGRAM_ID,
                    text=update,
                    parse_mode='Markdown'
                )
                
                # Add account summary
                summary = f"""
💰 *Account Update*
Balance: ${self.account.balance:.2f}
P&L: ${self.account.balance - self.account.initial_balance:+.2f}
Active Trades: {len(self.account.active_trades)}
"""
                await self.app.bot.send_message(
                    chat_id=YOUR_TELEGRAM_ID,
                    text=summary,
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            logger.error(f"Monitor trades error: {e}")

# ==================== REAL-TIME PRICE MODULE ====================
class RealTimePrice:
    @staticmethod
    def get_current_price(symbol="GC=F"):
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='1d', interval='1m')
            if not hist.empty:
                return hist['Close'].iloc[-1]
                
            info = ticker.info
            if 'currentPrice' in info:
                return info['currentPrice']
            elif 'regularMarketPrice' in info:
                return info['regularMarketPrice']
            elif 'previousClose' in info:
                return info['previousClose']
                
            return None
        except:
            return None

# ==================== BALANCED SCALPING MODULE ====================
class ScalpingModule:
    def __init__(self):
        self.symbol = "GC=F"
        self.price_module = RealTimePrice()
        
    async def fetch_scalping_data(self):
        try:
            ticker = yf.Ticker(self.symbol)
            
            data_1m = ticker.history(period='60m', interval='1m')
            data_5m = ticker.history(period='1d', interval='5m')
            
            current_price = self.price_module.get_current_price()
            
            return {
                '1m': data_1m if not data_1m.empty else None,
                '5m': data_5m if not data_5m.empty else None,
                'current_price': current_price,
                'timestamp': datetime.now()
            }
        except Exception as e:
            logger.error(f"Scalping data error: {e}")
            return {'1m': None, '5m': None, 'current_price': None}
    
    def calculate_scalping_indicators(self, df):
        if df is None or len(df) < 20:
            return None
            
        try:
            df['EMA_3'] = ta.trend.EMAIndicator(df['Close'], window=3).ema_indicator()
            df['EMA_5'] = ta.trend.EMAIndicator(df['Close'], window=5).ema_indicator()
            df['EMA_8'] = ta.trend.EMAIndicator(df['Close'], window=8).ema_indicator()
            df['RSI_5'] = ta.momentum.RSIIndicator(df['Close'], window=5).rsi()
            
            stoch = ta.momentum.StochasticOscillator(df['High'], df['Low'], df['Close'], window=5, smooth_window=3)
            df['Stoch_K'] = stoch.stoch()
            
            bb = ta.volatility.BollingerBands(df['Close'], window=10, window_dev=1.5)
            df['BB_upper'] = bb.bollinger_hband()
            df['BB_lower'] = bb.bollinger_lband()
            
            df['ATR'] = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close'], window=7).average_true_range()
            df['Volume_MA'] = df['Volume'].rolling(window=10).mean()
            df['Volume_Spike'] = df['Volume'] > (df['Volume_MA'] * 1.2)
            
            return df
        except:
            return None
    
    def detect_scalping_opportunity(self, df_1m, df_5m, current_price=None):
        if df_1m is None or len(df_1m) < 20:
            return None
            
        try:
            signals = []
            buy_score = 0
            sell_score = 0
            
            latest = df_1m.iloc[-1]
            prev = df_1m.iloc[-2]
            
            price = current_price if current_price else latest['Close']
            
            # 1. Basic trend
            if price > latest['EMA_3'] > latest['EMA_5']:
                buy_score += 2
                signals.append("📈 Short-term uptrend")
            elif price < latest['EMA_3'] < latest['EMA_5']:
                sell_score += 2
                signals.append("📉 Short-term downtrend")
            
            # 2. EMA Cross
            if latest['EMA_3'] > latest['EMA_8'] and prev['EMA_3'] <= prev['EMA_8']:
                buy_score += 2
                signals.append("🎯 Bullish cross")
            elif latest['EMA_3'] < latest['EMA_8'] and prev['EMA_3'] >= prev['EMA_8']:
                sell_score += 2
                signals.append("🎯 Bearish cross")
            
            # 3. RSI
            if latest['RSI_5'] < 30:
                buy_score += 2
                signals.append(f"🟢 RSI oversold ({latest['RSI_5']:.0f})")
            elif latest['RSI_5'] > 70:
                sell_score += 2
                signals.append(f"🔴 RSI overbought ({latest['RSI_5']:.0f})")
            
            # 4. Bollinger
            if price <= latest['BB_lower']:
                buy_score += 1
                signals.append("📊 At lower BB")
            elif price >= latest['BB_upper']:
                sell_score += 1
                signals.append("📊 At upper BB")
            
            # 5. Volume
            if latest['Volume_Spike']:
                signals.append("💥 Volume spike")
                if buy_score >= sell_score:
                    buy_score += 1
                else:
                    sell_score += 1
            
            # REASONABLE minimum
            if buy_score >= 3 and buy_score > sell_score:
                signal_type = "SCALP BUY 🟢"
                confidence = min((buy_score / 7) * 100, 85)
            elif sell_score >= 3 and sell_score > buy_score:
                signal_type = "SCALP SELL 🔴"
                confidence = min((sell_score / 7) * 100, 85)
            else:
                return None
            
            # Reasonable targets
            atr = latest['ATR']
            
            if "BUY" in signal_type:
                entry = price
                sl = price - (atr * 2)      # 2x ATR
                tp1 = price + (atr * 2.5)   # 2.5x ATR
                tp2 = price + (atr * 3.5)   # 3.5x ATR
                tp3 = price + (atr * 5)     # 5x ATR
            else:
                entry = price
                sl = price + (atr * 2)
                tp1 = price - (atr * 2.5)
                tp2 = price - (atr * 3.5)
                tp3 = price - (atr * 5)
            
            pips_to_tp1 = abs(tp1 - entry) * 100
            pips_to_tp2 = abs(tp2 - entry) * 100
            pips_to_tp3 = abs(tp3 - entry) * 100
            pips_sl = abs(entry - sl) * 100
            
            return {
                'type': signal_type,
                'confidence': confidence,
                'entry': entry,
                'sl': sl,
                'tp1': tp1,
                'tp2': tp2,
                'tp3': tp3,
                'signals': signals,
                'current_price': price,
                'pips_sl': pips_sl,
                'pips_tp1': pips_to_tp1,
                'pips_tp2': pips_to_tp2,
                'pips_tp3': pips_to_tp3,
                'score': buy_score if "BUY" in signal_type else sell_score,
                'timestamp': datetime.now()
            }
        except:
            return None

# ==================== BALANCED PROFESSIONAL MODULE ====================
class ProfessionalModule:
    def __init__(self):
        self.symbol = "GC=F"
        self.price_module = RealTimePrice()
        
    async def fetch_professional_data(self, interval='1h', period='10d'):
        try:
            ticker = yf.Ticker(self.symbol)
            data = ticker.history(period=period, interval=interval)
            
            current_price = self.price_module.get_current_price()
            
            return data if not data.empty else None, current_price
        except:
            return None, None
    
    def calculate_professional_indicators(self, df):
        if df is None or len(df) < 50:
            return None
            
        try:
            df['EMA_9'] = ta.trend.EMAIndicator(df['Close'], window=9).ema_indicator()
            df['EMA_21'] = ta.trend.EMAIndicator(df['Close'], window=21).ema_indicator()
            df['EMA_50'] = ta.trend.EMAIndicator(df['Close'], window=50).ema_indicator()
            
            df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
            
            macd = ta.trend.MACD(df['Close'])
            df['MACD'] = macd.macd()
            df['MACD_signal'] = macd.macd_signal()
            
            bb = ta.volatility.BollingerBands(df['Close'], window=20, window_dev=2)
            df['BB_upper'] = bb.bollinger_hband()
            df['BB_lower'] = bb.bollinger_lband()
            df['BB_middle'] = bb.bollinger_mavg()
            
            df['ATR'] = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close']).average_true_range()
            
            stoch = ta.momentum.StochasticOscillator(df['High'], df['Low'], df['Close'])
            df['Stoch_K'] = stoch.stoch()
            
            adx = ta.trend.ADXIndicator(df['High'], df['Low'], df['Close'])
            df['ADX'] = adx.adx()
            df['DI_plus'] = adx.adx_pos()
            df['DI_minus'] = adx.adx_neg()
            
            df['Volume_MA'] = df['Volume'].rolling(window=20).mean()
            df['Volume_Ratio'] = df['Volume'] / df['Volume_MA']
            
            return df
        except:
            return None
    
    def generate_professional_signal(self, df, current_price=None):
        if df is None or len(df) < 50:
            return None
            
        try:
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            buy_score = 0
            sell_score = 0
            reasons = []
            
            price = current_price if current_price else latest['Close']
            
            # 1. Trend (balanced)
            if price > latest['EMA_9'] > latest['EMA_21']:
                buy_score += 2
                reasons.append("📈 Bullish trend structure")
            elif price < latest['EMA_9'] < latest['EMA_21']:
                sell_score += 2
                reasons.append("📉 Bearish trend structure")
            
            # 2. EMA alignment
            if price > latest['EMA_50']:
                buy_score += 1
                reasons.append("📊 Above EMA 50")
            else:
                sell_score += 1
                reasons.append("📊 Below EMA 50")
            
            # 3. RSI (balanced zones)
            if latest['RSI'] < 40:
                buy_score += 2
                reasons.append(f"🟢 RSI bullish ({latest['RSI']:.0f})")
            elif latest['RSI'] > 60:
                sell_score += 2
                reasons.append(f"🔴 RSI bearish ({latest['RSI']:.0f})")
            elif 40 <= latest['RSI'] <= 50:
                buy_score += 1
            elif 50 < latest['RSI'] <= 60:
                sell_score += 1
            
            # 4. MACD
            if latest['MACD'] > latest['MACD_signal']:
                buy_score += 1
                reasons.append("📊 MACD bullish")
            else:
                sell_score += 1
                reasons.append("📊 MACD bearish")
            
            # 5. Stochastic
            if latest['Stoch_K'] < 40:
                buy_score += 1
                reasons.append(f"📊 Stoch bullish ({latest['Stoch_K']:.0f})")
            elif latest['Stoch_K'] > 60:
                sell_score += 1
                reasons.append(f"📊 Stoch bearish ({latest['Stoch_K']:.0f})")
            
            # 6. ADX
            if latest['ADX'] > 20:
                reasons.append(f"💪 Trend present (ADX: {latest['ADX']:.0f})")
                if latest['DI_plus'] > latest['DI_minus']:
                    buy_score += 1
                else:
                    sell_score += 1
            
            # 7. Volume
            if latest['Volume_Ratio'] > 1.2:
                reasons.append("📊 High volume")
                if price > prev['Close']:
                    buy_score += 1
                else:
                    sell_score += 1
            
            # BALANCED minimum score
            if buy_score >= 4 and buy_score > sell_score:
                signal_type = "BUY 🟢"
                confidence = min((buy_score / 10) * 100, 85)
                score = buy_score
            elif sell_score >= 4 and sell_score > buy_score:
                signal_type = "SELL 🔴"
                confidence = min((sell_score / 10) * 100, 85)
                score = sell_score
            else:
                return None
            
            # Accept reasonable confidence
            if confidence < 40:  # Lowered threshold
                return None
            
            # Reasonable targets
            atr = latest['ATR']
            
            if "BUY" in signal_type:
                entry = price
                sl = price - (atr * 3)      # 3x ATR
                tp1 = price + (atr * 4)     # 4x ATR
                tp2 = price + (atr * 6)     # 6x ATR
                tp3 = price + (atr * 9)     # 9x ATR
            else:
                entry = price
                sl = price + (atr * 3)
                tp1 = price - (atr * 4)
                tp2 = price - (atr * 6)
                tp3 = price - (atr * 9)
            
            # Risk level
            if confidence >= 70:
                lot_size = 0.03
                risk_level = "LOW"
            elif confidence >= 55:
                lot_size = 0.02
                risk_level = "MEDIUM"
            else:
                lot_size = 0.01
                risk_level = "HIGH"
            
            pips_to_tp1 = abs(tp1 - entry) * 100
            pips_to_tp2 = abs(tp2 - entry) * 100
            pips_to_tp3 = abs(tp3 - entry) * 100
            pips_sl = abs(entry - sl) * 100
            
            return {
                'signal': signal_type,
                'confidence': confidence,
                'entry': entry,
                'sl': sl,
                'tp1': tp1,
                'tp2': tp2,
                'tp3': tp3,
                'lot_size': lot_size,
                'risk_level': risk_level,
                'reasons': reasons,
                'current_price': price,
                'pips_sl': pips_sl,
                'pips_tp1': pips_to_tp1,
                'pips_tp2': pips_to_tp2,
                'pips_tp3': pips_to_tp3,
                'rsi': latest['RSI'],
                'adx': latest['ADX'],
                'score': score,
                'timestamp': datetime.now()
            }
        except:
            return None

# ==================== MAIN BOT CLASS ====================
class TradingBot:
    def __init__(self):
        self.scalping = ScalpingModule()
        self.professional = ProfessionalModule()
        
    async def get_scalping_signal(self):
        data = await self.scalping.fetch_scalping_data()
        
        if data['1m'] is None:
            return None
            
        df_1m = self.scalping.calculate_scalping_indicators(data['1m'])
        df_5m = self.scalping.calculate_scalping_indicators(data['5m']) if data['5m'] is not None else None
        
        signal = self.scalping.detect_scalping_opportunity(df_1m, df_5m, data.get('current_price'))
        
        if signal and data.get('timestamp'):
            signal['data_timestamp'] = data['timestamp']
            
        return signal
    
    async def get_professional_signal(self, timeframe):
        interval_map = {
            'M15': ('15m', '5d'),
            'M30': ('30m', '7d'),
            'H1': ('1h', '15d'),
            'H4': ('1h', '30d')
        }
        
        interval, period = interval_map.get(timeframe, ('1h', '10d'))
        df, current_price = await self.professional.fetch_professional_data(interval, period)
        
        if df is None:
            return None
            
        df = self.professional.calculate_professional_indicators(df)
        return self.professional.generate_professional_signal(df, current_price)

# Global instances
bot = TradingBot()
auto_sender = None

# ==================== TELEGRAM HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = """
🤖 *BALANCED TRADING BOT v3.0*

✅ *Features:*
• Auto signal detection active
• Virtual $100 account tracking
• Real-time price monitoring
• Balanced filters (not too strict)
• Auto TP/SL monitoring

📱 *Auto Signals ON for:*
• M5, M15, H1 timeframes
• Direct to your Telegram
• Virtual trades tracked

💰 *Manual Check:*
"""
    
    keyboard = [
        [InlineKeyboardButton("🚀 Quick Scalp", callback_data='scalp_quick')],
        [InlineKeyboardButton("📊 M15", callback_data='pro_m15'),
         InlineKeyboardButton("💰 M30", callback_data='pro_m30')],
        [InlineKeyboardButton("💎 H1", callback_data='pro_h1'),
         InlineKeyboardButton("🎯 H4", callback_data='pro_h4')],
        [InlineKeyboardButton("📈 Check Account", callback_data='account')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def handle_scalping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    loading = await query.message.reply_text("🔄 *Scanning for scalps...*", parse_mode='Markdown')
    
    signal = await bot.get_scalping_signal()
    
    if not signal:
        await loading.edit_text(
            "📊 *No clear scalp setup*\n\n"
            "Market is consolidating.\n"
            "Auto-scanner is active and will notify you!",
            parse_mode='Markdown'
        )
        return
    
    profit_tp1 = signal['pips_tp1'] * 0.01
    profit_tp2 = signal['pips_tp2'] * 0.01
    
    message = f"""
{signal['type']}

✅ *Confidence: {signal['confidence']:.0f}%*
💰 *Price: ${signal['current_price']:.2f}*

═══════════════════
📍 Entry: ${signal['entry']:.2f}
🛑 SL: ${signal['sl']:.2f} ({signal['pips_sl']:.0f} pips)

🎯 TP1: ${signal['tp1']:.2f} ({signal['pips_tp1']:.0f} pips)
🎯 TP2: ${signal['tp2']:.2f} ({signal['pips_tp2']:.0f} pips)
🎯 TP3: ${signal['tp3']:.2f} ({signal['pips_tp3']:.0f} pips)

💸 *Potential (0.01 lot):*
• TP1: ${profit_tp1:.2f}
• TP2: ${profit_tp2:.2f}

📊 *Signals ({signal['score']}/7):*
{chr(10).join(signal['signals'])}
"""
    
    await loading.delete()
    
    keyboard = [[
        InlineKeyboardButton("🔄 New Scan", callback_data='scalp_quick'),
        InlineKeyboardButton("📊 H1", callback_data='pro_h1')
    ]]
    
    await query.message.reply_text(
        message,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def analyze_professional(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    tf_map = {
        'pro_m15': 'M15',
        'pro_m30': 'M30',
        'pro_h1': 'H1',
        'pro_h4': 'H4'
    }
    
    timeframe = tf_map.get(query.data, 'H1')
    
    loading = await query.message.reply_text(
        f"🔄 *Analyzing {timeframe}...*",
        parse_mode='Markdown'
    )
    
    signal = await bot.get_professional_signal(timeframe)
    
    if not signal:
        await loading.edit_text(
            f"📊 *No setup on {timeframe}*\n\n"
            "Need more confirmations.\n"
            "Auto-scanner will alert you!",
            parse_mode='Markdown'
        )
        return
    
    message = f"""
{signal['signal']} *- {timeframe}*

✅ *Confidence: {signal['confidence']:.0f}%*
⚖️ *Risk: {signal['risk_level']}*

═══════════════════
💰 Price: ${signal['current_price']:.2f}
📍 Entry: ${signal['entry']:.2f}
🛑 SL: ${signal['sl']:.2f} ({signal['pips_sl']:.0f} pips)

🎯 TP1: ${signal['tp1']:.2f} ({signal['pips_tp1']:.0f} pips)
🎯 TP2: ${signal['tp2']:.2f} ({signal['pips_tp2']:.0f} pips)
🎯 TP3: ${signal['tp3']:.2f} ({signal['pips_tp3']:.0f} pips)

📦 Lot Size: {signal['lot_size']}

📊 *Analysis ({signal['score']}/10):*
{chr(10).join(signal['reasons'])}

RSI: {signal['rsi']:.0f} | ADX: {signal['adx']:.0f}
"""
    
    await loading.delete()
    
    keyboard = [[
        InlineKeyboardButton("🔄 Refresh", callback_data=query.data),
        InlineKeyboardButton("🚀 Scalp", callback_data='scalp_quick')
    ]]
    
    await query.message.reply_text(
        message,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def check_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if auto_sender:
        acc = auto_sender.account
        message = f"""
💼 *VIRTUAL ACCOUNT STATUS*

💰 Balance: ${acc.balance:.2f}
📊 P&L: ${acc.balance - acc.initial_balance:+.2f}
📈 Active Trades: {len(acc.active_trades)}
📉 Closed Trades: {len(acc.closed_trades)}

_Auto-trading active_
"""
    else:
        message = "❌ Auto-trader not initialized"
    
    await query.message.reply_text(message, parse_mode='Markdown')

async def post_init(application):
    """Initialize auto sender"""
    global auto_sender
    auto_sender = AutoSignalSender(application)
    
    # Start monitoring
    asyncio.create_task(auto_sender.monitor_markets())
    
    # Send startup message
    await application.bot.send_message(
        chat_id=YOUR_TELEGRAM_ID,
        text="🚀 *Bot Started Successfully!*\n\nAuto-monitoring active for:\n• M5, M15, H1 signals\n• Virtual $100 account\n• Real-time updates",
        parse_mode='Markdown'
    )

def main():
    print("🤖 Starting Balanced Trading Bot v3.0...")
    print(f"📱 Auto signals to: {YOUR_TELEGRAM_ID}")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_scalping, pattern='^scalp_'))
    application.add_handler(CallbackQueryHandler(analyze_professional, pattern='^pro_'))
    application.add_handler(CallbackQueryHandler(check_account, pattern='^account'))
    
    # Set post init
    application.post_init = post_init
    
    print("✅ Bot ready!")
    print("📊 Auto-scanning M5, M15, H1")
    print("💰 Virtual account: $100")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
