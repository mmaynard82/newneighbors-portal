import streamlit as st
import pandas as pd
import streamlit_authenticator as stauth
import gspread
from google.oauth2.service_account import Credentials
from streamlit_authenticator.utilities.hasher import Hasher

# ================== CONFIG ==================
st.set_page_config(page_title="New Neighbors Portal", layout="wide")

# ================== STYLE ==================
st.markdown("""
<style>
    .stApp { background-color: #f8fafc; }
    h1, h2, h3 { color: #1e40af; }
    .stButton>button { background-color: #1e40af; color: white; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# ================== HEADER ==================
col1, col2 = st.columns([1, 5])
with col1:
    st.image("logo.png", width=90)
with col2:
    st.title("New Neighbors Property Portal")
    st.caption("Property Monitoring Dashboard")

# ================== GOOGLE SHEETS ==================
@st.cache_resource
def get_gspread_client():
    creds_info = st.secrets["gcp_service_account"]
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = Credentials.from_service_account_info(creds_info, scopes=scope)
    return gspread.authorize(credentials)

client = get_gspread_client()

# ================== LOAD USERS ==================
def load_users():
    user_sheet = client.open("Users").sheet1
    values = user_sheet.get_all_values()

    if not values or len(values) < 2:
        return pd.DataFrame(columns=["Name", "Username", "Password"])

    headers = [str(col).strip() for col in values[0]]
    return pd.DataFrame(values[1:], columns=headers)

users_df = load_users()

# ================== AUTH SETUP ==================
credentials = {
    "usernames": {
        row["Username"]: {
            "name": row["Name"],
            "password": row["Password"]  # already hashed
        }
        for _, row in users_df.iterrows()
    }
}

authenticator = stauth.Authenticate(
    credentials,
    cookie_name="portal_cookie",
    cookie_key="CHANGE_THIS_SECRET_KEY_123",
    cookie_expiry_days=1
)

# ================== LOGIN ==================
name, authentication_status, username = authenticator.login("Login", "main")

# ================== MAIN APP ==================
if authentication_status is True:

    # Logout (safe)
    authenticator.logout("Logout", "sidebar")

    st.sidebar.image("logo.png", width=120)
    st.sidebar.write(f"**Welcome {name}**")

    # ================== LOAD PROPERTIES ==================
    try:
        prop_sheet = client.open("Properties").sheet1
        prop_values = prop_sheet.get_all_values()

        if len(prop_values) > 1:
            prop_df = pd.DataFrame(prop_values[1:], columns=prop_values[0])
        else:
            prop_df = pd.DataFrame()

    except:
        prop_df = pd.DataFrame()

    # ================== FILTER USER DATA ==================
    if not prop_df.empty and "Username" in prop_df.columns:
        user_props = prop_df[prop_df["Username"] == username]
    else:
        user_props = pd.DataFrame()

    # ================== DISPLAY ==================
    st.subheader("📍 Your Properties")

    if not user_props.empty:
        st.dataframe(user_props, use_container_width=True)
    else:
        st.info("No properties assigned yet.")

    # ================== ADD CLIENT (ADMIN USE) ==================
    st.sidebar.markdown("---")
    st.sidebar.subheader("➕ Add Client")

    user_sheet = client.open("Users").sheet1

    with st.sidebar.form("add_user", clear_on_submit=True):
        new_name = st.text_input("Name")
        new_username = st.text_input("Username")
        new_password = st.text_input("Password", type="password")

        if st.form_submit_button("Create Client"):
            if new_name and new_username and new_password:

                # 🔐 HASH PASSWORD BEFORE SAVING
                hashed_pw = Hasher([new_password]).generate()[0]

                user_sheet.append_row([new_name, new_username, hashed_pw])
                st.success("✅ Client added! Refresh page.")
                st.rerun()

            else:
                st.error("Fill all fields")

# ================== LOGIN STATES ==================
elif authentication_status is False:
    st.error("❌ Incorrect username or password")

elif authentication_status is None:
    st.warning("👤 Please enter your login details")
