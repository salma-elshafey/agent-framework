import json
import random
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

# --- Travel Planning Tools ---

def search_hotels(location: str, check_in: str, check_out: str, guests: int = 2) -> str:
    """
    Search for available hotels based on location and dates.
    """
    # Specific mock data for Paris December 15-18, 2025
    if "paris" in location.lower():
        mock_hotels = [
            {
                "name": "Hotel Eiffel Trocadéro",
                "rating": 4.6,
                "price_per_night": "$185",
                "total_price": "$555 for 3 nights",
                "distance_to_eiffel_tower": "0.3 miles",
                "amenities": ["WiFi", "Breakfast", "Eiffel Tower View", "Concierge"],
                "availability": "Available",
                "address": "35 Rue Benjamin Franklin, 16th arr., Paris"
            },
            {
                "name": "Mercure Paris Centre Tour Eiffel",
                "rating": 4.4,
                "price_per_night": "$220",
                "total_price": "$660 for 3 nights",
                "distance_to_eiffel_tower": "0.5 miles",
                "amenities": ["WiFi", "Restaurant", "Bar", "Gym", "Air Conditioning"],
                "availability": "Available",
                "address": "20 Rue Jean Rey, 15th arr., Paris"
            },
            {
                "name": "Pullman Paris Tour Eiffel",
                "rating": 4.7,
                "price_per_night": "$280",
                "total_price": "$840 for 3 nights",
                "distance_to_eiffel_tower": "0.2 miles",
                "amenities": ["WiFi", "Spa", "Gym", "Restaurant", "Rooftop Bar", "Concierge"],
                "availability": "Limited",
                "address": "18 Avenue de Suffren, 15th arr., Paris"
            }
        ]
    else:
        mock_hotels = [
            {
                "name": "Grand Plaza Hotel",
                "rating": 4.5,
                "price_per_night": "$150",
                "amenities": ["WiFi", "Pool", "Gym", "Restaurant"],
                "availability": "Available"
            }
        ]
    
    return json.dumps({
        "location": location,
        "check_in": check_in,
        "check_out": check_out,
        "guests": guests,
        "hotels_found": len(mock_hotels),
        "hotels": mock_hotels,
        "note": "Mock hotel search results matching your query"
    })

def get_hotel_details(hotel_name: str) -> str:
    """
    Get detailed information about a specific hotel.
    """
    hotel_details = {
        "Hotel Eiffel Trocadéro": {
            "description": "Charming boutique hotel with stunning Eiffel Tower views from select rooms. Perfect for couples and families.",
            "check_in_time": "3:00 PM",
            "check_out_time": "11:00 AM",
            "cancellation_policy": "Free cancellation up to 24 hours before check-in",
            "reviews": {
                "total": 1247,
                "recent_comments": [
                    "Amazing location! Walked to Eiffel Tower in 5 minutes.",
                    "Staff was incredibly helpful with restaurant recommendations.",
                    "Rooms are cozy and clean with great views."
                ]
            },
            "nearby_attractions": ["Eiffel Tower (0.3 mi)", "Trocadéro Gardens (0.2 mi)", "Seine River (0.4 mi)"]
        },
        "Mercure Paris Centre Tour Eiffel": {
            "description": "Modern hotel with contemporary rooms and excellent dining options. Close to metro stations.",
            "check_in_time": "2:00 PM",
            "check_out_time": "12:00 PM",
            "cancellation_policy": "Free cancellation up to 48 hours before check-in",
            "reviews": {
                "total": 2156,
                "recent_comments": [
                    "Great value for money, clean and comfortable.",
                    "Restaurant had excellent French cuisine.",
                    "Easy access to public transportation."
                ]
            },
            "nearby_attractions": ["Eiffel Tower (0.5 mi)", "Champ de Mars (0.4 mi)", "Les Invalides (0.8 mi)"]
        },
        "Pullman Paris Tour Eiffel": {
            "description": "Luxury hotel offering panoramic views, upscale amenities, and exceptional service. Ideal for a premium experience.",
            "check_in_time": "3:00 PM",
            "check_out_time": "12:00 PM",
            "cancellation_policy": "Free cancellation up to 72 hours before check-in",
            "reviews": {
                "total": 3421,
                "recent_comments": [
                    "Rooftop bar has the best Eiffel Tower views in Paris!",
                    "Luxurious rooms with every amenity you could want.",
                    "Worth the price for the location and service."
                ]
            },
            "nearby_attractions": ["Eiffel Tower (0.2 mi)", "Seine River Cruise Dock (0.3 mi)", "Trocadéro (0.5 mi)"]
        }
    }
    
    details = hotel_details.get(hotel_name, {
        "name": hotel_name,
        "description": "Comfortable hotel with modern amenities",
        "check_in_time": "3:00 PM",
        "check_out_time": "11:00 AM",
        "cancellation_policy": "Standard cancellation policy applies",
        "reviews": {"total": 0, "recent_comments": []},
        "nearby_attractions": []
    })
    
    return json.dumps({
        "hotel_name": hotel_name,
        "details": details,
        "note": "Mock hotel details"
    })

