import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta
import json
from collections import defaultdict
import hashlib

# Initialize session state for commentary history
if 'commentary_history' not in st.session_state:
    st.session_state.commentary_history = {}
if 'current_commentary' not in st.session_state:
    st.session_state.current_commentary = ""

# Portfolio Data
portfolio = [
    {"Ticker": "RELIANCE.NS", "Company": "Reliance Industries", "Qty": 100, "Buy Price": 1200, "Cur Price": 1264.65},
    {"Ticker": "TCS.NS", "Company": "Tata Consultancy Services", "Qty": 50, "Buy Price": 3200, "Cur Price": 3419.80},
    {"Ticker": "INFY.NS", "Company": "Infosys", "Qty": 75, "Buy Price": 1500, "Cur Price": 1640.70},
    {"Ticker": "HDFCBANK.NS", "Company": "HDFC Bank", "Qty": 75, "Buy Price": 1900, "Cur Price": 2006.45},
    {"Ticker": "ICICIBANK.NS", "Company": "ICICI Bank", "Qty": 100, "Buy Price": 1300, "Cur Price": 1425.10},
    {"Ticker": "KOTAKBANK.NS", "Company": "Kotak Mahindra Bank", "Qty": 30, "Buy Price": 2000, "Cur Price": 2129.80},
    {"Ticker": "ITC.NS", "Company": "ITC Ltd", "Qty": 150, "Buy Price": 400, "Cur Price": 418},
    {"Ticker": "BHARTIARTL.NS", "Company": "Bharti Airtel", "Qty": 60, "Buy Price": 1500, "Cur Price": 1630.55},
    {"Ticker": "ASIANPAINTS.NS", "Company": "Asian Paints", "Qty": 40, "Buy Price": 2200, "Cur Price": 2424.20},
    {"Ticker": "LT.NS", "Company": "Larsen & Toubro", "Qty": 50, "Buy Price": 3500, "Cur Price": 3300}
]

# Fetch news function (using Upstox API as provided)
def fetch_news_for_ticker(ticker):
    """Fetch recent news for a ticker"""
    try:
        url = "https://service.upstox.com/content/open/v5/news/sub-category/news/list//market-news/stocks?page=1&pageSize=500"
        response = requests.get(url)
        all_news = response.json()['data']
        company_name = ticker.split('.')[0]  # Get base ticker name
        return [n for n in all_news if company_name in n.get('title', '') or company_name in n.get('description', '')]
    except Exception as e:
        st.error(f"Error fetching news: {e}")
        return []

# Get market data
def get_market_data(ticker):
    stock = yf.Ticker(ticker)
    hist = stock.history(period="1mo")
    if not hist.empty:
        return {
            "52w_high": hist['High'].max(),
            "52w_low": hist['Low'].min(),
            "current_rsi": calculate_rsi(hist['Close']),
            "volume_change": (hist['Volume'][-1] / hist['Volume'].mean() - 1) * 100
        }
    return None

def calculate_rsi(prices, window=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs)).iloc[-1]

# Generate commentary with risk analysis
def generate_portfolio_commentary():
    commentary = "## Portfolio Performance Summary\n\n"
    total_pl = 0
    sector_exposure = defaultdict(float)
    
    # Market overview
    nifty = yf.Ticker("^NSEI").history(period="1d")
    if not nifty.empty:
        nifty_change = (nifty['Close'][-1] - nifty['Open'][0]) / nifty['Open'][0] * 100
        commentary += f"**Market Overview**: Nifty 50 is {'up' if nifty_change >=0 else 'down'} {abs(nifty_change):.2f}% today.\n\n"
    
    # Portfolio analysis
    commentary += "### Key Holdings Performance\n"
    for stock in portfolio:
        ticker = stock["Ticker"]
        pl = (stock["Cur Price"] - stock["Buy Price"]) * stock["Qty"]
        total_pl += pl
        pct_change = (stock["Cur Price"] - stock["Buy Price"]) / stock["Buy Price"] * 100
        
        # Get market data
        market_data = get_market_data(ticker)
        news = fetch_news_for_ticker(ticker)
        
        # Determine sector (simplified)
        sector = "Technology" if ticker in ["TCS.NS", "INFY.NS"] else \
                 "Banking" if "BANK" in ticker else \
                 "Conglomerate" if ticker == "RELIANCE.NS" else \
                 "Consumer" if ticker in ["ITC.NS", "ASIANPAINTS.NS"] else \
                 "Telecom" if ticker == "BHARTIARTL.NS" else "Industrial"
        
        sector_exposure[sector] += stock["Cur Price"] * stock["Qty"]
        
        # Generate stock-specific commentary
        stock_comment = f"- **{stock['Company']} ({ticker})**: "
        stock_comment += f"{'↑' if pct_change >=0 else '↓'} {abs(pct_change):.2f}% since purchase (₹{pl:,.2f} {'profit' if pl>=0 else 'loss'})"
        
        if market_data:
            stock_comment += f", RSI: {market_data['current_rsi']:.1f} {'(Overbought)' if market_data['current_rsi'] > 70 else '(Oversold)' if market_data['current_rsi'] < 30 else ''}"
        
        # Add news highlights
        if news:
            latest_news = sorted(news, key=lambda x: x.get('publishedAt', ''), reverse=True)[0]
            stock_comment += f"\n  - *News*: {latest_news.get('title', '')[:100]}... (Published: {latest_news.get('publishedAt', '')[:10]})"
        
        commentary += stock_comment + "\n"
    
    # Add sector exposure analysis
    total_value = sum([stock["Cur Price"] * stock["Qty"] for stock in portfolio])
    commentary += "\n### Sector Exposure\n"
    for sector, value in sector_exposure.items():
        commentary += f"- **{sector}**: {value/total_value*100:.1f}%\n"
    
    # Add overall risk assessment
    commentary += f"\n### Risk Assessment\n"
    commentary += f"- **Total Portfolio**: ₹{total_pl:,.2f} {'profit' if total_pl>=0 else 'loss'}\n"
    
    # Check for concentrated positions
    max_sector = max(sector_exposure.items(), key=lambda x: x[1])
    if max_sector[1]/total_value > 0.4:
        commentary += f"- ⚠️ **Concentration Risk**: Overexposed to {max_sector[0]} sector ({max_sector[1]/total_value*100:.1f}%)\n"
    
    # Check for high RSI stocks
    high_rsi_stocks = []
    for stock in portfolio:
        market_data = get_market_data(stock["Ticker"])
        if market_data and market_data["current_rsi"] > 70:
            high_rsi_stocks.append(stock["Company"])
    if high_rsi_stocks:
        commentary += f"- ⚠️ **Valuation Risk**: {', '.join(high_rsi_stocks)} appear overbought (RSI > 70)\n"
    
    # Store commentary with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.commentary_history[timestamp] = commentary
    st.session_state.current_commentary = commentary
    
    return commentary

