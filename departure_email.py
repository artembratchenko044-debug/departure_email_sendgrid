import ssl
import os
import requests
import time
from datetime import datetime
from dotenv import load_dotenv 
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# 1. SSL Fix for Mac (as used in your previous script)
ssl._create_default_https_context = ssl._create_unverified_context

# 2. Setup Credentials
load_dotenv()
# Get the credentials
api_key = os.environ.get('SENDGRID_API_KEY')
OPEN_SKY_ID = os.environ.get('OPEN_SKY_ID')
OPEN_SKY_SECRET = os.environ.get('OPEN_SKY_SECRET')

# --- VALIDATION (Optional but Recommended) ---
if not all([api_key, OPEN_SKY_ID, OPEN_SKY_SECRET]):
    print("❌ Error: One or more API keys are missing from the .env file!")
    exit()

# 3. OpenSky Authentication Function
def get_opensky_token():
    auth_url = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
    data = {
        "grant_type": "client_credentials", 
        "client_id": OPEN_SKY_ID, 
        "client_secret": OPEN_SKY_SECRET
    }
    response = requests.post(auth_url, data=data)
    return response.json().get("access_token") if response.status_code == 200 else None

# --- MAIN PROCESS ---

# Fetch the Token
token = get_opensky_token()

if token:
    # Set Time: Last 2 Hours
    now_ts = int(time.time())
    start_ts = now_ts - 7200
    airport = "KLAX"
    
    # Request Flight Data
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://opensky-network.org/api/flights/departure?airport={airport}&begin={start_ts}&end={now_ts}"
    
    print(f"Fetching LAX departures...")
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        flights_raw = response.json()
        
        # A. Format data for the SendGrid Template (d-0563ea372a754220bb62033c862c9d5c)
        departure_list = []
        for f in flights_raw:
            callsign = (f.get('callsign') or 'N/A').strip()
            
            flight_entry = {
                "airline": str(callsign[:3]),
                "departure_airport": str(f.get('estDepartureAirport') or 'KLAX'),
                "arrival_airport": str(f.get('estArrivalAirport') or 'Unknown'),
                "departure_time": datetime.fromtimestamp(f.get('firstSeen', 0)).strftime('%H:%M'),
                "arrival_time": datetime.fromtimestamp(f.get('lastSeen', 0)).strftime('%H:%M')
            }
            departure_list.append(flight_entry)

        # B. Generate the email timestamp (matching your style)
        formatted_now = datetime.now().strftime("%b %d, %Y - %H:%M")

      # C. Create the final data structure for the email
        email_data = {
            "first_name": "Artem",
            "email_sent_at": formatted_now,
            "dep_count": len(departure_list),  # <--- Added this for your {{dep_count}} variable
            "departures": departure_list
        }

        # D. Create and Send the Email
        message = Mail(
            from_email='artem.bratchenko044@gmail.com', # Must be verified in SG
            to_emails='nova.shift1996@proton.me'
        )
        
        message.template_id = 'd-0563ea372a754220bb62033c862c9d5c'
        message.dynamic_template_data = email_data

        try:
            sg = SendGridAPIClient(api_key)
            sg_response = sg.send(message)
            print(f"✅ Success! Flight Data Sent. Status Code: {sg_response.status_code}")
            print(f"Total flights sent: {len(departure_list)}")
        except Exception as e:
            print(f"❌ SendGrid Error: {e}")
    else:
        print(f"❌ OpenSky Error: {response.status_code}")
else:
    print("❌ Could not connect to OpenSky (Auth failed)")