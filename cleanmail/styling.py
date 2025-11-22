"""Styling configuration for Streamlit application."""

import streamlit as st


def apply_custom_styles():
    """
    Apply custom CSS styles to make input fields always visible.
    This function should be called early in the app initialization.
    """
    st.markdown("""
        <style>
        /* Style text input fields to always show a border */
        .stTextInput > div > div > input,
        .stTextInput input[type="text"],
        .stTextInput input[type="password"],
        .stTextInput input {
            border: 1px solid #cccccc !important;
            border-radius: 4px !important;
        }
        
        /* Style text input fields on focus */
        .stTextInput > div > div > input:focus,
        .stTextInput input[type="text"]:focus,
        .stTextInput input[type="password"]:focus,
        .stTextInput input:focus {
            border: 1px solid #1f77b4 !important;
            box-shadow: 0 0 0 1px #1f77b4 !important;
        }
        
        /* Style number input fields to always show a border - multiple selectors for compatibility */
        .stNumberInput input,
        .stNumberInput > div > div > input,
        .stNumberInput input[type="number"],
        .stNumberInput [data-baseweb="input"] input,
        div[data-baseweb="input"] input[type="number"],
        div[data-baseweb="input"] input,
        input[type="number"][aria-label*="batch"],
        input[type="number"][aria-label*="Batch"],
        /* Target BaseWeb input wrapper used by Streamlit */
        [data-baseweb="input"] input {
            border: 1px solid #cccccc !important;
            border-radius: 4px !important;
        }
        
        /* Style number input fields on focus */
        .stNumberInput input:focus,
        .stNumberInput > div > div > input:focus,
        .stNumberInput input[type="number"]:focus,
        .stNumberInput [data-baseweb="input"] input:focus,
        div[data-baseweb="input"] input[type="number"]:focus,
        div[data-baseweb="input"] input:focus,
        input[type="number"][aria-label*="batch"]:focus,
        input[type="number"][aria-label*="Batch"]:focus,
        [data-baseweb="input"] input:focus {
            border: 1px solid #1f77b4 !important;
            box-shadow: 0 0 0 1px #1f77b4 !important;
        }
        
        /* Style textarea fields to always show a border */
        .stTextArea > div > div > textarea,
        .stTextArea textarea {
            border: 1px solid #cccccc !important;
            border-radius: 4px !important;
        }
        
        /* Style textarea fields on focus */
        .stTextArea > div > div > textarea:focus,
        .stTextArea textarea:focus {
            border: 1px solid #1f77b4 !important;
            box-shadow: 0 0 0 1px #1f77b4 !important;
        }
        </style>
    """, unsafe_allow_html=True)

