"""
CleanMail - A tool to quickly clean up your email inbox!

This package provides utilities for analyzing and cleaning email inboxes
via IMAP connections.
"""

from cleanmail.mail_client import MailAnalyzer
from cleanmail.email_validator import EmailValidator, EmailValidationError

__version__ = "0.1.0"
__all__ = ["MailAnalyzer", "EmailValidator", "EmailValidationError"]

