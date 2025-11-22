import math
import os

import streamlit as st
from dotenv import load_dotenv
from mail_client import MailAnalyzer
from email_validator import EmailValidator, EmailValidationError
from styling import apply_custom_styles


def analyze_emails_component(analyzer):
    max_batches = st.number_input(
        "Max Batches to Analyze (500 emails per batch)",
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
                    except Exception as e:
                        st.error(f"Error deleting emails from {sender}: {e}")
                        st.toast(f"Failed to delete emails from {sender}")
                st.session_state.email_data = None
                st.rerun()


def email_cleanup_component():
    analyzer = MailAnalyzer(
        st.session_state.email_address, st.session_state.mail_password, st.session_state.server
    )
    # Show "Analyze Emails" button only if sender_stats is not populated
    if st.session_state.email_data is None:
        analyze_emails_component(analyzer)
        return

    sender_list_for_cleanup_component()


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
    
    # Apply custom styles globally (must be called early)
    apply_custom_styles()

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

    # Title row with refresh button
    title_col, reset_col = st.columns([7, 1])
    with title_col:
        st.title("CleanMail")
    with reset_col:
        if st.button("🔄 Reset", use_container_width=True):
            st.session_state.email_data = None
            st.rerun()

    if st.session_state.email_address and st.session_state.mail_password:
        email_cleanup_component()
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