def search_flights(origin: str, destination: str, departure_date: str, return_date: str = None, passengers: int = 1) -> str:
    """
    Search for available flights between two locations.
    """
    # Specific mock data for JFK to Paris December 15-18, 2025
    if "jfk" in origin.lower() or "new york" in origin.lower():
        if "paris" in destination.lower() or "cdg" in destination.lower():
            mock_flights = [
                {
                    "outbound": {
                        "flight_number": "AF007",
                        "airline": "Air France",
                        "departure": "December 15, 2025 at 6:30 PM",
                        "arrival": "December 16, 2025 at 8:15 AM",
                        "duration": "7h 45m",
                        "aircraft": "Boeing 777-300ER",
                        "class": "Economy",
                        "price": "$520"
                    },
                    "return": {
                        "flight_number": "AF008",
                        "airline": "Air France",
                        "departure": "December 18, 2025 at 11:00 AM",
                        "arrival": "December 18, 2025 at 2:15 PM",
                        "duration": "8h 15m",
                        "aircraft": "Airbus A350-900",
                        "class": "Economy",
                        "price": "Included"
                    },
                    "total_price": "$520",
                    "stops": "Nonstop",
                    "baggage": "1 checked bag included"
                },
                {
                    "outbound": {
                        "flight_number": "DL264",
                        "airline": "Delta",
                        "departure": "December 15, 2025 at 10:15 PM",
                        "arrival": "December 16, 2025 at 12:05 PM",
                        "duration": "7h 50m",
                        "aircraft": "Airbus A330-900neo",
                        "class": "Economy",
                        "price": "$485"
                    },
                    "return": {
                        "flight_number": "DL265",
                        "airline": "Delta",
                        "departure": "December 18, 2025 at 1:45 PM",
                        "arrival": "December 18, 2025 at 5:00 PM",
                        "duration": "8h 15m",
                        "aircraft": "Airbus A330-900neo",
                        "class": "Economy",
                        "price": "Included"
                    },
                    "total_price": "$485",
                    "stops": "Nonstop",
                    "baggage": "1 checked bag included"
                },
                {
                    "outbound": {
                        "flight_number": "UA57",
                        "airline": "United Airlines",
                        "departure": "December 15, 2025 at 5:00 PM",
                        "arrival": "December 16, 2025 at 6:50 AM",
                        "duration": "7h 50m",
                        "aircraft": "Boeing 767-400ER",
                        "class": "Economy",
                        "price": "$560"
                    },
                    "return": {
                        "flight_number": "UA58",
                        "airline": "United Airlines",
                        "departure": "December 18, 2025 at 9:30 AM",
                        "arrival": "December 18, 2025 at 12:45 PM",
                        "duration": "8h 15m",
                        "aircraft": "Boeing 787-10",
                        "class": "Economy",
                        "price": "Included"
                    },
                    "total_price": "$560",
                    "stops": "Nonstop",
                    "baggage": "1 checked bag included"
                }
            ]
        else:
            mock_flights = [{"flight_number": "XX123", "airline": "Generic Air", "price": "$400", "note": "Generic route"}]
    else:
        mock_flights = [
            {
                "outbound": {
                    "flight_number": "AA123",
                    "airline": "Generic Airlines",
                    "departure": f"{departure_date} at 9:00 AM",
                    "arrival": f"{departure_date} at 2:30 PM",
                    "duration": "5h 30m",
                    "class": "Economy",
                    "price": "$350"
                },
                "total_price": "$350",
                "stops": "Nonstop"
            }
        ]
    
    return json.dumps({
        "origin": origin,
        "destination": destination,
        "departure_date": departure_date,
        "return_date": return_date,
        "passengers": passengers,
        "flights_found": len(mock_flights),
        "flights": mock_flights,
        "note": "Mock flight search results for JFK to Paris CDG"
    })

