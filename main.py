import math
import os

import streamlit as st
from dotenv import load_dotenv
from cleanmail import MailAnalyzer, EmailValidator, EmailValidationError
from cleanmail.styling import apply_custom_styles


def analyze_emails_component(analyzer):
    max_batches = st.number_input(
        "Limit number of Batches to Analyze (500 emails per batch)",
        min_value=1,
        value=None,
        step=1,
        help="Optional: Limit the number of batches to analyze. Leave empty to analyze all emails.",
        key="max_batches_input"
    )
    
    if st.button("Analyze Emails"):
        progress_bar = st.progress(0)
        status_text = st.empty()

        def update_progress(current, total):
            progress = current / total
            progress_bar.progress(progress)
            warn_for_large_inboxes = f"""
                    
            Whoa, that's a pretty large inbox! This may take a while...
            We are estimating the analysis to take about {math.floor((total/50)/60)} minutes
            
            _Usually we have seen that more than 40% of the emails are usually from the top five senders_
            So after one cleanup, the next time will be blazing fast!
            """
            status_text.markdown(
                f"""
                Processing email {current}/{total}
                {warn_for_large_inboxes if total > 3000 else ""}
                """
            )

        st.session_state.email_data = analyzer.get_sender_statistics(
            progress_callback=update_progress,
            max_batches=max_batches if max_batches else None
        )

        progress_bar.empty()
        status_text.empty()
        st.rerun()


@st.fragment
def sender_list_for_cleanup_component():
    df = st.session_state.email_data

    with st.form("cleanup_form", border=False):
        # Create display columns with cleanup checkbox as first column
        display_df = df[["Sender Name", "Email", "Count", "Unsubscribe Link"]].copy()
        display_df["should_clean_up"] = False
        # Reorder columns to put checkbox first
        display_df = display_df[
            ["should_clean_up", "Sender Name", "Email", "Count", "Unsubscribe Link"]
        ]

        # Create the interactive dataframe
        edited_df = st.data_editor(
            display_df,
            column_config={
                "should_clean_up": st.column_config.CheckboxColumn(
                    "Clean up?",
                    help="Select to clean up emails from this sender",
                    default=False,
                ),
                "Email": st.column_config.TextColumn(
                    "Email",
                    help="Sender email address",
                    disabled=True,  # Make read-only to prevent manual editing
                ),
                "Unsubscribe Link": st.column_config.LinkColumn(
                    "Unsubscribe link",
                    help="Click to unsubscribe",
                    display_text="🔗 Unsubscribe",
                    validate="https?://.*",
                ),
                "Count": st.column_config.NumberColumn(
                    "Mail count", help="Number of emails from this sender"
                ),
            },
            hide_index=True,
            use_container_width=True,
            height=500,
        )

        if st.form_submit_button("🧹 Clean Selected Emails", use_container_width=True):
            sender_ids_to_be_cleaned = {
                row["Email"]
                for _, row in edited_df.iterrows()
                if row["should_clean_up"]
            }
            if not sender_ids_to_be_cleaned:
                st.toast("No senders selected for cleanup!")
            else:
                st.write(
                    f"Cleaning up emails from: {', '.join(sender_ids_to_be_cleaned)}"
                )
                st.toast(
                    "This may take a while depending on the number of emails. Please be patient!"
                )
                analyzer = MailAnalyzer(
                    st.session_state.email_address, st.session_state.mail_password, st.session_state.server
                )
                # TODO: move to bulk delete
                for sender in sender_ids_to_be_cleaned:
                    try:
                        # Validate email before deletion (additional safety check)
                        validated_sender = EmailValidator.validate_email_for_imap(sender)
                        deleted_count = analyzer.delete_emails_from_sender(validated_sender)
                        st.toast(f"Moved {deleted_count} emails from {sender} to the bin!")
                    except EmailValidationError as e:
                        st.error(f"Invalid email address '{sender}': {e}")
                        st.toast(f"Skipped invalid email address: {sender}")
                        print(f"Invalid email address '{sender}': {e}")
                    except Exception as e:
                        st.error(f"Error deleting emails from {sender}: {e}")
                        print(f"Error deleting emails from {sender}: {e}")
                        st.toast(f"Failed to delete emails from {sender}")
                st.session_state.email_data = None
                st.rerun()


