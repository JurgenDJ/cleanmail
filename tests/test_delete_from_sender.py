"""
Test script for mail_client.py

This script tests the MailAnalyzer class by attempting to delete all emails
from a specific sender (notification@hoplr.com) using connection properties
from the .env file.
"""

import argparse
import os
import sys
from dotenv import load_dotenv

from cleanmail import MailAnalyzer, EmailValidator, EmailValidationError


def main():
    """Test the MailAnalyzer delete functionality."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Test script for MailAnalyzer - delete emails from a specific sender"
    )
    parser.add_argument(
        "sender_email",
        help="Email address of the sender whose emails should be deleted"
    )
    args = parser.parse_args()
    
    # Load environment variables from .env file
    load_dotenv()
    
    # Get connection properties from .env file
    email_address = os.getenv("EMAIL_ADDRESS")
    mail_password = os.getenv("MAIL_PASSWORD")
    mail_server = os.getenv("IMAP_SERVER")
    
    # Check if all required environment variables are set
    if not email_address:
        print("ERROR: EMAIL_ADDRESS not found in .env file")
        sys.exit(1)
    
    if not mail_password:
        print("ERROR: MAIL_PASSWORD not found in .env file")
        sys.exit(1)
    
    if not mail_server:
        print("ERROR: IMAP_SERVER not found in .env file")
        sys.exit(1)
    
    print("Loaded connection properties:")
    print(f"  Email: {email_address}")
    print(f"  Server: {mail_server}")
    print(f"  Password: {'*' * len(mail_password)}")
    print()
    
    # Get sender email from command-line argument
    test_sender = args.sender_email
    
    # Validate the sender email before proceeding
    try:
        validated_sender = EmailValidator.validate_email_for_imap(test_sender)
        print(f"Sender email validated: {validated_sender}")
    except EmailValidationError as e:
        print(f"ERROR: Invalid sender email '{test_sender}': {e}")
        sys.exit(1)
    
    print()
    
    # Create MailAnalyzer instance
    try:
        print("Creating MailAnalyzer instance...")
        analyzer = MailAnalyzer(email_address, mail_password, mail_server)
        print("✓ MailAnalyzer instance created successfully")
        print()
    except Exception as e:
        print(f"ERROR: Failed to create MailAnalyzer instance: {e}")
        sys.exit(1)
    
    # Test connection
    try:
        print("Testing connection...")
        mail = analyzer.connect()
        mail.logout()
        print("✓ Connection successful")
        print()
    except Exception as e:
        print(f"ERROR: Failed to connect to mail server: {e}")
        sys.exit(1)
    
    # Attempt to delete emails from the test sender
    try:
        print(f"Attempting to delete all emails from: {validated_sender}")
        print("This may take a while depending on the number of emails...")
        print()
        
        deleted_count = analyzer.delete_emails_from_sender(validated_sender)
        
        print()
        print("=" * 60)
        print(f"SUCCESS: Moved {deleted_count} email(s) from {validated_sender} to bin")
        print("=" * 60)
        
    except EmailValidationError as e:
        print(f"ERROR: Email validation failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to delete emails: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