def get_flight_details(flight_number: str) -> str:
    """
    Get detailed information about a specific flight.
    """
    mock_details = {
        "flight_number": flight_number,
        "airline": "Sky Airways",
        "aircraft": "Boeing 737-800",
        "departure": {
            "airport": "JFK International Airport",
            "terminal": "Terminal 4",
            "gate": "B23",
            "time": "08:00 AM"
        },
        "arrival": {
            "airport": "Charles de Gaulle Airport",
            "terminal": "Terminal 2E",
            "gate": "K15",
            "time": "11:30 AM local time"
        },
        "duration": "3h 30m",
        "baggage_allowance": {
            "carry_on": "1 bag (10kg)",
            "checked": "1 bag (23kg)"
        },
        "amenities": ["WiFi", "In-flight entertainment", "Meals included"]
    }
    
    return json.dumps({
        "flight_details": mock_details,
        "note": "Mock flight details"
    })

def search_activities(location: str, date: str = None, category: str = None) -> str:
    """
    Search for available activities and attractions at a destination.
    """
    # Specific mock data for Paris activities
    if "paris" in location.lower():
        all_activities = [
            {
                "name": "Eiffel Tower Summit Access",
                "category": "Sightseeing",
                "duration": "2-3 hours",
                "price": "$35",
                "rating": 4.8,
                "description": "Skip-the-line access to all three levels including the summit. Best views of Paris!",
                "availability": "Daily 9:30 AM - 11:00 PM",
                "best_time": "Early morning or sunset",
                "booking_required": True
            },
            {
                "name": "Louvre Museum Guided Tour",
                "category": "Sightseeing",
                "duration": "3 hours",
                "price": "$55",
                "rating": 4.7,
                "description": "Expert-guided tour covering masterpieces including Mona Lisa and Venus de Milo.",
                "availability": "Daily except Tuesdays, 9:00 AM entry",
                "best_time": "Morning entry recommended",
                "booking_required": True
            },
            {
                "name": "Seine River Cruise",
                "category": "Sightseeing",
                "duration": "1 hour",
                "price": "$18",
                "rating": 4.6,
                "description": "Scenic cruise past Notre-Dame, Eiffel Tower, and historic bridges.",
                "availability": "Every 30 minutes, 10:00 AM - 10:00 PM",
                "best_time": "Evening for illuminated monuments",
                "booking_required": False
            },
            {
                "name": "Musée d'Orsay Visit",
                "category": "Culture",
                "duration": "2-3 hours",
                "price": "$16",
                "rating": 4.7,
                "description": "Impressionist masterpieces in a stunning Beaux-Arts railway station.",
                "availability": "Tuesday-Sunday 9:30 AM - 6:00 PM",
                "best_time": "Weekday mornings",
                "booking_required": True
            },
            {
                "name": "Versailles Palace Day Trip",
                "category": "Culture",
                "duration": "5-6 hours",
                "price": "$75",
                "rating": 4.9,
                "description": "Explore the opulent palace and stunning gardens of Louis XIV (includes transport).",
                "availability": "Daily except Mondays, 8:00 AM departure",
                "best_time": "Full day trip",
                "booking_required": True
            },
            {
                "name": "Montmartre Walking Tour",
                "category": "Culture",
                "duration": "2.5 hours",
                "price": "$25",
                "rating": 4.6,
                "description": "Discover the artistic heart of Paris, including Sacré-Cœur and artists' square.",
                "availability": "Daily at 10:00 AM and 2:00 PM",
                "best_time": "Morning or late afternoon",
                "booking_required": False
            },
            {
                "name": "French Cooking Class",
                "category": "Culinary",
                "duration": "3 hours",
                "price": "$120",
                "rating": 4.9,
                "description": "Learn to make classic French dishes like coq au vin and crème brûlée, then enjoy your creations.",
                "availability": "Tuesday-Saturday, 10:00 AM and 6:00 PM sessions",
                "best_time": "Morning or evening sessions",
                "booking_required": True
            },
            {
                "name": "Wine & Cheese Tasting",
                "category": "Culinary",
                "duration": "1.5 hours",
                "price": "$65",
                "rating": 4.7,
                "description": "Sample French wines and artisanal cheeses with expert sommelier guidance.",
                "availability": "Daily at 5:00 PM and 7:30 PM",
                "best_time": "Evening sessions",
                "booking_required": True
            },
            {
                "name": "Food Market Tour",
                "category": "Culinary",
                "duration": "2 hours",
                "price": "$45",
                "rating": 4.6,
                "description": "Explore authentic Parisian markets and taste local specialties like cheeses, pastries, and charcuterie.",
                "availability": "Tuesday, Thursday, Saturday mornings",
                "best_time": "Morning (markets are freshest)",
                "booking_required": False
            }
        ]
        
        if category:
            activities = [act for act in all_activities if act["category"] == category]
        else:
            activities = all_activities
    else:
        activities = [
            {
                "name": "City Walking Tour",
                "category": "Sightseeing",
                "duration": "3 hours",
                "price": "$45",
                "rating": 4.7,
                "description": "Explore the historic downtown area with an expert guide",
                "availability": "Daily at 10:00 AM and 2:00 PM"
            }
        ]
    
    return json.dumps({
        "location": location,
        "date": date,
        "category": category,
        "activities_found": len(activities),
        "activities": activities,
        "note": "Mock activity search results for Paris with sightseeing, culture, and culinary options"
    })