def inbox_cleanup_component():
    analyzer = MailAnalyzer(
        st.session_state.email_address, st.session_state.mail_password, st.session_state.server
    )
    # Show "Analyze Emails" button only if sender_stats is not populated
    if st.session_state.email_data is None:
        st.markdown("""
        ### Inbox Cleanup

        This tool will **analyze your inbox** and show you a list of senders along with the number of emails from each.

        1. **Select** the senders you'd like to clean up by checking the box next to their email address.
        2. Click **'Clean Selected Emails'** to move all emails from the selected senders to the bin.

        🚨 *This process might take some time depending on your inbox size. you can limit the number of batches to analyze.*
        """)

        analyze_emails_component(analyzer)
        return

    sender_list_for_cleanup_component()


def trash_bin_component():
    """Component for trash bin management functionality."""
    if not (st.session_state.email_address and st.session_state.mail_password and st.session_state.server):
        st.info("Please authenticate using your credentials in the sidebar to use this feature.")
        return

    analyzer = MailAnalyzer(
        st.session_state.email_address, st.session_state.mail_password, st.session_state.server
    )

    # Get unquoted bin folder name for count_messages()
    bin_folder_unquoted = analyzer.bin_folder.strip('"')
    
    # Get message count in trash bin
    try:
        trash_count = analyzer.count_messages(bin_folder_unquoted)
    except Exception as e:
        trash_count = 0
        st.warning(f"Could not retrieve trash bin message count: {e}")

    st.markdown(f"""
    ### Trash Bin Management
    
    This tool allows you to permanently delete all emails in your trash/bin folder.
    
    **Current trash bin:** {trash_count} message{'s' if trash_count != 1 else ''}
    
    ⚠️ **Warning:** This action cannot be undone! All emails in the trash bin will be permanently deleted.
    """)
    
    if st.button("🗑️ Empty Trash Bin", use_container_width=True, type="primary"):
        st.warning("⚠️ This will permanently delete all emails in your trash bin. This action cannot be undone!")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            def update_progress(current, total):
                progress = current / total if total > 0 else 0
                progress_bar.progress(progress)
                status_text.markdown(
                    f"""
                    Deleting email {current}/{total}
                    """
                )
            
            deleted_count = analyzer.empty_bin_folder(progress_callback=update_progress)
            
            if deleted_count > 0:
                st.success(f"Successfully deleted {deleted_count} emails from the trash bin!")
                st.toast(f"Deleted **{deleted_count}** emails from trash bin!")
                st.rerun()
            else:
                st.info("The trash bin is already empty.")
        except Exception as e:
            st.error(f"Error emptying trash bin: {e}")
            st.toast(f"Failed to empty trash bin: {e}")
            print(f"Error emptying trash bin: {e}")
        finally:
            progress_bar.empty()
            status_text.empty()


def load_folders(analyzer):
    """Load folders and store in session state."""
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        def update_progress(current, total):
            progress = current / total if total > 0 else 0
            progress_bar.progress(progress)
            status_text.markdown(
                f"""
                Counting messages in folder {current}/{total}
                """
            )
        
        folders = analyzer.get_all_folders(progress_callback=update_progress)
        
        if folders:
            # Sort folders by message count (descending)
            folders = sorted(folders, key=lambda x: x['message_count'], reverse=True)
            st.session_state.folders = folders
        else:
            st.session_state.folders = []
    except Exception as e:
        st.error(f"Error loading folders: {e}")
        st.toast(f"Failed to load folders: {e}")
        print(f"Error loading folders: {e}")
        st.session_state.folders = []
    finally:
        progress_bar.empty()
        status_text.empty()


