"""
Test script for mail_client.py

This script tests the MailAnalyzer class by retrieving all folders with their
printable names, raw names, and message counts using connection properties
from the .env file.
"""

import os
import sys
from dotenv import load_dotenv

from cleanmail import MailAnalyzer


def main():
    """Test the MailAnalyzer get_all_folders functionality."""
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
    
    # Retrieve all folders
    try:
        print("Retrieving all folders...")
        print("This may take a while depending on the number of folders...")
        print()
        
        folders = analyzer.get_all_folders()
        
        if not folders:
            print("No folders found.")
            return
        
        print()
        print("=" * 80)
        print(f"SUCCESS: Retrieved {len(folders)} folder(s)")
        print("=" * 80)
        print()
        
        # Display folders in a formatted table
        print(f"{'Printable Name':<40} {'Raw Name':<40} {'Messages':<10}")
        print("-" * 90)
        
        for folder in folders:
            printable_name = folder['printable_name']
            raw_name = folder['raw_name']
            message_count = folder['message_count']
            
            # Truncate long names for display
            display_printable = printable_name[:37] + "..." if len(printable_name) > 40 else printable_name
            display_raw = raw_name[:37] + "..." if len(raw_name) > 40 else raw_name
            
            print(f"{display_printable:<40} {display_raw:<40} {message_count:<10}")
        
        print()
        print("=" * 80)
        print("Note: Raw names can be used with delete_emails_older_than() method")
        print("=" * 80)
        
    except Exception as e:
        print(f"ERROR: Failed to retrieve folders: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

