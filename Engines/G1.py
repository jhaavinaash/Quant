import pandas as pd
from pathlib import Path
import yfinance as yf
import warnings
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

warnings.filterwarnings('ignore')

# ===== PATH SETUP (compatible with orchestrator) =====
BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR.parent / "data" / "sector_map_fixed.csv"
PORTFOLIO_FILE = BASE_DIR.parent / "portfolio" / "trades_log.csv"

# ===== USER CONFIGURATION =====
TOTAL_CAPITAL = 100000       # Total capital pool
MAX_POSITIONS = 6            # Maximum slots allowed
STOP_LOSS_PCT = 0.045        # 4.5% Stop Loss
TARGET_PCT = 0.06            # 6.0% Target

# SECURE OUTBOUND EMAIL CONFIGURATION
SENDER_EMAIL = "jhaavinaash@gmail.com"
RECEIVER_EMAIL = "jhaavinaash@gmail.com"
EMAIL_APP_PASSWORD = "ahzv hisi ubcx pgoe"  # Verified 16-character Google App Password
# ==============================


def send_screener_email(table_content, date_str, breadth_status):
    """
    Establishes an immediate, secure SSL connection on Port 465
    to transmit the exact console output directly to your inbox.
    """
    print(f"[EMAIL] Outbound connection initiating via Secure SSL... Sending results to {RECEIVER_EMAIL}")
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECEIVER_EMAIL
        msg['Subject'] = f"V7 Screener Alert: {date_str} [BREADTH: {breadth_status}]"

        body = f"The V7 production screener script finished running successfully.\n\n{table_content}"
        msg.attach(MIMEText(body, 'plain'))

        # Secure connection wrapper to eliminate firewall handshaking dropouts
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(SENDER_EMAIL, EMAIL_APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        server.quit()
        print("[EMAIL] Table successfully transmitted to your inbox!")
    except Exception as e:
        print(f"[EMAIL ERROR] Transmission failed: {e}")


def _build_g1_scan():
    """Run the exact G1 screener logic and return structured results."""
    print(f"--- V7.0 BREADTH SCREENER (6-SLOT PRODUCTION) ---")

    # 1. Load and Sanitize Universe Parameters
    try:
        df_map = pd.read_csv(DATA_FILE)
        df_map.columns = df_map.columns.str.strip().str.lower()
        df_map = df_map.apply(lambda x: x.str.strip().str.lower() if x.dtype == "object" else x)
        tickers = df_map['ticker'].unique().tolist()
    except Exception as e:
        print(f"Error: Could not find 'sector_map_fixed.csv'. {e}")
        return {
            "date_str": None,
            "breadth_status": "ERROR",
            "output_buffer": f"Error: Could not find 'sector_map_fixed.csv'. {e}\n",
            "primary_signals": [],
            "all_signals": [],
        }

    # 2. Sync Recent Historical Market Data
    print(f"Syncing data for {len(tickers)} symbols...")
    data = yf.download(tickers, period="100d", progress=False)
    close = data['Close'].ffill()

    valid_tickers = close.columns.intersection(df_map['ticker']).tolist()
    close = close[valid_tickers]

    # 3. Calculate Core System Breadth (The Green/Red Light Engine)
    new_highs = (close == close.rolling(20).max()).sum(axis=1)
    breadth_ok = (new_highs.diff().rolling(3).sum() > 0).iloc[-1]

    dma_50 = close.rolling(50).mean()
    window_rets = close.pct_change(3)

    last_date = close.index[-1]
    date_str = last_date.strftime('%Y-%m-%d')
    breadth_status = "🟢 POSITIVE" if breadth_ok else "🔴 NEGATIVE"

    # Build the structured console/email string buffer
    output_buffer = "=" * 85 + "\n"
    output_buffer += f"DATE: {date_str} | BREADTH: {breadth_status}\n"
    output_buffer += "=" * 85 + "\n\n"

    if not breadth_ok:
        output_buffer += "ACTION: RISK OFF. Do not initiate new trades today.\n"
        print(output_buffer)
        # Email handled by signal_alerts.py when run via dashboard
        return {
            "date_str": date_str,
            "breadth_status": breadth_status,
            "output_buffer": output_buffer,
            "primary_signals": [],
            "all_signals": [],
        }

    # 4. Process Multi-Layered Sector Breadth & Individual Trend Filters
    daily_ret = window_rets.iloc[-1]
    temp = pd.DataFrame({'ticker': valid_tickers, 'ret': daily_ret.values}).merge(df_map, on='ticker').dropna()

    final_signals = []
    for sector, gp in temp.groupby('sector'):
        # Sector Constraints: Min 3 stocks, >2% average return, >=60% participation positive
        if len(gp) >= 3 and gp['ret'].mean() > 0.02 and (gp['ret'] > 0).mean() >= 0.6:
            for t in gp['ticker']:
                price = close.at[last_date, t]
                avg_50 = dma_50.at[last_date, t]
                stock_momentum = gp.loc[gp['ticker'] == t, 'ret'].values[0]

                # Trend Filter: Individual stock price must hold above its 50 DMA
                if price > avg_50:
                    final_signals.append({
                        'Ticker': t.upper(),
                        'Sector': str(sector).title(),
                        'Price': round(price, 2),
                        'Momentum': stock_momentum,
                    })

    # 5. Core Velocity Ranking (Unbiased Alpha Sort)
    final_signals = sorted(final_signals, key=lambda x: x['Momentum'], reverse=True)

    if not final_signals:
        output_buffer += "No setups met the Sector Momentum criteria today.\n"
        print(output_buffer)
        # Email handled by signal_alerts.py when run via dashboard
        return {
            "date_str": date_str,
            "breadth_status": breadth_status,
            "output_buffer": output_buffer,
            "primary_signals": [],
            "all_signals": [],
        }

    # 6. Format the Production Execution Matrix
    slot_allocation = TOTAL_CAPITAL / MAX_POSITIONS
    output_buffer += f"{'TYPE':<10} | {'TICKER':<10} | {'PRICE':<10} | {'SL (4.5%)':<10} | {'TGT (6%)':<10} | {'QTY':<8}\n"
    output_buffer += "-" * 85 + "\n"

    primary_signals = []
    all_signals = []

    for i, s in enumerate(final_signals, 1):
        status = "PRIMARY" if i <= MAX_POSITIONS else "EXCESS"
        price = s['Price']
        sl = round(price * (1 - STOP_LOSS_PCT), 2)
        tgt = round(price * (1 + TARGET_PCT), 2)
        qty = int(slot_allocation // price)
        capital_used = round(qty * price, 2)

        row = {
            'Status': status,
            'Ticker': s['Ticker'],
            'Sector': s['Sector'],
            'Price': price,
            'Entry': price,
            'SL': sl,
            'StopLoss': sl,
            'Target': tgt,
            'Partial_Target': tgt,
            'Qty': qty,
            'Shares': qty,
            'Capital_Used': capital_used,
            'Capital': capital_used,
            'Action': 'BUY',
            'SignalType': 'BUY',
        }
        all_signals.append(row)
        if status == 'PRIMARY':
            primary_signals.append(row)

        output_buffer += f"{status:<10} | {s['Ticker']:<10} | {price:<10} | {sl:<10} | {tgt:<10} | {qty:<8}\n"

    output_buffer += "-" * 85 + "\n"
    output_buffer += f"INSTRUCTIONS:\n"
    output_buffer += f"1. Only enter 'PRIMARY' slots if you have vacant portfolio space.\n"
    output_buffer += f"2. Capital per slot: ₹{slot_allocation:,.2f}\n"
    output_buffer += f"3. Exit if Target (6%), Stop Loss (4.5%), or 5 trading days are reached.\n"

    return {
        "date_str": date_str,
        "breadth_status": breadth_status,
        "output_buffer": output_buffer,
        "primary_signals": primary_signals,
        "all_signals": all_signals,
    }


def get_signals():
    """Orchestrator-friendly interface: return actionable PRIMARY signals only."""
    scan = _build_g1_scan()
    return scan.get("primary_signals", [])


def run_v7_production_screener():
    scan = _build_g1_scan()
    output_buffer = scan.get("output_buffer", "")
    date_str = scan.get("date_str")
    breadth_status = scan.get("breadth_status", "UNKNOWN")

    print(output_buffer)

    if date_str is not None:
        # Automatically forward transmission via secure mail protocols
        send_screener_email(output_buffer, date_str, "SIGNALS_FOUND")


if __name__ == "__main__":
    run_v7_production_screener()
