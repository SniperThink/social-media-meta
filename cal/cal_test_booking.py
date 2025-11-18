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
        "eventTypeId": 3841623,
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


def create_booking(start_time, customer_name, customer_email, customer_notes=""):
    """
    Create a booking on Cal.com
    
    Args:
        start_time (str): Selected slot time in ISO format
        customer_name (str): Customer's full name
        customer_email (str): Customer's email address
        customer_notes (str): Optional notes
    
    Returns:
        dict: Booking response
    """
    url = "https://api.cal.com/v1/bookings"
    
    params = {
        "apiKey": "cal_live_6a2a7c960b5816b38f3a90e8976150c5"
    }
    
    payload = {
        "eventTypeId": 3841623,
        "start": start_time,
        "responses": {
            "name": customer_name,
            "email": customer_email,
            "notes": customer_notes
        },
        "timeZone": "Asia/Kolkata",
        "language": "en",
        "metadata": {}
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, params=params, json=payload, headers=headers)
    
    if response.status_code in [200, 201]:
        return {
            "status": "success",
            "message": "Booking created successfully",
            "data": response.json()
        }
    else:
        return {
            "status": "error",
            "message": f"Booking failed with status {response.status_code}",
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
    
    # Create numbered list for selection
    for idx, slot in enumerate(result["available_times"], 1):
        print(f"   [{idx}] {slot['time']} - {slot['date']}")
    
    print("\n" + "="*60)
    return result["available_times"]


def print_booking_result(result):
    """Pretty print booking result"""
    print("\n" + "="*60)
    print("📋 BOOKING RESULT")
    print("="*60)
    
    if result["status"] == "success":
        print("✅ Booking created successfully!")
        print(f"\n📧 Confirmation email sent")
        print(f"🎉 You're all set!")
    else:
        print(f"❌ {result['message']}")
        print(f"   Details: {result.get('details', 'No details available')}")
    
    print("="*60)


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


def booking_flow():
    """Interactive booking flow"""
    print("\n" + "="*60)
    print("📅 Step 1: Check Available Slots")
    print("="*60)
    
    # Step 1: Get date
    while True:
        user_input = input("\n📅 Enter date (today/tomorrow/YYYY-MM-DD): ").strip()
        start, end = parse_user_date(user_input)
        
        if start is None:
            print("❌ Invalid date format. Please try again.")
            continue
        break
    
    # Step 2: Check availability
    print(f"\n🔍 Checking availability...")
    result = check_calendar_availability(start, end)
    available_slots = print_availability(result)
    
    if not available_slots:
        print("\n❌ No slots available. Please try another date.")
        return
    
    # Step 3: Select slot
    print("\n" + "="*60)
    print("📅 Step 2: Select a Time Slot")
    print("="*60)
    
    while True:
        try:
            slot_number = input(f"\n🕐 Enter slot number (1-{len(available_slots)}): ").strip()
            slot_idx = int(slot_number) - 1
            
            if 0 <= slot_idx < len(available_slots):
                selected_slot = available_slots[slot_idx]
                break
            else:
                print(f"❌ Please enter a number between 1 and {len(available_slots)}")
        except ValueError:
            print("❌ Please enter a valid number")
    
    print(f"\n✅ Selected: {selected_slot['time']} on {selected_slot['date']}")
    
    # Step 4: Collect customer details
    print("\n" + "="*60)
    print("👤 Step 3: Your Details")
    print("="*60)
    
    name = input("\n📝 Full Name: ").strip()
    email = input("📧 Email Address: ").strip()
    notes = input("💬 Any special requirements (optional): ").strip()
    
    # Step 5: Confirm
    print("\n" + "="*60)
    print("✅ Confirm Booking")
    print("="*60)
    print(f"📅 Date & Time: {selected_slot['time']} on {selected_slot['date']}")
    print(f"👤 Name: {name}")
    print(f"📧 Email: {email}")
    if notes:
        print(f"💬 Notes: {notes}")
    print("="*60)
    
    confirm = input("\n✔️  Confirm booking? (yes/no): ").strip().lower()
    
    if confirm not in ["yes", "y"]:
        print("\n❌ Booking cancelled")
        return
    
    # Step 6: Create booking
    print("\n🔄 Creating booking...")
    booking_result = create_booking(
        start_time=selected_slot['iso_time'],
        customer_name=name,
        customer_email=email,
        customer_notes=notes
    )
    
    print_booking_result(booking_result)


if __name__ == "__main__":
    print("\n" + "="*60)
    print("🗓️  RUSHIL'S CALENDAR BOOKING SYSTEM")
    print("="*60)
    print("\nBook a 30-minute demo with Rushil Dhube")
    print("="*60)
    
    while True:
        print("\nOptions:")
        print("  1. Book a meeting")
        print("  2. Exit")
        
        choice = input("\n📋 Enter choice (1 or 2): ").strip()
        
        if choice == "1":
            booking_flow()
            
            another = input("\n🔄 Book another meeting? (yes/no): ").strip().lower()
            if another not in ["yes", "y"]:
                break
        elif choice == "2":
            break
        else:
            print("❌ Invalid choice. Please enter 1 or 2.")
    
    print("\n👋 Thank you for using the booking system!")
