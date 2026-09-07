import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD

def send_otp_email(to_email: str, otp_code: str) -> bool:
    """
    Sends an OTP verification email to the user.
    If SMTP variables are not configured or connection fails,
    it falls back to printing the OTP to the console logs.
    """
    if not all([SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD]):
        print(f"\n==========================================")
        print(f"[OTP Verification Fallback] Code for {to_email} is: {otp_code}")
        print(f"==========================================\n")
        return False
        
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = to_email
        msg['Subject'] = "Documind - Verify Your Email Account"
        
        body = f"""Hi there,

Thank you for signing up for Documind!

Your 6-digit email verification code is:

{otp_code}

This code is valid for 10 minutes. Please enter it on the signup screen to verify your email and complete your registration.

If you did not request this code, please ignore this email.

Best regards,
The Documind Team
"""
        msg.attach(MIMEText(body, 'plain'))
        
        # Connect and send email
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, to_email, msg.as_string())
        server.quit()
        
        print(f"Verification email successfully sent to {to_email}.")
        return True
    except Exception as e:
        print(f"Error sending verification email: {e}")
        # Log to terminal as a fallback so local dev / test suites don't break
        print(f"\n==========================================")
        print(f"[OTP Verification Fallback] Code for {to_email} is: {otp_code}")
        print(f"==========================================\n")
        return False
