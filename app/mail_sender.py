import smtplib
import streamlit as st
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

APP_ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
ROOT_ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(ROOT_ENV_PATH)
load_dotenv(APP_ENV_PATH, override=True)

class MailSender:
    def __init__(self):
        self._smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self._smtp_port = int(os.getenv("SMTP_PORT", 587))
        self._sender_email = os.getenv("SENDER_EMAIL")
        # Clean app password by removing spaces
        raw_password = os.getenv("SENDER_PASSWORD", "")
        self._sender_password = raw_password.replace(" ", "") if raw_password else ""
    
    @property
    def smtp_server(self):
        return self._smtp_server
    
    @smtp_server.setter
    def smtp_server(self, value):
        self._smtp_server = value
    
    @property
    def smtp_port(self):
        return self._smtp_port
    
    @smtp_port.setter
    def smtp_port(self, value):
        self._smtp_port = value
    
    @property
    def sender_email(self):
        return self._sender_email
    
    @sender_email.setter
    def sender_email(self, value):
        self._sender_email = value
    
    @property
    def sender_password(self):
        return self._sender_password
    
    @sender_password.setter
    def sender_password(self, value):
        # Automatically remove spaces from app password
        self._sender_password = value.replace(" ", "") if value else value
    
    def send_email(self, recipient_email: str, subject: str, body: str) -> tuple[bool, str]:
        """Send email and return (success_status, message)"""
        try:
            recipient_email = (recipient_email or "").strip()
            
            # Validate inputs
            if not all([self.sender_email, self.sender_password, recipient_email]):
                missing = []
                if not self.sender_email: missing.append("sender_email")
                if not self.sender_password: missing.append("sender_password")
                if not recipient_email: missing.append("recipient_email")
                return False, f"Missing: {', '.join(missing)}"
            
            # Check password length for Gmail
            if self.smtp_server == "smtp.gmail.com" and len(self.sender_password) != 16:
                return False, f"Invalid password length: {len(self.sender_password)}. Should be 16 characters."
            
            # Create message
            msg = MIMEMultipart()
            msg["From"] = self.sender_email
            msg["To"] = recipient_email
            msg["Subject"] = subject
            
            # Attach body
            msg.attach(MIMEText(body, "plain"))

            # Send email based on configured port
            if int(self.smtp_port) == 465:
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=30) as server:
                    server.login(self.sender_email, self.sender_password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30) as server:
                    server.ehlo()
                    if int(self.smtp_port) == 587:
                        server.starttls()
                        server.ehlo()
                    server.login(self.sender_email, self.sender_password)
                    server.send_message(msg)
            
            return True, f"Email sent successfully to {recipient_email}"
        
        except smtplib.SMTPAuthenticationError as e:
            return False, f"Authentication failed. Error: {str(e)}"
        except smtplib.SMTPException as e:
            return False, f"SMTP error: {str(e)}"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"
    
    def validate_credentials(self) -> tuple[bool, str]:
        """Validate email credentials without sending an email"""
        try:
            # Check if credentials exist
            if not self.sender_email:
                return False, "No sender email configured"
            
            if not self.sender_password:
                return False, "No password configured"
            
            # Check password length for Gmail
            if self.smtp_server == "smtp.gmail.com":
                if len(self.sender_password) != 16:
                    return False, f"Invalid password length: {len(self.sender_password)} characters. Google App Passwords must be exactly 16 characters. Your password has {len(self.sender_password)} characters."
            
            # Test SMTP connection
            if int(self.smtp_port) == 465:
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=30) as server:
                    server.login(self.sender_email, self.sender_password)
            else:
                with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30) as server:
                    server.ehlo()
                    if int(self.smtp_port) == 587:
                        server.starttls()
                        server.ehlo()
                    server.login(self.sender_email, self.sender_password)
            
            return True, "Credentials validated successfully! Your email configuration is working."
        
        except smtplib.SMTPAuthenticationError as e:
            error_msg = str(e)
            if "535" in error_msg:
                return False, "Authentication failed. This usually means:\n1. You're using your regular Gmail password instead of an App Password\n2. Your App Password has spaces (remove them)\n3. The App Password is incorrect\n\nGenerate a new App Password at: https://myaccount.google.com/apppasswords"
            return False, f"Authentication failed: {error_msg}"
        except smtplib.SMTPException as e:
            return False, f"SMTP connection error: {str(e)}"
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    def get_config_status(self) -> dict:
        """Get current configuration status"""
        return {
            "smtp_server": self.smtp_server,
            "smtp_port": self.smtp_port,
            "sender_email": self.sender_email,
            "has_password": bool(self.sender_password),
            "password_length": len(self.sender_password) if self.sender_password else 0,
            "is_valid_for_gmail": len(self.sender_password) == 16 if self.smtp_server == "smtp.gmail.com" else True
        }
    
    def clear_credentials(self):
        """Clear all email credentials"""
        self._sender_email = None
        self._sender_password = None
        return True, "Credentials cleared successfully"