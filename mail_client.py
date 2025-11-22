import email
import imaplib
import re
from email.utils import parseaddr
from bs4 import BeautifulSoup
from typing import Optional, List, Any

import pandas as pd

from email_validator import EmailValidator, EmailValidationError


class MailAnalyzer:
    def __init__(self, email_address, mail_password, mail_server):
        self.email_address = email_address
        self.mail_password = mail_password
        self.mail_server = mail_server
        self.bin_folder = self.__determine_bin_folder()

    @staticmethod
    def _print_folder_list(folders: List[bytes]) -> None:
        """Print a readable list of folder names from IMAP folder list."""
        folder_names = []
        for folder in folders:
            decoded_folder = folder.decode()
            folder_name = decoded_folder.split(' "/" ')[-1].strip('"')
            folder_names.append(folder_name)
        
        print("Could not find Bin or Trash folder. Available folders:")
        for folder_name in folder_names:
            print(f"  - {folder_name}")

    def __determine_bin_folder(self) -> str:
        mail = self.connect()
        if not mail:
            raise Exception("Connection failed")

        result, folders = mail.list()
        if result != "OK":
            raise Exception("Could not list folders")

        for folder in folders:
            # Decode the folder
            decoded_folder = folder.decode()

            # Extract the folder name from the string
            # The folder name is the part between the last "/" and the end
            folder_name = decoded_folder.split(' "/" ')[-1].strip('"')

            # Match the folder name exactly
            if folder_name in [
                "Trash",
                "[Gmail]/Bin",
                "[Gmail]/Trash",
                "[Yahoo]/Bin",
                "[Yahoo]/Trash",
                "Deleted Items",
            ]:
                return folder_name

        self._print_folder_list(folders)
        raise Exception("Could not find Bin or Trash folder")

    # def __get_imap_url(self) -> str:
    #     endpoints = {
    #         "yahoo.com": "imap.mail.yahoo.com",
    #         "gmail.com": "imap.gmail.com",
    #     }
    #     # Extract domain from email address
    #     domain = self.email_address.lower().split("@")[-1]

    #     # Match domain to known IMAP endpoints
    #     if domain in endpoints:
    #         return endpoints[domain]
    #     else:
    #         raise ValueError(f"Unsupported email domain: {domain}")

    def connect(self) -> imaplib.IMAP4_SSL:
        """Create a fresh IMAP connection"""
        mail = imaplib.IMAP4_SSL(self.mail_server)
        mail.login(self.email_address, self.mail_password)
        return mail

    @staticmethod
    def chunk(array: List[Any], chunk_size: int) -> List[List[Any]]:
        """Split an array into chunks of a specified size."""
        return [array[i : i + chunk_size] for i in range(0, len(array), chunk_size)]

    def get_sender_statistics(self, progress_callback=None) -> pd.DataFrame:
        """Analyze recent emails and return a DataFrame with sender information"""
        mail = self.connect()

        mail.select("INBOX")
        _, messages = mail.uid("search", None, "ALL")

        message_ids = messages[0].split()

        sender_data = {}
        total_messages = len(message_ids)

        batch_size = 500
        processed_messages = 0
        for batch_ids in self.chunk(message_ids, batch_size):
            if progress_callback:
                processed_messages += len(batch_ids)
                progress_callback(processed_messages, total_messages)

            _, msg_data = mail.uid(
                "fetch", ",".join([el.decode() for el in batch_ids]), "(RFC822)"
            )

            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    email_message = email.message_from_bytes(response_part[1])
                    raw_data = response_part[1]

                    sender = email_message["from"]
                    sender_name, sender_addr = parseaddr(sender)

                    if sender_addr:
                        if sender_addr not in sender_data:
                            sender_data[sender_addr] = {
                                "Sender Name": sender_name,
                                "Email": sender_addr,
                                "Count": 0,
                                "Raw Data": raw_data,
                                "Unsubscribe Link": MailAnalyzer.get_unsubscribe_link(
                                    raw_data
                                ),
                            }
                        sender_data[sender_addr]["Count"] += 1

        mail.logout()

        if not sender_data:
            return pd.DataFrame()

        df = pd.DataFrame(sender_data.values())
        return df.sort_values("Count", ascending=False).reset_index(drop=True)

    @staticmethod
    def get_unsubscribe_link(raw_email_data) -> Optional[str]:
        """Extract unsubscribe link from email data"""
        try:
            email_message = email.message_from_bytes(raw_email_data)

            list_unsubscribe = email_message.get("List-Unsubscribe")
            if list_unsubscribe:
                urls = re.findall(
                    r'https?://[^\s<>"]+|www\.[^\s<>"]+', list_unsubscribe
                )
                if urls:
                    return urls[0]

            for part in email_message.walk():
                if part.get_content_type() == "text/html":
                    html_body = part.get_payload(decode=True).decode()
                    soup = BeautifulSoup(html_body, "html.parser")
                    for a_tag in soup.find_all(
                        "a", string=re.compile("unsubscribe", re.IGNORECASE)
                    ):
                        return a_tag.get("href")

                    unsubscribe_patterns = [
                        r'https?://[^\s<>"]+(?:unsubscribe|opt[_-]out)[^\s<>"]*',
                        r'https?://[^\s<>"]+(?:click\.notification)[^\s<>"]*',
                    ]
                    for pattern in unsubscribe_patterns:
                        matches = re.findall(pattern, html_body, re.IGNORECASE)
                        if matches:
                            return matches[0]
            return None
        except Exception as e:
            return None

    def delete_emails_from_sender(self, sender_email) -> int:
        """
        Delete emails from a specific sender by moving them to the bin folder.
        
        Args:
            sender_email: The email address of the sender. This is validated
                         to prevent IMAP command injection.
        
        Returns:
            The number of emails moved to the bin.
            
        Raises:
            EmailValidationError: If the sender_email is invalid or unsafe.
        """
        # Validate email address to prevent IMAP command injection
        sender_email = EmailValidator.validate_email_for_imap(sender_email)
        
        mail = self.connect()

        mail.select("INBOX", readonly=False)
        _, messages = mail.uid("SEARCH", None, f'FROM "{sender_email}"')
        if not messages[0]:
            mail.logout()
            return 0

        message_uids = messages[0].split()
        mail.uid("COPY", b",".join(message_uids).decode("utf-8"), self.bin_folder)

        mail.close()
        return len(message_uids)
