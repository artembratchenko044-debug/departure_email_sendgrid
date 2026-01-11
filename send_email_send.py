import ssl
import os
from datetime import datetime  # New import for time
from dotenv import load_dotenv 
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# Mac SSL Fix
ssl._create_default_https_context = ssl._create_unverified_context

load_dotenv()
api_key = os.environ.get('SENDGRID_API_KEY')


# 1. Generate the timestamp
# %b = Month name, %d = Day, %Y = Year, %H:%M = Time
now = datetime.now()
formatted_date = now.strftime("%b %d, %Y - %H:%M")

# 2. Your original list of items
items = [
    {
        "title": "Leather Jacket",
        "price": "150.00",
        "image_url": "http://cdn.mcauto-images-production.sendgrid.net/954c252fedab403f/f812833d-a1d7-4e7f-b5dd-8607415f078b/104x104.png"
    },
    {
        "title": "Blue Jeans",
        "price": "50.00",
        "image_url": "http://cdn.mcauto-images-production.sendgrid.net/954c252fedab403f/f812833d-a1d7-4e7f-b5dd-8607415f078b/104x104.png"
    }
]

# 2. Calculate the Math
subtotal = 0
for item in items:
    subtotal += float(item['price'])  # Add each price to the subtotal

taxes = subtotal * 0.10               # 10% tax
grand_total = subtotal + taxes        # Final total

# 3. Create the final JSON structure for SendGrid
# We use f-strings to ensure the numbers show 2 decimal places (e.g., 20.00)
order_data = {
    "first_name": "Artem",
    "email_sent_at": formatted_date, # New variable
    "items": items,
    "subtotal": f"{subtotal:.2f}",
    "taxes": f"{taxes:.2f}",
    "grand_total": f"{grand_total:.2f}"
}

# 4. Create the email message
message = Mail(
    from_email='artem.bratchenko044@gmail.com',
    to_emails='nova.shift1996@proton.me'
)

message.template_id = 'd-e82e9372dc534144b82ef9596d6329fe'
message.dynamic_template_data = order_data

try:
    sg = SendGridAPIClient(api_key)
    response = sg.send(message)
    print(f"Order Email Sent! Status Code: {response.status_code}")
except Exception as e:
    print(f"Error: {e}")