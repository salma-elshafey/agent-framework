calculator_tool_spec = {
    "type": "function",
    "function": {
        "name": "run_calculator",
        "description": "Performs a mathematical calculation using a simple expression.",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "The mathematical expression to evaluate, e.g., '2 + 2', 'sqrt(9) * 5', '45 / 3.14'."
                }
            },
            "required": ["expression"]
        }
    }
}

date_tool_spec = {
    "type": "function",
    "function": {
        "name": "get_date_information",
        "description": "Retrieves the current date, time, and day of the week, or calculates a future/past date.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A natural language query for date/time information, e.g., 'What is the date in 5 days?', 'What is today’s date and time in Tokyo?'."
                }
            },
            "required": ["query"]
        }
    }
}

google_search_tool_spec = {
    "type": "function",
    "function": {
        "name": "google_search",
        "description": "Performs a web search using Google to find up-to-date, real-time, or general information on a topic.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query, e.g., 'latest news on AI regulations', 'current temperature in New York', 'history of the Roman Empire'."
                }
            },
            "required": ["query"]
        }
    }
}

wiki_search_tool_spec = {
    "type": "function",
    "function": {
        "name": "wikipedia_search",
        "description": "Searches for an article or information on Wikipedia for encyclopedic or historical context.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "The topic or article title to search for on Wikipedia, e.g., 'Quantum Computing', 'World War II', 'Albert Einstein'."
                }
            },
            "required": ["topic"]
        }
    }
}

current_weather_tool_spec = {
    "type": "function",
    "function": {
        "name": "get_current_weather",
        "description": "Retrieves the current weather conditions for a specified location.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The city and state or country, e.g., 'London, UK' or 'San Francisco, CA'."
                },
                "unit": {
                    "type": "string",
                    "description": "The temperature unit to return the result in.",
                    "enum": ["celsius", "fahrenheit"]
                }
            },
            "required": ["location"]
        }
    }
}

historical_weather_tool_spec = {
    "type": "function",
    "function": {
        "name": "get_historical_weather",
        "description": "Retrieves past weather data for a specific location and date or date range.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The city and state or country, e.g., 'Rome, Italy'."
                },
                "start_date": {
                    "type": "string",
                    "description": "The start date for the historical data in YYYY-MM-DD format, or a single date."
                },
                "end_date": {
                    "type": "string",
                    "description": "The end date for the historical data in YYYY-MM-DD format. Optional if querying for a single day."
                }
            },
            "required": ["location", "start_date"]
        }
    }
}

wolfram_alpha_tool_spec = {
    "type": "function",
    "function": {
        "name": "wolfram_alpha_query",
        "description": "Uses Wolfram Alpha to perform complex scientific, computational, statistical, or factual queries.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The complex query to resolve, e.g., 'integrate x^2 from 0 to 10', 'population of the world in 1950', 'distance to the moon'."
                }
            },
            "required": ["query"]
        }
    }
}

time_series_intraday_tool_spec = {
    "type": "function",
    "function": {
        "name": "get_intraday_time_series",
        "description": "Retrieves stock market price data at frequent intervals (e.g., 1-minute, 5-minute) within a single trading day.",
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "The stock ticker symbol, e.g., 'AAPL' for Apple, 'GOOGL' for Alphabet."
                },
                "interval": {
                    "type": "string",
                    "description": "The time interval for the data points.",
                    "enum": ["1min", "5min", "15min", "30min", "60min"]
                }
            },
            "required": ["ticker", "interval"]
        }
    }
}

time_series_daily_tool_spec = {
    "type": "function",
    "function": {
        "name": "get_daily_time_series",
        "description": "Retrieves end-of-day stock market price data for a specified ticker over a range of dates.",
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "The stock ticker symbol, e.g., 'MSFT' for Microsoft."
                },
                "output_size": {
                    "type": "string",
                    "description": "The amount of data to return.",
                    "enum": ["compact", "full"]
                }
            },
            "required": ["ticker"]
        }
    }
}

ticker_search_tool_spec = {
    "type": "function",
    "function": {
        "name": "find_stock_ticker",
        "description": "Searches for the official stock ticker symbol of a company or asset.",
        "parameters": {
            "type": "object",
            "properties": {
                "company_name": {
                    "type": "string",
                    "description": "The name of the company or financial asset, e.g., 'Tesla', 'Coca-Cola Company', 'Bitcoin'."
                }
            },
            "required": ["company_name"]
        }
    }
}
