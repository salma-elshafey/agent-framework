import json
from datetime import datetime, timedelta

# --- General Purpose Tools ---

def run_calculator(expression: str) -> str:
    """
    Performs a mathematical calculation using a simple expression.
    """
    mock_result = "10.0" if '2 + 8' in expression else "The calculated result is 42.5"
    return json.dumps({
        "expression": expression,
        "result": mock_result,
        "note": "Calculation executed successfully (Mock)."
    })

def get_date_information(query: str) -> str:
    """
    Retrieves the current date, time, and day of the week, or calculates a future/past date.
    """
    # Use current time to provide a relevant, non-static mock
    now = datetime.now()
    if "5 days" in query.lower():
        future_date = (now + timedelta(days=5)).strftime("%A, %B %d, %Y")
        mock_info = f"The date in 5 days is {future_date}."
    elif "tokyo" in query.lower():
        mock_info = f"The current date and time (mocked) is {now.strftime('%Y-%m-%d %H:%M:%S')} JST."
    else:
        mock_info = f"Today's date and time is {now.strftime('%A, %B %d, %Y, %I:%M %p %Z')}."

    return json.dumps({
        "query": query,
        "date_info": mock_info,
        "current_system_time": now.isoformat()
    })

def google_search(query: str) -> str:
    """
    Performs a web search using Google to find up-to-date, real-time, or general information.
    """
    if "latest news" in query.lower():
        mock_snippet = "Major tech company announces new generative AI model."
    elif "temperature" in query.lower():
        mock_snippet = "The current temperature in the queried location is 15°C/59°F."
    else:
        mock_snippet = "A relevant web page snippet was found."

    return json.dumps({
        "search_query": query,
        "snippet": mock_snippet,
        "source": "https://mock.search.engine/result"
    })

def wikipedia_search(topic: str) -> str:
    """
    Searches for an article or information on Wikipedia for encyclopedic or historical context.
    """
    mock_summary = f"Wikipedia summary of {topic}: This topic is historically significant and is primarily known for its complexity and foundational role in modern science."

    return json.dumps({
        "topic": topic,
        "summary": mock_summary,
        "source": f"https://en.wikipedia.org/wiki/{topic.replace(' ', '_')}"
    })

def wolfram_alpha_query(query: str) -> str:
    """
    Uses Wolfram Alpha to perform complex scientific, computational, statistical, or factual queries.
    """
    mock_result = "Result: 1.2566370614 * 10^3 (Mock result for complex computation)."
    if "integrate" in query.lower():
        mock_result = "The definite integral of x^2 from 0 to 10 is approximately 333.33."

    return json.dumps({
        "query": query,
        "computed_result": mock_result
    })

# --- Weather Tools ---

def get_current_weather(location: str, unit: str = "celsius") -> str:
    """
    Retrieves the current weather conditions for a specified location.
    """
    temp_c = 20
    temp_f = 68
    
    if unit == "fahrenheit":
        mock_weather = f"{temp_f}°F (Mock) - Sunny"
    else:
        mock_weather = f"{temp_c}°C (Mock) - Sunny"

    return json.dumps({
        "location": location,
        "temperature": mock_weather,
        "conditions": "Clear skies"
    })

def get_historical_weather(location: str, start_date: str, end_date: str = None) -> str:
    """
    Retrieves past weather data for a specific location and date or date range.
    """
    date_range = f"{start_date} to {end_date}" if end_date else start_date
    mock_data = {
        "date": date_range,
        "average_temperature": "18°C / 64°F",
        "precipitation": "2.5mm",
        "conditions": "Partly Cloudy"
    }

    return json.dumps({
        "location": location,
        "historical_data": mock_data
    })

# --- Financial Tools ---

def get_intraday_time_series(ticker: str, interval: str) -> str:
    """
    Retrieves stock market price data at frequent intervals within a single trading day.
    """
    mock_data = {
        "ticker": ticker.upper(),
        "interval": interval,
        "last_5min_close": "175.50",
        "change": "+0.45",
        "note": "Mock intraday data for last hour of trading."
    }
    return json.dumps(mock_data)

def get_daily_time_series(ticker: str, output_size: str = "compact") -> str:
    """
    Retrieves end-of-day stock market price data for a specified ticker over a range of dates.
    """
    mock_data = {
        "ticker": ticker.upper(),
        "output_size": output_size,
        "last_close": "180.20",
        "open": "179.80",
        "volume": "15,500,000",
        "note": f"Mock daily data (Output size: {output_size})."
    }
    return json.dumps(mock_data)

def find_stock_ticker(company_name: str) -> str:
    """
    Searches for the official stock ticker symbol of a company or asset.
    """
    company_name = company_name.lower()
    if "tesla" in company_name:
        ticker = "TSLA"
    elif "google" in company_name or "alphabet" in company_name:
        ticker = "GOOGL"
    else:
        ticker = "MOCK"

    return json.dumps({
        "search_name": company_name,
        "ticker_symbol": ticker,
        "exchange": "NASDAQ (Mock)"
    })
