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

def get_busiest_hour(flights, time_key):
    if not flights: return "N/A"
    hour_counts = {}
    for f in flights:
        hour = datetime.fromtimestamp(f.get(time_key, 0)).strftime('%I %p')
        hour_counts[hour] = hour_counts.get(hour, 0) + 1
    return max(hour_counts, key=hour_counts.get)

# --- START PROCESS ---
token = get_opensky_token()
if not token:
    print("❌ Auth failed")
    exit()

headers = {"Authorization": f"Bearer {token}"}
airport = "KLAX"
now_ts = int(time.time())

# --- 1. GET DATA FOR CHART (Last 24 Hours) ---
day_ago_ts = now_ts - 86400
url_24h = f"https://opensky-network.org/api/flights/departure?airport={airport}&begin={day_ago_ts}&end={now_ts}"
flights_24h = requests.get(url_24h, headers=headers).json()

# --- 2. GET DATA FOR YESTERDAY SUMMARY ---
today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
yesterday_start = today_start - timedelta(days=1)
y_start_ts = int(yesterday_start.timestamp())
y_end_ts = int(today_start.timestamp()) - 1

y_deps = requests.get(f"https://opensky-network.org/api/flights/departure?airport={airport}&begin={y_start_ts}&end={y_end_ts}", headers=headers).json()
y_arrs = requests.get(f"https://opensky-network.org/api/flights/arrival?airport={airport}&begin={y_start_ts}&end={y_end_ts}", headers=headers).json()

# --- 3. GENERATE THE CHART ---
labels, counts = [], []
for i in range(24, 0, -1):
    b_start = now_ts - (i * 3600)
    b_end = now_ts - ((i-1) * 3600)
    count = len([f for f in flights_24h if b_start <= f.get('firstSeen', 0) < b_end])
    labels.append(datetime.fromtimestamp(b_start).strftime('%H:%M') if i % 4 == 0 else "")
    counts.append(count)

plt.figure(figsize=(10, 5))
plt.plot(range(24), counts, marker='o', color='#1a73e8', linewidth=3)
plt.xticks(range(24), labels)
plt.title("LAX Hourly Departures")
plt.gcf().set_facecolor('white')
img_buffer = io.BytesIO()
plt.savefig(img_buffer, format='png', facecolor='white')
img_buffer.seek(0)
img_data = base64.b64encode(img_buffer.read()).decode()
plt.close()

# --- 4. PREPARE DATA FOR SENDGRID ---
two_hours_ago = now_ts - 7200
recent_deps = [f for f in flights_24h if f.get('firstSeen', 0) >= two_hours_ago]

departure_list = []
for f in recent_deps:
    departure_list.append({
                "airline": str((f.get('callsign') or 'N/A').strip()[:3]),
                # Match your template tags exactly:
                "departure_time": datetime.fromtimestamp(f.get('firstSeen', 0)).strftime('%H:%M'),
                "arrival_time": datetime.fromtimestamp(f.get('lastSeen', 0)).strftime('%H:%M'),
                "from": str(f.get('estDepartureAirport') or 'KLAX'),
                "arrival": str(f.get('estArrivalAirport') or 'Unknown')
            })

email_data = {
    "first_name": "Artem",
    "email_sent_at": datetime.now().strftime("%b %d, %H:%M"),
    "dep_count": len(departure_list),
    "departures": departure_list,
    "yesterday_date": yesterday_start.strftime("%A, %b %d"),
    "y_total_deps": len(y_deps),
    "y_total_arrs": len(y_arrs),
    "y_busiest_dep_hour": get_busiest_hour(y_deps, 'firstSeen'),
    "y_busiest_arr_hour": get_busiest_hour(y_arrs, 'lastSeen')
}

# --- 5. SEND EMAIL ---
message = Mail(from_email='artem.bratchenko044@gmail.com', to_emails='nova.shift1996@proton.me')
message.template_id = 'd-0563ea372a754220bb62033c862c9d5c'
message.dynamic_template_data = email_data

attachment = Attachment()
attachment.file_content, attachment.file_type, attachment.file_name = FileContent(img_data), FileType('image/png'), FileName('chart.png')
attachment.disposition, attachment.content_id = Disposition('inline'), ContentId('departure_chart')
message.add_attachment(attachment)

try:
    sg = SendGridAPIClient(api_key)
    sg.send(message)
    print("✅ Success! Email sent with chart and stats.")
except Exception as e:
    print(f"❌ Error: {e}")


# --- 6. SEND ONESIGNAL PUSH ---
onesignal_api_key = os.environ.get('ONESIGNAL_API_KEY')
onesignal_app_id = "a10f1409-7129-4703-810f-dfcf43c7efb7"

push_header = {
    "Content-Type": "application/json; charset=utf-8",
    "Authorization": f"Basic {onesignal_api_key}"
}

# Values to be injected
count_val = str(len(departure_list))
time_val = datetime.now().strftime("%b %d, %H:%M")

push_payload = {
    "app_id": onesignal_app_id,
    "template_id": "05a11ed6-b5f1-42c3-9491-cd63443cbb38",
    "included_segments": ["Total Subscriptions"],
    # OneSignal uses 'data' for substitution variables in many template setups
    "custom_data": {
        "dep_count": count_val,
        "push_sent_at": time_val
    }
}

try:
    push_response = requests.post(
        "https://onesignal.com/api/v1/notifications",
        headers=push_header,
        json=push_payload
    )
    # Logging the response help us debug if it still fails
    print(f"OneSignal Response: {push_response.text}") 
except Exception as e:
    print(f"❌ Push error: {e}")