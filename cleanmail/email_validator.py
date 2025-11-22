"""
Email validation utilities for IMAP operations.

This module provides validation functions to prevent IMAP command injection
and ensure email addresses are safe to use in IMAP queries.
"""

import re


class EmailValidationError(ValueError):
    """Custom exception for email validation errors."""
    pass


class EmailValidator:
    """Validates email addresses for safe use in IMAP operations."""
    
    # RFC 5322 compliant email regex (simplified but safe)
    EMAIL_PATTERN = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )
    
    # Characters that could be used for IMAP command injection
    DANGEROUS_CHARS = ['"', '\\', '\r', '\n', '\x00']
    
    # Maximum email length (RFC 5321)
    MAX_EMAIL_LENGTH = 254
    
    @classmethod
    def validate_email_for_imap(cls, email: str) -> str:
        """
        Validate and sanitize an email address for safe use in IMAP commands.
        
        This function prevents IMAP command injection by:
        1. Validating the email format
        2. Checking for dangerous characters
        3. Enforcing length limits
        
        Args:
            email: The email address to validate
            
        Returns:
            The validated email address (normalized to lowercase)
            
        Raises:
            EmailValidationError: If the email address is invalid or unsafe
        """
        if not isinstance(email, str):
            raise EmailValidationError(
                f"Email must be a string, got {type(email).__name__}"
            )
        
        # Strip whitespace
        email = email.strip()
        
        # Check length
        if len(email) == 0:
            raise EmailValidationError("Email address cannot be empty")
        
        if len(email) > cls.MAX_EMAIL_LENGTH:
            raise EmailValidationError(
                f"Email address too long (max {cls.MAX_EMAIL_LENGTH} characters)"
            )
        
        # Check for dangerous characters that could be used for IMAP injection
        dangerous_found = [char for char in cls.DANGEROUS_CHARS if char in email]
        if dangerous_found:
            # Show printable representation of dangerous chars
            dangerous_repr = ', '.join(
                repr(char) if char.isprintable() else f'\\x{ord(char):02x}'
                for char in dangerous_found
            )
            raise EmailValidationError(
                f"Email address contains invalid characters: {dangerous_repr}"
            )
        
        # Validate email format
        if not cls.EMAIL_PATTERN.match(email):
            raise EmailValidationError(
                f"Invalid email address format: {email}"
            )
        
        # Normalize to lowercase for consistency
        return email.lower()
    
    @classmethod
    def is_valid_email(cls, email: str) -> bool:
        """
        Check if an email address is valid without raising an exception.
        
        Args:
            email: The email address to check
            
        Returns:
            True if the email is valid, False otherwise
        """
        try:
            cls.validate_email_for_imap(email)
            return True
        except EmailValidationError:
            return False
    
    @classmethod
    def validate_app_password(cls, password: str, min_length: int = 8, max_length: int = 100) -> str:
        """
        Validate an app password for basic security requirements.
        
        Args:
            password: The app password to validate
            min_length: Minimum password length (default: 8)
            max_length: Maximum password length (default: 100)
            
        Returns:
            The validated password
            
        Raises:
            EmailValidationError: If the password is invalid
        """
        if not isinstance(password, str):
            raise EmailValidationError(
                f"Password must be a string, got {type(password).__name__}"
            )
        
        password = password.strip()
        
        if len(password) == 0:
            raise EmailValidationError("App password cannot be empty")
        
        if len(password) < min_length:
            raise EmailValidationError(
                f"App password must be at least {min_length} characters long"
            )
        
        if len(password) > max_length:
            raise EmailValidationError(
                f"App password must be at most {max_length} characters long"
            )
        
        return password

