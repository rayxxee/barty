import smtplib
from email.mime.text import MIMEText
EMAIL_ADDRESS = 'rayyanaiza74@gmail.com'
EMAIL_PASSWORD = 'vzrfmiljddqyxybr'
msg = MIMEText('Test email')
msg['Subject'] = 'Test'
msg['From'] = EMAIL_ADDRESS
msg['To'] = 'rayyanaiza74@gmail.com'
with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
    server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
    server.send_message(msg)