# /home/1.Study/1.ecom_fastapi/bazarghat/email_utils.py

# Only import what's truly needed for email utilities.
# BackgroundTasks, HTTPException, Request, status are generally used in API endpoints.
# File, Form, UploadFile are for handling file uploads in API endpoints.
# They are removed here as they don't belong in email utilities.
# If your email utility function needs to handle exceptions, import HTTPException from fastapi.
from fastapi import BackgroundTasks # Keep if send_email is designed to be run as a background task
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from dotenv import dotenv_values # Assuming 'dot_env' is a custom or specific library for .env
from pydantic import EmailStr, BaseModel
from typing import List
import jwt # Correct import name for pyjwt
from models import User # Correct relative import for User model


# Load environment variables
config_credentials = dotenv_values(".env")

# Basic check for essential environment variables
if not config_credentials.get("EMAIL") or \
   not config_credentials.get("PASSWORD") or \
   not config_credentials.get("SECRET_KEY"):
    raise ValueError("Missing EMAIL, PASSWORD, or SECRET_KEY in .env file.")


# Use ConnectionConfig for fastapi_mail
# This is the crucial part that needs to be correct:
conf = ConnectionConfig(
    MAIL_USERNAME=config_credentials["EMAIL"],
    MAIL_PASSWORD=config_credentials["PASSWORD"],
    MAIL_FROM=config_credentials["EMAIL"],
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    # THESE ARE THE NEW PARAMETERS:
    MAIL_STARTTLS=True,  # <--- THIS MUST BE HERE INSTEAD OF MAIL_TLS
    MAIL_SSL_TLS=False,  # <--- THIS MUST BE HERE INSTEAD OF MAIL_SSL
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
    # Ensure there are NO other MAIL_TLS or MAIL_SSL lines below this
    # and no typos in the new names.
)

fastmail = FastMail(conf)


async def send_verification_email(email_to: EmailStr, instance: User):
    """
    Sends a verification email to the user.

    Args:
        email_to (EmailStr): The email address of the recipient.
        instance (User): The User instance for whom the email is being sent.
    """
    token_data = {
        "id": instance.id,  # Corrected to string key
        "username": instance.username,
        # Consider adding an expiry time to your token for security:
        # "exp": datetime.utcnow() + timedelta(minutes=30)
    }

    # Ensure SECRET_KEY is a string. dotenv_values returns strings.
    token = jwt.encode(token_data, config_credentials["SECRET_KEY"], algorithm="HS256")

    template = f"""
        <!DOCTYPE html>
        <html >
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #f5f5f5;
                    margin: 0;
                    padding: 0;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #fff;
                    border-radius: 5px;
                    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);                
                }}
                h1 {{
                    color: #333;
                    font-size: 24px;
                    margin-bottom: 20px;
                }}
                p {{
                    color: #666;
                    font-size: 16px;
                    margin-bottom: 20px;
                }}
                .button {{
                    display: inline-block;
                    padding: 10px 20px;
                    background-color: #007BFF;
                    color: #fff;
                    text-decoration: none;
                    border-radius: 5px;
                }}
                .button:hover {{
                    background-color: #0056b3;                          
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Account Verification</h1>
                <p>Click the button below to verify your account:</p>
                <a href="https://e-com-fastapi.onrender.com/verify/{token}" class="button">Verify Account</a>
            </div>
        </body>
        </html>
    """
    message = MessageSchema(
        subject="BazarGhat Account Verification",
        # recipients expects a list of strings, so [email_to]
        recipients=[email_to],
        body=template,
        subtype="html"
    )
    await fastmail.send_message(message)
    # The return value from send_email is not typically used for client response,
    # as it's a background task. The caller will handle API response.
    # return {"status": "success"} # This return is usually for the background task itself, not the API endpoint.