"""
Test script for mail_client.py

This script tests the MailAnalyzer class by attempting to delete all emails
older than a specified number of days from a given folder using connection
properties from the .env file.
"""

import argparse
import os
import sys
from dotenv import load_dotenv

from cleanmail import MailAnalyzer


def main():
    """Test the MailAnalyzer prone_emails_older_than functionality."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Test script for MailAnalyzer - delete emails older than a specified number of days"
    )
    parser.add_argument(
        "foldername",
        help="Name of the folder to search in (e.g., 'INBOX')"
    )
    parser.add_argument(
        "days_ago",
        type=int,
        help="Number of days ago as threshold (e.g., 30 means delete emails older than 30 days)"
    )
    args = parser.parse_args()
    
    # Validate days_ago parameter
    if args.days_ago < 0:
        print(f"ERROR: days_ago must be a non-negative integer, got {args.days_ago}")
        sys.exit(1)
    
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
    
    # Get parameters from command-line arguments
    test_foldername = args.foldername
    test_days_ago = args.days_ago
    
    print(f"Test parameters:")
    print(f"  Folder: {test_foldername}")
    print(f"  Days ago: {test_days_ago}")
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
    
    # Attempt to delete emails older than the specified threshold
    try:
        print(f"Attempting to delete emails older than {test_days_ago} days from folder: {test_foldername}")
        print("This may take a while depending on the number of emails...")
        print()
        
        deleted_count = analyzer.prone_emails_older_than(test_foldername, test_days_ago, action="delete")
        
        print()
        print("=" * 60)
        print(f"SUCCESS: Moved {deleted_count} email(s) older than {test_days_ago} days from '{test_foldername}' to bin")
        print("=" * 60)
        
    except ValueError as e:
        print(f"ERROR: Invalid parameter: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to delete emails: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

