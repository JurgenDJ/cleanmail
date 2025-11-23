import email
import imaplib
import re
from datetime import datetime, timedelta
from email.utils import parseaddr
from bs4 import BeautifulSoup
from typing import Optional, List, Any

import pandas as pd

from cleanmail.email_validator import EmailValidator, EmailValidationError


class MailAnalyzer:
    def __init__(self, email_address, mail_password, mail_server):
        self.email_address = email_address
        self.mail_password = mail_password
        self.mail_server = mail_server
        # Fetch and cache folder list once during initialization
        self._folders = self.__fetch_folders()
        self.bin_folder = self.__determine_bin_folder()
        self.archive_folder = self.__determine_archive_folder()

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

    def __fetch_folders(self) -> List[bytes]:
        """
        Fetch the folder list from the IMAP server.
        
        Returns:
            List of folder bytes as returned by mail.list()
        
        Raises:
            Exception: If connection fails or listing fails
        """
        mail = self.connect()
        try:
            result, folders = mail.list()
            if result != "OK":
                raise Exception("Could not list folders")
            return folders
        finally:
            mail.logout()

    def __find_folder_by_names(self, valid_folder_names: List[str], error_message: str) -> str:
        """
        Common method to find a folder by matching against a list of valid folder names.
        Uses the cached folder list from initialization.
        
        Args:
            valid_folder_names: List of folder names to match against
            error_message: Error message to raise if folder is not found
        
        Returns:
            The folder name (quoted if it contains spaces, for OVH compatibility)
        
        Raises:
            Exception: If folder is not found
        """
        folders = self._folders

        for folder in folders:
            # Decode the folder
            decoded_folder = folder.decode()

            # Extract the folder name from the string
            # The folder name is the part between the last "/" and the end
            folder_name = decoded_folder.split(' "/" ')[-1].strip('"')

            # Match the folder name exactly
            if folder_name in valid_folder_names:
                # For OVH and servers with spaces in folder names, we need to quote it
                # Extract the quoted mailbox name from LIST response
                # Match the quoted mailbox name at the end
                match = re.search(r'"([^"]+)"\s*$', decoded_folder)
                if match:
                    # Return quoted version for OVH compatibility
                    full_path = match.group(1)
                    # If folder name has spaces, return it quoted (OVH requires this)
                    if ' ' in full_path:
                        return f'"{full_path}"'
                    return full_path
                # Fallback: quote if it has spaces
                if ' ' in folder_name:
                    return f'"{folder_name}"'
                return folder_name

        self._print_folder_list(folders)
        raise Exception(error_message)

    def __determine_bin_folder(self) -> str:
        return self.__find_folder_by_names(
            [
                "Trash",
                "[Gmail]/Bin",
                "[Gmail]/Trash",
                "[Yahoo]/Bin",
                "[Yahoo]/Trash",
                "Deleted Items",
            ],
            "Could not find Bin or Trash folder"
        )

    def __determine_archive_folder(self) -> str:
        return self.__find_folder_by_names(
            [
                "Archive",
                "Archief",
            ],
            "Could not find Archive or Archief folder"
        )

    def connect(self) -> imaplib.IMAP4_SSL:
        """Create a fresh IMAP connection"""
        mail = imaplib.IMAP4_SSL(self.mail_server)
        mail.login(self.email_address, self.mail_password)
        return mail

    def count_messages(self, foldername: str) -> int:
        """
        Count the number of messages in a given folder.
        
        Args:
            foldername: The name of the folder (raw_name format, unquoted)
        
        Returns:
            The number of messages in the folder (int). Returns 0 if folder selection fails.
        """
        mail = self.connect()
        
        try:
            # Format folder name for SELECT: quote if it has spaces (for OVH and similar servers)
            formatted_foldername = foldername
            if ' ' in foldername:
                formatted_foldername = f'"{foldername}"'
            
            # Select folder to get message count (readonly=True to avoid modifications)
            status, data = mail.select(formatted_foldername, readonly=True)
            if status == 'OK':
                return int(data[0])
            else:
                # If selection fails, return 0
                return 0
        finally:
            mail.logout()

    def get_all_folders(self, progress_callback=None) -> List[dict]:
        """
        Retrieve all folders with their printable names, raw names, and message counts.
        Uses the cached folder list from initialization.
        
        Args:
            progress_callback: Optional callback function for progress updates.
                Called as progress_callback(current_processed, total_folders).
        
        Returns:
            List of dictionaries, each containing:
            - 'printable_name': Human-readable folder name (str)
            - 'raw_name': Folder name that can be used in prone_emails_older_than (str, unquoted)
            - 'message_count': Number of messages in the folder (int)
        
        Raises:
            Exception: If connection fails
        """
        # Use cached folder list instead of calling mail.list() again
        folders = self._folders
        
        folder_info_list = []
        total_folders = len(folders)
        
        for idx, folder in enumerate(folders):
            # Decode the folder
            decoded_folder = folder.decode()
            
            # Extract the folder name from the string
            # The folder name is the part between the last "/" and the end
            folder_name = decoded_folder.split(' "/" ')[-1].strip('"')
            
            # Extract the full path from the LIST response for raw_name
            # Match the quoted mailbox name at the end
            match = re.search(r'"([^"]+)"\s*$', decoded_folder)
            if match:
                # Use the full path as raw_name (unquoted, matching prone_emails_older_than format)
                raw_name = match.group(1)
            else:
                # Fallback: use folder_name
                raw_name = folder_name
            
            # Use count_messages() to get the message count
            message_count = self.count_messages(raw_name)
            
            folder_info_list.append({
                'printable_name': folder_name,
                'raw_name': raw_name,
                'message_count': message_count
            })
            
            # Call progress callback if provided
            if progress_callback:
                progress_callback(idx + 1, total_folders)
        
        return folder_info_list

    @staticmethod
    def chunk(array: List[Any], chunk_size: int) -> List[List[Any]]:
        """Split an array into chunks of a specified size."""
        return [array[i : i + chunk_size] for i in range(0, len(array), chunk_size)]

    def get_sender_statistics(self, progress_callback=None, max_batches: Optional[int] = None) -> pd.DataFrame:
        """Analyze recent emails and return a DataFrame with sender information
        
        Args:
            progress_callback: Optional callback function for progress updates
            max_batches: Optional limit on the number of batches (500 mails per batch) to analyze. If None, all batches are processed.
        
        Returns:
            DataFrame with sender statistics
        """
        mail = self.connect()

        mail.select("INBOX")
        _, messages = mail.uid("search", None, "ALL")

        message_ids = messages[0].split()

        sender_data = {}
        batch_size = 500
        
        # Calculate total messages, capping at max_batches * batch_size if max_batches is set
        if max_batches is not None:
            total_messages = min(len(message_ids), max_batches * batch_size)
        else:
            total_messages = len(message_ids)
        processed_messages = 0
        batch_count = 0
        for batch_ids in self.chunk(message_ids, batch_size):
            if max_batches is not None and batch_count >= max_batches:
                break
            batch_count += 1
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

    def _move_message_uids(self, mail: imaplib.IMAP4_SSL, message_uids: List[bytes], destination_folder: str, mark_as_deleted: bool = True, progress_callback=None, total_messages: int = None) -> int:
        """
        Helper method to move messages by their UIDs to a destination folder.
        
        Args:
            mail: Active IMAP connection
            message_uids: List of message UIDs (bytes) to move
            destination_folder: Folder to move messages to (bin or archive)
            mark_as_deleted: If True, mark messages as deleted and expunge. If False, just copy.
            progress_callback: Optional callback function for progress updates.
                Called as progress_callback(current_processed, total_messages).
            total_messages: Total number of messages for progress tracking. If None, uses len(message_uids).
        
        Returns:
            The number of emails moved.
        """
        if not message_uids:
            return 0
        
        # Use provided total_messages or fall back to len(message_uids)
        if total_messages is None:
            total_messages = len(message_uids)
        
        # Process emails in small batches for better performance
        # OVH's IMAP server works with quoted folder names and small batches
        batch_size = 50
        total_copied = 0
        
        for batch_start in range(0, len(message_uids), batch_size):
            batch_uids = message_uids[batch_start:batch_start + batch_size]
            batch_num = batch_start // batch_size + 1
            total_batches = (len(message_uids) + batch_size - 1) // batch_size
            
            print(f"Processing batch {batch_num} of {total_batches} ({len(batch_uids)} emails)...")
            
            # Decode UIDs
            uid_strings = [uid.decode() for uid in batch_uids]
            uid_list = ','.join(uid_strings)
            
            # Batch fetch sequence numbers for all UIDs in this batch
            result, data = mail.uid("FETCH", uid_list, "(UID)")
            if result != "OK":
                raise Exception(f"Failed to fetch sequence numbers for batch: {result}")
            
            # Parse sequence numbers from FETCH response
            # Format: b'1 (UID 12345)', b'2 (UID 12346)', etc.
            seq_nums = []
            for item in data:
                if isinstance(item, tuple):
                    # Skip the data part, we only need the header
                    continue
                if isinstance(item, bytes):
                    # Parse: b'1 (UID 12345)'
                    parts = item.decode().split()
                    if parts:
                        seq_nums.append(parts[0])
            
            if len(seq_nums) != len(batch_uids):
                raise Exception(f"Mismatch: got {len(seq_nums)} sequence numbers for {len(batch_uids)} UIDs")
            
            # Batch COPY: try copying all at once, fall back to individual if needed
            seq_list = ','.join(seq_nums)
            result, response = mail.copy(seq_list, destination_folder)
            
            if result != "OK":
                # Fall back to individual copies if batch fails
                print("Batch COPY failed, falling back to individual copies...")
                for seq_num, uid in zip(seq_nums, uid_strings):
                    result, response = mail.copy(seq_num, destination_folder)
                    if result != "OK":
                        raise Exception(f"Failed to copy email UID {uid} (seq {seq_num}) to {destination_folder}: {result} {response}")
            
            # Only mark as deleted and expunge if this is a delete operation
            if mark_as_deleted:
                # Batch STORE: mark all as deleted at once
                result, response = mail.uid("STORE", uid_list, '+FLAGS', '\\Deleted')
                if result != "OK":
                    raise Exception(f"Failed to mark emails as deleted: {result} {response}")
            
            total_copied += len(batch_uids)
            
            # Call progress callback if provided
            if progress_callback:
                progress_callback(total_copied, total_messages)
            
            # Expunge every 50 emails to keep memory usage down (only if deleting)
            if mark_as_deleted and total_copied % 50 == 0:
                try:
                    mail.expunge()
                except Exception as e:
                    # If expunge fails, continue - we'll expunge at the end
                    print(f"Warning: Expunge failed at {total_copied} emails: {e}")
        
        # Final expunge at the end (only if deleting)
        if mark_as_deleted:
            try:
                mail.expunge()
            except Exception as e:
                print(f"Warning: Final expunge failed: {e}")
        
        return total_copied

    def _delete_message_uids(self, mail: imaplib.IMAP4_SSL, message_uids: List[bytes]) -> int:
        """
        Helper method to delete messages by their UIDs.
        Moves messages to the bin folder and marks them as deleted.
        
        Args:
            mail: Active IMAP connection
            message_uids: List of message UIDs (bytes) to delete
        
        Returns:
            The number of emails moved to the bin.
        """
        return self._move_message_uids(mail, message_uids, self.bin_folder, mark_as_deleted=True)

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
        
        try:
            mail.select("INBOX", readonly=False)
            # Use UID SEARCH to get UIDs (which remain stable after deletions)
            _, messages = mail.uid("SEARCH", None, f'FROM "{sender_email}"')
            if not messages[0]:
                return 0

            message_uids = messages[0].split()
            if not message_uids:
                return 0
            
            total_copied = self._delete_message_uids(mail, message_uids)
            return total_copied
        finally:
            mail.close()

    def prone_emails_older_than(self, foldername: str, days_ago: int, action: str = "delete", progress_callback=None) -> int:
        """
        Prune (delete or archive) emails older than a specified number of days from a given folder.
        
        Args:
            foldername: The name of the folder to search in (e.g., "INBOX")
            days_ago: Number of days ago as threshold (e.g., 30 means prune emails older than 30 days)
            action: Either "delete" to move to bin folder or "archive" to move to archive folder (default: "delete")
            progress_callback: Optional callback function for progress updates.
                Called as progress_callback(current_processed, total_messages).
        
        Returns:
            The number of emails moved.
        
        Raises:
            ValueError: If days_ago is negative or action is not "delete" or "archive"
        """
        if days_ago < 0:
            raise ValueError("days_ago must be a non-negative integer")
        
        if action not in ["delete", "archive"]:
            raise ValueError(f'action must be either "delete" or "archive", got "{action}"')
        
        # Determine destination folder based on action
        if action == "delete":
            destination_folder = self.bin_folder
            mark_as_deleted = True
        else:  # action == "archive"
            destination_folder = self.archive_folder
            mark_as_deleted = False
        
        # Calculate the threshold date
        threshold_date = datetime.now() - timedelta(days=days_ago)
        # Format date for IMAP: DD-MMM-YYYY (e.g., "01-Jan-2024")
        imap_date = threshold_date.strftime("%d-%b-%Y")
        
        # Format folder name: quote if it has spaces (for OVH and similar servers)
        formatted_foldername = foldername
        if ' ' in foldername:
            formatted_foldername = f'"{foldername}"'
        
        mail = self.connect()
        selected = False
        
        try:
            mail.select(formatted_foldername, readonly=False)
            selected = True
            # Use UID SEARCH with SENTBEFORE to find messages older than the threshold date
            _, messages = mail.uid("SEARCH", None, f'SENTBEFORE "{imap_date}"')
            if not messages[0]:
                return 0
            
            message_uids = messages[0].split()
            if not message_uids:
                return 0
            
            total_messages = len(message_uids)
            total_copied = self._move_message_uids(mail, message_uids, destination_folder, mark_as_deleted, progress_callback, total_messages)
            return total_copied
        finally:
            # Use close() only if we successfully selected a folder, otherwise use logout()
            if selected:
                try:
                    mail.close()
                except Exception:
                    mail.logout()
            else:
                mail.logout()

    def empty_bin_folder(self, progress_callback=None) -> int:
        """
        Permanently delete all emails in the bin/trash folder.
        
        Args:
            progress_callback: Optional callback function for progress updates.
                Called as progress_callback(current_deleted, total_messages).
        
        Returns:
            The number of emails permanently deleted.
        
        Raises:
            Exception: If connection fails or folder selection fails
        """
        mail = self.connect()
        selected = False
        
        try:
            # Format folder name for SELECT: unquote if already quoted, then quote if it has spaces
            # (for OVH and similar servers)
            unquoted_foldername = self.bin_folder.strip('"')
            formatted_foldername = unquoted_foldername
            if ' ' in unquoted_foldername:
                formatted_foldername = f'"{unquoted_foldername}"'
            
            # Select the bin folder
            status, data = mail.select(formatted_foldername, readonly=False)
            if status != "OK":
                raise Exception(f"Failed to select bin folder: {status}")
            selected = True
            
            # Get all message UIDs in the bin folder
            _, messages = mail.uid("SEARCH", None, "ALL")
            if not messages[0]:
                return 0
            
            message_uids = messages[0].split()
            if not message_uids:
                return 0
            
            total_messages = len(message_uids)
            
            # Process in batches for better performance
            batch_size = 50
            total_deleted = 0
            
            for batch_start in range(0, len(message_uids), batch_size):
                batch_uids = message_uids[batch_start:batch_start + batch_size]
                batch_num = batch_start // batch_size + 1
                total_batches = (len(message_uids) + batch_size - 1) // batch_size
                
                print(f"Processing batch {batch_num} of {total_batches} ({len(batch_uids)} emails)...")
                
                # Decode UIDs
                uid_strings = [uid.decode() for uid in batch_uids]
                uid_list = ','.join(uid_strings)
                
                # Mark messages as deleted
                result, response = mail.uid("STORE", uid_list, '+FLAGS', '\\Deleted')
                if result != "OK":
                    raise Exception(f"Failed to mark emails as deleted: {result} {response}")
                
                total_deleted += len(batch_uids)
                
                # Call progress callback if provided
                if progress_callback:
                    progress_callback(total_deleted, total_messages)
                
                # Expunge every 50 emails to keep memory usage down
                if total_deleted % 50 == 0:
                    try:
                        mail.expunge()
                    except Exception as e:
                        # If expunge fails, continue - we'll expunge at the end
                        print(f"Warning: Expunge failed at {total_deleted} emails: {e}")
            
            # Final expunge to permanently delete all marked messages
            try:
                mail.expunge()
            except Exception as e:
                print(f"Warning: Final expunge failed: {e}")
            
            return total_deleted
            
        finally:
            # Use close() only if we successfully selected a folder, otherwise use logout()
            if selected:
                try:
                    mail.close()
                except Exception:
                    mail.logout()
            else:
                mail.logout()