def get_activity_details(activity_name: str) -> str:
    """
    Get detailed information about a specific activity.
    """
    # Paris-specific activity details
    activity_details_map = {
        "Eiffel Tower Summit Access": {
            "name": "Eiffel Tower Summit Access",
            "description": "Skip-the-line access to all three levels of the Eiffel Tower, including the summit. Enjoy panoramic views of Paris from 276 meters high.",
            "duration": "2-3 hours (self-guided)",
            "price": "$35 per person",
            "included": ["Skip-the-line ticket", "Access to all 3 levels", "Summit access", "Audio guide app"],
            "meeting_point": "Eiffel Tower South Pillar entrance, look for priority access line",
            "what_to_bring": ["Photo ID", "Comfortable shoes", "Camera", "Light jacket (summit can be windy)"],
            "cancellation_policy": "Free cancellation up to 24 hours in advance",
            "languages": ["English", "French", "Spanish", "German", "Italian"],
            "max_group_size": "No limit",
            "rating": 4.8,
            "reviews_count": 15234
        },
        "Louvre Museum Guided Tour": {
            "name": "Louvre Museum Guided Tour",
            "description": "Expert-guided tour of the world's largest art museum, focusing on must-see masterpieces including Mona Lisa, Venus de Milo, and Winged Victory.",
            "duration": "3 hours",
            "price": "$55 per person",
            "included": ["Skip-the-line entry", "Expert art historian guide", "Headsets for groups over 6", "Museum highlights map"],
            "meeting_point": "Glass Pyramid main entrance, look for guide with 'Louvre Tours' sign",
            "what_to_bring": ["Photo ID", "Comfortable shoes", "Camera (no flash)", "Water bottle"],
            "cancellation_policy": "Free cancellation up to 48 hours in advance",
            "languages": ["English", "French", "Spanish"],
            "max_group_size": 20,
            "rating": 4.7,
            "reviews_count": 8921
        },
        "French Cooking Class": {
            "name": "French Cooking Class",
            "description": "Hands-on cooking experience where you'll learn to prepare classic French dishes like coq au vin, ratatouille, and crème brûlée under expert chef guidance.",
            "duration": "3 hours",
            "price": "$120 per person",
            "included": ["All ingredients", "Chef instruction", "Apron and recipe booklet", "Wine pairing", "Lunch/dinner of your creations"],
            "meeting_point": "Le Chef Cooking Studio, 15 Rue du Bac, 7th arrondissement",
            "what_to_bring": ["Appetite", "Camera for food photos"],
            "cancellation_policy": "Free cancellation up to 72 hours in advance",
            "languages": ["English", "French"],
            "max_group_size": 12,
            "rating": 4.9,
            "reviews_count": 2341
        }
    }
    
    details = activity_details_map.get(activity_name, {
        "name": activity_name,
        "description": "An immersive experience that showcases the best of local culture and attractions.",
        "duration": "3 hours",
        "price": "$45 per person",
        "included": ["Professional guide", "Entry fees"],
        "meeting_point": "Central meeting location",
        "what_to_bring": ["Comfortable shoes", "Camera"],
        "cancellation_policy": "Free cancellation up to 24 hours in advance",
        "languages": ["English"],
        "max_group_size": 15,
        "rating": 4.5,
        "reviews_count": 100
    })
    
    return json.dumps({
        "activity_details": details,
        "note": "Mock activity details for Paris attractions"
    })

