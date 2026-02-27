import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv
import os
import sys

load_dotenv()
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')

if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
    print("Email or password not loaded!")
    sys.exit(1)

msg = MIMEText('Test email 587')
msg['Subject'] = 'Test 587'
msg['From'] = EMAIL_ADDRESS
msg['To'] = EMAIL_ADDRESS

print("Testing port 587 (STARTTLS)...")
try:
    with smtplib.SMTP('smtp.gmail.com', 587, timeout=10) as server:
        server.set_debuglevel(1)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        print("Success on 587!")
except Exception as e:
    print(f"Error on 587: {e}")

print("Testing port 465 (SMTP_SSL)...")
msg['Subject'] = 'Test 465'
try:
    with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=10) as server:
        server.set_debuglevel(1)
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        print("Success on 465!")
except Exception as e:
    print(f"Error on 465: {e}")