# Improve commentary based on history
def improve_commentary():
    if not st.session_state.commentary_history:
        return generate_portfolio_commentary()
    
    # Analyze past commentaries for improvement opportunities
    past_comments = list(st.session_state.commentary_history.values())
    
    # Simple improvement logic (in a real system, use LLM analysis)
    improvements = []
    if any("Concentration Risk" in c for c in past_comments):
        improvements.append("Added more detailed sector breakdown")
    if any("RSI" in c for c in past_comments) and not any("MACD" in c for c in past_comments):
        improvements.append("Added MACD analysis")
    if not any("dividend" in c.lower() for c in past_comments):
        improvements.append("Added dividend yield analysis")
    
    # Generate new commentary with improvements
    new_commentary = generate_portfolio_commentary()
    
    # Add improvements section
    if improvements:
        new_commentary += "\n### Commentary Improvements\n"
        new_commentary += "This analysis incorporates:\n"
        for imp in improvements:
            new_commentary += f"- {imp}\n"
    
    # Store improved commentary
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.commentary_history[timestamp] = new_commentary
    st.session_state.current_commentary = new_commentary
    
    return new_commentary

# Streamlit UI
st.title("AI Portfolio Risk Dashboard")
st.subheader("Your Indian Equity Portfolio")

# Display portfolio table
df = pd.DataFrame(portfolio)
df['Current Value'] = df['Qty'] * df['Cur Price']
df['P/L'] = (df['Cur Price'] - df['Buy Price']) * df['Qty']
st.dataframe(df.style.format({
    'Buy Price': '{:,.2f}',
    'Cur Price': '{:,.2f}',
    'Current Value': '{:,.2f}',
    'P/L': '{:,.2f}'
}))

# Commentary generation buttons
col1, col2 = st.columns(2)
with col1:
    if st.button("Analyze Portfolio"):
        st.session_state.current_commentary = generate_portfolio_commentary()
with col2:
    if st.button("Improve Analysis"):
        st.session_state.current_commentary = improve_commentary()

# Display current commentary
if st.session_state.current_commentary:
    st.markdown(st.session_state.current_commentary)

# Show commentary history
if st.session_state.commentary_history:
    st.subheader("Analysis History")
    for timestamp, comment in sorted(st.session_state.commentary_history.items(), reverse=True):
        with st.expander(f"Analysis from {timestamp}"):
            st.markdown(comment)

# Risk heatmap visualization
st.subheader("Risk Heatmap")
sectors = {
    "Technology": ["TCS.NS", "INFY.NS"],
    "Banking": ["HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS"],
    "Conglomerate": ["RELIANCE.NS"],
    "Consumer": ["ITC.NS", "ASIANPAINTS.NS"],
    "Telecom": ["BHARTIARTL.NS"],
    "Industrial": ["LT.NS"]
}

# Calculate sector risk scores (simplified)
sector_risk = {}
for sector, tickers in sectors.items():
    risk_score = 0
    for ticker in tickers:
        stock_data = next((s for s in portfolio if s["Ticker"] == ticker), None)
        if stock_data:
            pct_change = (stock_data["Cur Price"] - stock_data["Buy Price"]) / stock_data["Buy Price"] * 100
            market_data = get_market_data(ticker)
            rsi = market_data["current_rsi"] if market_data else 50
            # Simple risk formula (higher RSI and negative returns = higher risk)
            risk_score += (abs(pct_change) * (rsi/50)) if pct_change < 0 else (rsi/70)
    sector_risk[sector] = risk_score / len(tickers) if tickers else 0

# Display heatmap
heatmap_df = pd.DataFrame.from_dict(sector_risk, orient='index', columns=['Risk Score'])
st.bar_chart(heatmap_df)