def folder_pruning_component():
    """Component for folder pruning functionality."""
    if not (st.session_state.email_address and st.session_state.mail_password and st.session_state.server):
        st.info("Please authenticate using your credentials in the sidebar to use this feature.")
        return

    analyzer = MailAnalyzer(
        st.session_state.email_address, st.session_state.mail_password, st.session_state.server
    )

    col1, col2 = st.columns([1,1])
    with col1:
        st.markdown("""
        ### Folder Pruning
        
        This tool will help you manage and prune email folders by deleting old messages.
        
        """
        )
    with col2:
        # Get list of folders
        if st.button("🔄 Refresh Folder List", use_container_width=True):
            load_folders(analyzer)
            st.rerun()
        prune_action = st.selectbox(
            "Choose what to do with pruned emails:",
            options=["Delete", "Move to Archive"],
            key="prune_action_selectbox"
        )
        st.session_state.prune_action = prune_action
        st.write(f'Pruning emails will be moved to: {analyzer.bin_folder if prune_action == "Delete" else analyzer.archive_folder}')
    
    # Initialize folders in session state if not present
    if 'folders' not in st.session_state:
        st.session_state.folders = None
    
    # Get folders from session state
    folders = st.session_state.folders
    
    if folders is None:
        st.info("Click 'Refresh Folder List' to load folders.")
        return
    
    if not folders:
        st.warning("No folders found.")
        return
    
    st.markdown("#### Folders and Pruning Actions")
            
    # Create table header using columns
    header_cols = st.columns([5, 1, 5])
    with header_cols[0]:
        st.markdown("**Folder Name**")
    with header_cols[1]:
        st.markdown("**Messages**")
    with header_cols[2]:
        st.markdown("**Prune Messages older than:**")
    
    st.markdown("---")
    
    # Create table rows with dropdowns and buttons in the same row
    for idx, folder in enumerate(folders):
            if folder['printable_name'] == analyzer.archive_folder and st.session_state.prune_action == "Move to Archive":
                continue
            if folder['printable_name'] == analyzer.bin_folder:
                continue

            folder_name = folder['printable_name']
            message_count = folder['message_count']
            
            # Create columns for this row: folder name, count, and prune dropdown
            cols = st.columns([5,1,5])
            
            # First column: Folder name
            with cols[0]:
                st.markdown(folder_name)
            
            # Second column: Message count
            with cols[1]:
                st.markdown(f"`{message_count}`")
            
            # Third column: Dropdown and button
            with cols[2]:
                prune_folder_fragment(analyzer, folder['raw_name'], folder_name)
            # Add a subtle divider between rows (optional)
            if idx < len(folders) - 1:
                st.markdown("<hr style='margin: 8px 0;'>", unsafe_allow_html=True)

@st.fragment
def prune_folder_fragment(analyzer: MailAnalyzer, folder_raw_name: str, folder_display_name: str):
    """Fragment for pruning buttons in a folder row."""
    container = st.container(horizontal=True, horizontal_alignment="left")
    
    # Get the prune action from session state (default to "Delete" if not set)
    prune_action = st.session_state.get("prune_action", "Delete")
    
    # Map UI action to method action parameter
    action_map = {
        "Delete": "delete",
        "Move to Archive": "archive"
    }
    action = action_map.get(prune_action, "delete")
    
    # Define action verbs for messages
    action_verb = "Deleting" if action == "delete" else "Archiving"
    action_past_verb = "deleted" if action == "delete" else "archived"
    action_noun = "deleted" if action == "delete" else "moved to archive"
    
    # Define days options
    days_options = [30, 90, 150, 365, 730]
    
    for days in days_options:
        button_key = f"action_{folder_raw_name}_{days}"
        if container.button(f"{days} d", key=button_key):
            st.info(f"Pruning emails older than {days} days from '{folder_display_name}'...")
            st.toast(f"Pruning emails older than {days} days. This may take a while...")
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                def update_progress(current, total):
                    progress = current / total if total > 0 else 0
                    progress_bar.progress(progress)
                    status_text.markdown(
                        f"""
                        {action_verb} email {current}/{total}
                        """
                    )
                
                processed_count = analyzer.prone_emails_older_than(
                    folder_raw_name, 
                    days, 
                    action=action,
                    progress_callback=update_progress
                )
                
                if processed_count > 0:
                    st.success(f"Successfully {action_past_verb} {processed_count} emails older than {days} days from '{folder_display_name}'!")
                    st.toast(f"{processed_count} emails {action_noun}!")
                else:
                    st.info(f"No emails found older than {days} days in '{folder_display_name}'.")
                
                # Refresh the folder list to show updated counts
                st.rerun()
                
            except Exception as e:
                st.error(f"Error pruning emails: {e}")
                st.toast(f"Failed to prune emails: {e}")
                print(f"Error pruning emails from {folder_display_name}: {e}")
            finally:
                progress_bar.empty()
                status_text.empty()

