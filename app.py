import streamlit as st
import pandas as pd
import streamlit_authenticator as stauth
import gspread
from google.oauth2.service_account import Credentials
from streamlit_authenticator.utilities.hasher import Hasher

st.set_page_config(page_title="New Neighbors Portal", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #f8fafc; }
    h1, h2, h3 { color: #1e40af; }
    .stButton>button { background-color: #1e40af; color: white; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

col1, col2 = st.columns([1, 5])
with col1:
    st.image("logo.png", width=90)
with col2:
    st.title("New Neighbors Property Portal")
    st.caption("Property Monitoring Dashboard")

# Google Sheets
@st.cache_resource
def get_gspread_client():
    creds_info = st.secrets["gcp_service_account"]
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_info(creds_info, scopes=scope)
    return gspread.authorize(credentials)

client = get_gspread_client()

# Load Users
try:
    user_sheet = client.open("Users").sheet1
    values = user_sheet.get_all_values()
    if not values or len(values) < 2:
        st.warning("No users yet – add some using the sidebar form.")
        names = usernames = passwords = []
    else:
        headers = [str(col).strip() for col in values[0]]
        users_data = pd.DataFrame(values[1:], columns=headers)
        st.sidebar.info(f"Columns: {list(users_data.columns)}")
        names = users_data["Name"].dropna().astype(str).tolist()
        usernames = users_data["Username"].dropna().astype(str).tolist()
        passwords = users_data["Password"].dropna().astype(str).tolist()
except Exception as e:
    st.error(f"Users load error: {e}")
    st.stop()

# Auth Setup
hashed_passwords = Hasher(passwords).generate() if passwords else []
credentials = {"usernames": {u: {"name": n, "password": p} for u, n, p in zip(usernames, names, hashed_passwords)}}

authenticator = stauth.Authenticate(
    credentials=credentials,
    cookie_name="portal_cookie",
    cookie_key="super_secret_random_key_change_this_2026",
    cookie_expiry_days=1
)

# Login
authentication_status = authenticator.login(location="main")

# ======================= LOGGED IN SECTION =======================
if authentication_status:
    authenticator.logout("Logout", "sidebar")   # ← Safe here only
    
    st.sidebar.image("logo.png", width=120)
    st.sidebar.write(f"**Welcome {st.session_state.get('name')}**")

    st.subheader("📍 Your Properties")
    st.info("Reports section will appear here once you have data in the Reports sheet.")

    # Add Client Form
    st.sidebar.markdown("---")
    st.sidebar.subheader("➕ Add Client")
    with st.sidebar.form("add_user", clear_on_submit=True):
        new_name = st.text_input("Name")
        new_username = st.text_input("Username")
        new_password = st.text_input("Password", type="password")
        if st.form_submit_button("Create Client"):
            if new_name and new_username and new_password:
                user_sheet.append_row([new_name, new_username, new_password])
                st.success("✅ Client added! Refresh page.")
                st.rerun()
            else:
                st.error("Fill all fields")

elif authentication_status == False:
    st.error("❌ Incorrect username or password")
else:
    st.warning("👤 Please enter your login details")
