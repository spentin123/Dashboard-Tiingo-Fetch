import os
import json
import requests
import pandas as pd
from datetime import datetime

# CONFIGURATION
TIINGO_KEY = os.environ.get("TIINGO_API_KEY") 
# Add your watchlist here
TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "BRK.B", "LLY", "V", "JPM", "WMT"] 

def fetch_tiingo_data(ticker):
    headers = {'Content-Type': 'application/json'}
    print(f"Fetching {ticker}...")
    
    # 1. Daily Meta (Profile)
    try:
        meta = requests.get(f"https://api.tiingo.com/tiingo/daily/{ticker}?token={TIINGO_KEY}").json()
    except:
        meta = {}

    # 2. Fundamentals Daily (Stats like PE, Market Cap)
    try:
        stats_list = requests.get(f"https://api.tiingo.com/tiingo/fundamentals/{ticker}/daily?token={TIINGO_KEY}").json()
        latest_stat = stats_list[0] if stats_list and isinstance(stats_list, list) else {}
    except:
        latest_stat = {}
    
    # 3. Financial Statements (Standardized)
    # The 'sort=-date' ensures we get newest first.
    try:
        stmts = requests.get(f"https://api.tiingo.com/tiingo/fundamentals/{ticker}/statements?token={TIINGO_KEY}&sort=-date").json()
    except:
        stmts = []
    
    # 4. Price History (Last 2 Years)
    try:
        start_date = (datetime.now() - pd.DateOffset(years=2)).strftime('%Y-%m-%d')
        history = requests.get(f"https://api.tiingo.com/tiingo/daily/{ticker}/prices?startDate={start_date}&token={TIINGO_KEY}").json()
    except:
        history = []

    # --- PROCESSING ---

    # Helper to safely get nested values
    def get_val(obj, key, default=0):
        if not obj: return default
        return obj.get(key, default)

    # Process Financials
    financials = { "Annual": [], "Quarterly": [] }
    
    if stmts and isinstance(stmts, list):
        for s in stmts:
            # Skip if date is in the future (Tiingo sometimes has projections)
            if s.get('date') > datetime.now().strftime('%Y-%m-%d'):
                continue

            sd = s.get('statementData', {})
            
            # MAPPING: Map Tiingo keys to Dashboard keys
            # Tiingo keys are usually camelCase inside statementData
            metric = {
                "date": s.get('date'),
                "period": f"{s.get('year')} Q{s.get('quarter')}" if s.get('quarter') else str(s.get('year')),
                
                # Income Statement
                "revenue": get_val(sd, 'totalRevenue', 0) or get_val(sd, 'revenue', 0),
                "netIncome": get_val(sd, 'netIncome', 0),
                "eps": get_val(sd, 'epsDiluted', 0) or get_val(sd, 'epsBasic', 0),
                
                # Cash Flow
                "freeCashFlow": get_val(sd, 'freeCashFlow', 0),
                
                # Ratios & Margins (Tiingo provides some pre-calc, otherwise we calc on frontend)
                "grossMargin": get_val(sd, 'grossMargin', 0),
                "operatingMargin": get_val(sd, 'operatingMargin', 0) or get_val(sd, 'opMargin', 0),
                "netMargin": get_val(sd, 'profitMargin', 0),
                
                # Balance Sheet
                "totalAssets": get_val(sd, 'totalAssets', 0),
                "totalEquity": get_val(sd, 'totalEquity', 0) or get_val(sd, 'totalStockholderEquity', 0),
                "totalLiabilities": get_val(sd, 'totalLiabilities', 0),
                "longTermDebt": get_val(sd, 'longTermDebt', 0)
            }
            
            # Check strictly for 0 revenue to avoid polluting data
            if metric['revenue'] == 0 and metric['eps'] == 0:
                continue

            if s.get('quarter') == 0:
                financials['Annual'].append(metric)
            else:
                financials['Quarterly'].append(metric)

    # Process History
    clean_history = []
    if history and isinstance(history, list):
        for h in history:
            clean_history.append({
                "date": h.get('date', '').split('T')[0],
                "price": h.get('adjClose') or h.get('close') or 0
            })

    # Construct Final JSON
    data = {
        "Profile": {
            "Symbol": meta.get('ticker', ticker),
            "Name": meta.get('name', ticker),
            "Description": meta.get('description', 'No description available'),
            "Sector": meta.get('sector'),
            "Industry": meta.get('industry'),
            "CurrentPrice": clean_history[-1]['price'] if clean_history else 0,
            "Currency": "USD" 
        },
        "Stats": {
            "marketCap": latest_stat.get('marketCap'),
            "pe": latest_stat.get('peRatio'),
            "dividendYield": latest_stat.get('dividendYield'),
            "beta": latest_stat.get('beta'),
            "fiftyTwoWeekHigh": latest_stat.get('high52Week'),
            "fiftyTwoWeekLow": latest_stat.get('low52Week'),
            "roe": latest_stat.get('roe'),
            "eps": latest_stat.get('eps')
        },
        "Financials": financials,
        "History": clean_history
    }
    return data

# MAIN LOOP
if __name__ == "__main__":
    if not os.path.exists("data"):
        os.makedirs("data")
        
    for ticker in TICKERS:
        try:
            data = fetch_tiingo_data(ticker)
            if data:
                with open(f"data/{ticker}.json", "w") as f:
                    json.dump(data, f, indent=2)
                print(f"Success: {ticker}")
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
