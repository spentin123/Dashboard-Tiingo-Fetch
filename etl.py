import os
import json
import requests
import pandas as pd
from datetime import datetime

# CONFIGURATION
TIINGO_KEY = os.environ.get("TIINGO_API_KEY") # Set this in GitHub Secrets
TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "BRK.B", "LLY", "V"] # Add your watchlist here

def fetch_tiingo_data(ticker):
    headers = {'Content-Type': 'application/json'}
    
    # 1. Daily Meta & Stats
    meta = requests.get(f"https://api.tiingo.com/tiingo/daily/{ticker}?token={TIINGO_KEY}").json()
    stats = requests.get(f"https://api.tiingo.com/tiingo/fundamentals/{ticker}/daily?token={TIINGO_KEY}").json()
    
    # 2. Financial Statements (Standardized)
    stmts = requests.get(f"https://api.tiingo.com/tiingo/fundamentals/{ticker}/statements?token={TIINGO_KEY}&sort=-date").json()
    
    # 3. Price History (2 Years)
    start_date = (datetime.now() - pd.DateOffset(years=2)).strftime('%Y-%m-%d')
    history = requests.get(f"https://api.tiingo.com/tiingo/daily/{ticker}/prices?startDate={start_date}&token={TIINGO_KEY}").json()

    if not meta or not stats: return None

    latest_stat = stats[0] if stats else {}
    
    # Process Financials (Group by Annual/Quarterly)
    financials = { "Annual": [], "Quarterly": [] }
    for s in stmts:
        # Map Tiingo fields to Dashboard Schema
        metric = {
            "date": s['date'],
            "period": f"{s['year']} Q{s['quarter']}" if s['quarter'] else str(s['year']),
            "revenue": s.get('statementData', {}).get('totalRevenue', 0),
            "netIncome": s.get('statementData', {}).get('netIncome', 0),
            "eps": s.get('statementData', {}).get('epsDiluted', 0),
            "freeCashFlow": s.get('statementData', {}).get('freeCashFlow', 0),
            # ... map other fields (grossMargin, operatingMargin, etc) ...
        }
        if s['quarter'] == 0:
            financials['Annual'].append(metric)
        else:
            financials['Quarterly'].append(metric)

    # Construct Final JSON
    data = {
        "Profile": {
            "Symbol": meta.get('ticker'),
            "Name": meta.get('name'),
            "Description": meta.get('description'),
            "Sector": meta.get('sector'),
            "Industry": meta.get('industry'),
            "CurrentPrice": history[-1]['adjClose'] if history else 0
        },
        "Stats": {
            "marketCap": latest_stat.get('marketCap'),
            "pe": latest_stat.get('peRatio'),
            "dividendYield": latest_stat.get('dividendYield'),
            "beta": latest_stat.get('beta'),
            "fiftyTwoWeekHigh": latest_stat.get('high52Week'),
            "fiftyTwoWeekLow": latest_stat.get('low52Week')
        },
        "Financials": financials,
        "History": [{"date": h['date'].split('T')[0], "price": h['adjClose']} for h in history]
    }
    return data

# MAIN LOOP
if __name__ == "__main__":
    if not os.path.exists("data"):
        os.makedirs("data")
        
    for ticker in TICKERS:
        print(f"Fetching {ticker}...")
        try:
            data = fetch_tiingo_data(ticker)
            if data:
                with open(f"data/{ticker}.json", "w") as f:
                    json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