def sidebar_component():
    st.sidebar.header("Authentication")

    with st.sidebar:
        with st.form("authentication_form"):
            server_input = st.text_input(
                "Imap Server",
                value=st.session_state.server,
                type="default",
            )
            email_input = st.text_input(
                "Email Address",
                value=st.session_state.email_address,
                type="default",
            )
            password_input = st.text_input(
                "Password",
                value=st.session_state.mail_password,
                type="password",
            )

            col1, col2 = st.columns(2)
            with col1:
                connect_clicked = st.form_submit_button("Connect", use_container_width=True)
            with col2:
                save_clicked = st.form_submit_button("💾 Save", use_container_width=True)

            # Handle Connect button
            if connect_clicked:
                if email_input and password_input:
                    # Update session state with current form values
                    st.session_state.server = server_input
                    st.session_state.email_address = email_input
                    st.session_state.mail_password = password_input
                    
                    analyzer = MailAnalyzer(
                        email_input, password_input, server_input
                    )
                    test_conn = analyzer.connect()
                    if test_conn:
                        test_conn.logout()
                        st.success("Successfully connected to Gmail!")
                        st.session_state.email_data = None
                        st.rerun()
            
            # Handle Save button
            if save_clicked:
                # Use form input values directly, not session state
                email_to_save = email_input if email_input else st.session_state.email_address
                password_to_save = password_input if password_input else st.session_state.mail_password
                server_to_save = server_input if server_input else st.session_state.server
                
                if email_to_save and server_to_save:
                    try:
                        with open(".env", "w") as f:
                            if server_to_save:
                                f.write(f"IMAP_SERVER={server_to_save}\n")
                            f.write(f"EMAIL_ADDRESS={email_to_save}\n")
                            f.write(f"MAIL_PASSWORD={password_to_save}\n")
                        st.sidebar.success("Settings saved to .env!")
                        st.toast("Settings saved to .env")
                        # Update session state after successful save
                        st.session_state.server = server_to_save
                        st.session_state.email_address = email_to_save
                        st.session_state.mail_password = password_to_save
                    except Exception as e:
                        st.sidebar.error(f"Failed to save settings: {e}")
                else:
                    st.sidebar.warning("Please fill in email and password before saving")

        # Add a button to star the repository
        st.sidebar.markdown(
            """
            ---

            Credits: Forked from [BharatKalluri/cleanmail](https://github.com/BharatKalluri/cleanmail)
            
            """
        )


def main():
    st.set_page_config(page_title="CleanMail", layout="wide")
    
    # Load defaults from .env file if it exists
    load_dotenv()
    
    # Use session state to store email credentials and sender stats
    # Load defaults from .env file, falling back to None if not set
    session_defaults = {
        "server": os.getenv("IMAP_SERVER"),
        "email_address": os.getenv("EMAIL_ADDRESS"),
        "mail_password": os.getenv("MAIL_PASSWORD"),
        "email_data": None,
    }
    for key, default_value in session_defaults.items():
        st.session_state.setdefault(key, default_value)

    # Sidebar for authentication
    sidebar_component()


    if st.session_state.email_address and st.session_state.mail_password and st.session_state.server:
        # Create tabs for different functionalities
        tab1, tab2, tab3 = st.tabs(["Inbox Cleanup", "Folder Pruning", "Trash Bin"])
        
        with tab1:
            inbox_cleanup_component()
        
        with tab2:
            folder_pruning_component()
        
        with tab3:
            trash_bin_component()
    else:
        st.info("Please authenticate using your credentials in the sidebar.")
        st.markdown(
            """
        ### Instructions:
        1. Enter your Gmail or Yahoo address
        2. Enter your [Gmail App Password](https://myaccount.google.com/apppasswords) or [Yahoo App Password](https://help.yahoo.com/kb/SLN15241.html)
        3. Select the number of recent emails to analyze
        4. Click Connect to start analyzing your inbox
        
        **Note:** _This app requires a App Password, not your regular password_!
        """
        )


if __name__ == "__main__":
    main()
