import ssl
import os
import requests
import time
import base64
import io
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from dotenv import load_dotenv 
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition, ContentId

# 1. SSL Fix for Mac
ssl._create_default_https_context = ssl._create_unverified_context

# 2. Setup Credentials
load_dotenv()
api_key = os.environ.get('SENDGRID_API_KEY')
OPEN_SKY_ID = os.environ.get('OPEN_SKY_ID')
OPEN_SKY_SECRET = os.environ.get('OPEN_SKY_SECRET')

def get_opensky_token():
    auth_url = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
    data = {"grant_type": "client_credentials", "client_id": OPEN_SKY_ID, "client_secret": OPEN_SKY_SECRET}
    response = requests.post(auth_url, data=data)
    return response.json().get("access_token") if response.status_code == 200 else None

# --- PROCESS ---
token = get_opensky_token()

if token:
    now_ts = int(time.time())
    day_ago_ts = now_ts - 86400 # 24 hours ago
    airport = "KLAX"
    headers = {"Authorization": f"Bearer {token}"}
    
    # Request 24 hours of data for the chart
    url = f"https://opensky-network.org/api/flights/departure?airport={airport}&begin={day_ago_ts}&end={now_ts}"
    print(f"Fetching 24h LAX data...")
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        all_flights = response.json()
        
        # A. Filter for the Table (Last 2 Hours only)
        two_hours_ago = now_ts - 7200
        recent_flights = [f for f in all_flights if f.get('firstSeen', 0) >= two_hours_ago]
        
        departure_list = []
        for f in recent_flights:
            departure_list.append({
                "airline": str((f.get('callsign') or 'N/A').strip()[:3]),
                "departure_airport": str(f.get('estDepartureAirport') or 'KLAX'),
                "arrival_airport": str(f.get('estArrivalAirport') or 'Unknown'),
                "departure_time": datetime.fromtimestamp(f.get('firstSeen', 0)).strftime('%H:%M'),
                "arrival_time": datetime.fromtimestamp(f.get('lastSeen', 0)).strftime('%H:%M')
            })

       # B. Generate Chart Data (Last 24h in 1h blocks)
        labels = []
        counts = []
        
        print("Calculating hourly counts for the chart...")
        for i in range(24, 0, -1):  
            block_seconds = 3600 
            block_end = now_ts - ((i-1) * block_seconds)
            block_start = now_ts - (i * block_seconds)
            
            # Filter flights that fall within this specific hour
            count = len([f for f in all_flights if block_start <= f.get('firstSeen', 0) < block_end])
            
            # Label every 4th hour to keep it very clean
            time_label = datetime.fromtimestamp(block_start).strftime('%H:%M') if i % 4 == 0 else ""
            
            labels.append(time_label)
            counts.append(count)
            # This will show up in your GitHub Action logs:
            if count > 0: print(f"Hour {time_label or '...'} had {count} flights")

        # C. Create the Plot (High Contrast Version)
        plt.style.use('seaborn-v0_8-muted') # Ensures a clean, modern look
        plt.figure(figsize=(10, 5))
        
        # We use a thick line and clear dots
        plt.plot(range(24), counts, marker='o', color='#1a73e8', linewidth=3, markersize=6, label='Departures')
        
        # Fill the area under the line to make it visible
        plt.fill_between(range(24), counts, color='#1a73e8', alpha=0.1)
        
        plt.xticks(range(24), labels, fontsize=10)
        plt.title(f"LAX Departures per Hour (Last 24 Hours)", fontsize=14, pad=20)
        plt.ylabel("Number of Flights", fontsize=12)
        plt.grid(True, axis='y', linestyle='--', alpha=0.3)
        
        # IMPORTANT: Ensure the background isn't transparent
        plt.gcf().set_facecolor('white')
        
        # Save to buffer
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', bbox_inches='tight', dpi=120, facecolor='white')
        img_buffer.seek(0)
        img_data = base64.b64encode(img_buffer.read()).decode()
        plt.close()

        # D. Email Setup
        formatted_now = datetime.now().strftime("%b %d, %Y - %H:%M")
        email_data = {
            "first_name": "Artem",
            "email_sent_at": formatted_now,
            "dep_count": len(departure_list),
            "departures": departure_list
        }

        message = Mail(
            from_email='artem.bratchenko044@gmail.com',
            to_emails='nova.shift1996@proton.me'
        )
        message.template_id = 'd-0563ea372a754220bb62033c862c9d5c'
        message.dynamic_template_data = email_data

        # E. Attach the Chart
        attachment = Attachment()
        attachment.file_content = FileContent(img_data)
        attachment.file_type = FileType('image/png')
        attachment.file_name = FileName('chart.png')
        attachment.disposition = Disposition('inline')
        attachment.content_id = ContentId('departure_chart') # Match this in your HTML!
        message.add_attachment(attachment)

        try:
            sg = SendGridAPIClient(api_key)
            sg.send(message)
            print(f"✅ Email with Chart Sent! Total flights in table: {len(departure_list)}")
        except Exception as e:
            print(f"❌ SendGrid Error: {e}")