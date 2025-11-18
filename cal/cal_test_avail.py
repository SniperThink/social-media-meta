import requests
from datetime import datetime, timedelta


def check_calendar_availability(start_time, end_time):
    """
    Check available slots on Cal.com calendar
    
    Args:
        start_time (str): Start time in ISO format (e.g., "2025-11-09T00:00:00+05:30")
        end_time (str): End time in ISO format (e.g., "2025-11-09T23:59:00+05:30")
    
    Returns:
        dict: API response with available slots in readable format
    """
    url = "https://api.cal.com/v1/slots"
    
    params = {
        "apiKey": "cal_live_6a2a7c960b5816b38f3a90e8976150c5",
        "eventTypeSlug": "30-min-demo",
        "usernameList": "rushil-dhube-6hkusj",
        "startTime": start_time,
        "endTime": end_time,
        "timeZone": "Asia/Kolkata"
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, params=params, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        return format_availability(data)
    else:
        return {
            "error": f"API call failed with status {response.status_code}",
            "details": response.text
        }


def format_availability(api_response):
    """
    Format API response into readable time slots
    
    Args:
        api_response (dict): Raw API response
    
    Returns:
        dict: Formatted response with readable times
    """
    slots = api_response.get("slots", {})
    
    if not slots:
        return {
            "status": "no_slots",
            "message": "No available slots found",
            "available_times": []
        }
    
    formatted_slots = []
    
    for date, time_slots in slots.items():
        for slot in time_slots:
            time_str = slot.get("time", "")
            if time_str:
                # Parse ISO time
                dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                
                # Convert to IST and format
                readable_date = dt.strftime("%A, %B %d, %Y")
                readable_time = dt.strftime("%I:%M %p IST")
                
                formatted_slots.append({
                    "date": readable_date,
                    "time": readable_time,
                    "iso_time": time_str
                })
    
    return {
        "status": "success",
        "total_slots": len(formatted_slots),
        "available_times": formatted_slots
    }


def print_availability(result):
    """Pretty print availability results"""
    print("\n" + "="*60)
    print("📅 CALENDAR AVAILABILITY CHECK")
    print("="*60)
    
    if "error" in result:
        print(f"❌ Error: {result['error']}")
        print(f"   Details: {result['details']}")
        return
    
    if result["status"] == "no_slots":
        print("❌ No available slots found")
        return
    
    print(f"✅ Found {result['total_slots']} available slots\n")
    
    current_date = None
    for slot in result["available_times"]:
        if slot["date"] != current_date:
            current_date = slot["date"]
            print(f"\n📆 {current_date}")
            print("-" * 60)
        
        print(f"   ⏰ {slot['time']}")
    
    print("\n" + "="*60)


def parse_user_date(user_input):
    """
    Parse user input and return start and end times
    
    Args:
        user_input (str): User input like "today", "tomorrow", "2025-11-09"
    
    Returns:
        tuple: (start_time, end_time) in ISO format
    """
    user_input = user_input.strip().lower()
    
    if user_input == "today":
        date = datetime.now()
    elif user_input == "tomorrow":
        date = datetime.now() + timedelta(days=1)
    else:
        # Try to parse as YYYY-MM-DD
        try:
            date = datetime.strptime(user_input, "%Y-%m-%d")
        except ValueError:
            return None, None
    
    date_str = date.strftime("%Y-%m-%d")
    start_time = f"{date_str}T00:00:00+05:30"
    end_time = f"{date_str}T23:59:00+05:30"
    
    return start_time, end_time


if __name__ == "__main__":
    print("\n" + "="*60)
    print("🗓️  RUSHIL'S CALENDAR AVAILABILITY CHECKER")
    print("="*60)
    print("\nOptions:")
    print("  • Type 'today' for today's availability")
    print("  • Type 'tomorrow' for tomorrow's availability")
    print("  • Type a date in YYYY-MM-DD format (e.g., 2025-11-09)")
    print("  • Type 'exit' to quit")
    print("="*60)
    
    while True:
        user_input = input("\n📅 Enter date: ").strip()
        
        if user_input.lower() == "exit":
            print("\n👋 Goodbye!")
            break
        
        start, end = parse_user_date(user_input)
        
        if start is None:
            print("❌ Invalid date format. Please use 'today', 'tomorrow', or YYYY-MM-DD format.")
            continue
        
        print(f"\n🔍 Checking availability for {user_input}...")
        result = check_calendar_availability(start, end)
        print_availability(result)