def confirm_booking(booking_type: str, booking_id: str, customer_info: dict) -> str:
    """
    Confirm a booking reservation.
    """
    confirmation_number = f"CONF-{booking_type.upper()}-{booking_id}"
    
    mock_confirmation = {
        "confirmation_number": confirmation_number,
        "booking_type": booking_type,
        "status": "Confirmed",
        "customer_name": customer_info.get("name", "Guest"),
        "email": customer_info.get("email", "guest@example.com"),
        "confirmation_sent": True,
        "next_steps": [
            "Check your email for booking details",
            "Arrive 30 minutes before scheduled time",
            "Bring confirmation number and valid ID"
        ]
    }
    
    return json.dumps({
        "confirmation": mock_confirmation,
        "note": "Mock booking confirmation"
    })

def check_availability(service_type: str, service_name: str, date: str, quantity: int = 1) -> str:
    """
    Check availability for hotels, flights, or activities.
    """
    # Mock availability - randomly available or limited
    availability_status = random.choice(["Available", "Available", "Limited", "Sold Out"])
    
    mock_availability = {
        "service_type": service_type,
        "service_name": service_name,
        "date": date,
        "quantity_requested": quantity,
        "status": availability_status,
        "available_slots": 8 if availability_status == "Available" else (2 if availability_status == "Limited" else 0),
        "price_per_unit": "$150",
        "last_checked": datetime.now().isoformat()
    }
    
    return json.dumps({
        "availability": mock_availability,
        "note": "Mock availability check"
    })

def process_payment(amount: float, currency: str, payment_method: dict, booking_reference: str) -> str:
    """
    Process payment for a booking.
    """
    transaction_id = f"TXN-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    mock_payment = {
        "transaction_id": transaction_id,
        "amount": amount,
        "currency": currency,
        "status": "Success",
        "payment_method": payment_method.get("type", "Credit Card"),
        "last_4_digits": payment_method.get("last_4", "****"),
        "booking_reference": booking_reference,
        "timestamp": datetime.now().isoformat(),
        "receipt_url": f"https://mock.payment.com/receipt/{transaction_id}"
    }
    
    return json.dumps({
        "payment_result": mock_payment,
        "note": "Mock payment processing - no actual transaction occurred"
    })

def validate_payment_method(payment_method: dict) -> str:
    """
    Validate payment method details.
    """
    method_type = payment_method.get("type", "credit_card")
    
    # Mock validation
    is_valid = True
    validation_messages = []
    
    if method_type == "credit_card":
        if not payment_method.get("number"):
            is_valid = False
            validation_messages.append("Card number is required")
        if not payment_method.get("expiry"):
            is_valid = False
            validation_messages.append("Expiry date is required")
        if not payment_method.get("cvv"):
            is_valid = False
            validation_messages.append("CVV is required")
    
    mock_validation = {
        "is_valid": is_valid,
        "payment_method_type": method_type,
        "validation_messages": validation_messages if not is_valid else ["Payment method is valid"],
        "supported_currencies": ["USD", "EUR", "GBP", "JPY"],
        "processing_fee": "2.5%"
    }
    
    return json.dumps({
        "validation_result": mock_validation,
        "note": "Mock payment validation"
    })
