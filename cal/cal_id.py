import requests

def get_event_types():
    """Fetch and print your Cal.com event types with their IDs"""
    url = "https://api.cal.com/v1/event-types"
    params = {
        "apiKey": "cal_live_6a2a7c960b5816b38f3a90e8976150c5"  # Your API key here
    }
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        data = response.json()
        event_types = data.get("event_types", [])
        
        print("\n" + "="*40)
        print("YOUR CAL.COM EVENT TYPES")
        print("="*40)
        
        for event in event_types:
            print(f"Title: {event.get('title')}")
            print(f"Slug: {event.get('slug')}")
            print(f"ID: {event.get('id')}")   # ← This is the numeric ID you need
            print(f"Length: {event.get('length')} minutes")
            print("-" * 40)
    else:
        print(f"Failed to retrieve event types. Status code: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    get_event_types()
