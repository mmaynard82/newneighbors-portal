import streamlit as st
import pandas as pd
import streamlit_authenticator as stauth
import gspread
from google.oauth2.service_account import Credentials

# ----------------------------- PAGE CONFIG -----------------------------
st.set_page_config(page_title="New Neighbors Portal", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #f8fafc; }
    h1, h2, h3 { color: #1e40af; }
    .stButton>button { background-color: #1e40af; color: white; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# ----------------------------- HEADER -----------------------------
col1, col2 = st.columns([1, 5])
with col1:
    st.image("logo.png", width=90)
with col2:
    st.title("New Neighbors Property Portal")
    st.caption("Property Monitoring Dashboard")

# ----------------------------- GOOGLE SHEETS CONNECTION -----------------------------
@st.cache_resource(show_spinner="Connecting to Google Sheets...")
def get_gspread_client():
    try:
        creds_info = st.secrets["gcp_service_account"]
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        credentials = Credentials.from_service_account_info(creds_info, scopes=scope)
        return gspread.authorize(credentials)
    except Exception as e:
        st.error("❌ Failed to connect to Google Sheets")
        st.error(f"Error: {str(e)}")
        st.info("Make sure your secrets are correctly added under **[gcp_service_account]**")
        st.stop()

client = get_gspread_client()

# ----------------------------- LOAD USERS (Robust Version) -----------------------------
try:
    user_sheet = client.open("Users").sheet1
    users_data = pd.DataFrame(user_sheet.get_all_records())

    # Show actual columns in sidebar for debugging
    st.sidebar.info(f"Users sheet columns found: {list(users_data.columns)}")

    # Flexible column detection (case-insensitive)
    def find_column(df, possible_names):
        for col in df.columns:
            if str(col).strip().lower() in [name.lower() for name in possible_names]:
                return col
        return None

    name_col = find_column(users_data, ["Name", "Full Name", "Client Name", "name"])
    username_col = find_column(users_data, ["Username", "User", "Email", "username"])
    password_col = find_column(users_data, ["Password", "Pass", "Pwd", "password"])

    if not name_col or not username_col or not password_col:
        st.error("❌ Users sheet is missing required columns.")
        st.error("Please make sure your 'Users' sheet has columns for: **Name**, **Username**, and **Password**")
        st.info(f"Found columns: {list(users_data.columns)}")
        st.stop()

    names = users_data[name_col].dropna().tolist()
    usernames = users_data[username_col].dropna().tolist()
    passwords = users_data[password_col].dropna().tolist()

    if len(names) == 0:
        st.warning("No users found in the Users sheet. Please add some users first.")
        names = []
        usernames = []
        passwords = []

except Exception as e:
    st.error(f"Failed to load Users sheet: {e}")
    st.stop()

# Hash passwords
hashed_passwords = stauth.Hasher().hash_list(passwords)

authenticator = stauth.Authenticate(
    names, usernames, hashed_passwords,
    "portal_cookie", "abc123", cookie_expiry_days=1
)

name, auth_status, username = authenticator.login("Client Login", "main")

# ----------------------------- HEALTH SCORE -----------------------------
def get_health_score(status):
    status = str(status).lower()
    if status == "excellent": return 95
    elif status == "good": return 85
    elif status == "needs attention": return 70
    elif status == "critical": return 50
    return 75

# ----------------------------- AUTH SUCCESS -----------------------------
if auth_status:
    authenticator.logout("Logout", "sidebar")
    st.sidebar.image("logo.png", width=120)
    st.sidebar.write(f"Welcome {name}")

    # Load Reports
    try:
        report_sheet = client.open("Reports").sheet1
        data = pd.DataFrame(report_sheet.get_all_records())
        user_data = data[data["Client"].str.lower() == username.lower()] if "Client" in data.columns else pd.DataFrame()

        st.subheader("📍 Your Properties")
        if user_data.empty:
            st.info("No properties found for your account yet.")
        else:
            for _, row in user_data.iterrows():
                score = get_health_score(row.get("Status", "Good"))
                st.markdown("---")
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.subheader(f"🏡 {row.get('Property', 'Unknown Property')}")
                    st.write(f"📅 Last Visit: {row.get('Date', 'N/A')}")
                    st.write(f"📊 Status: {row.get('Status', 'N/A')}")
                    if row.get("Report"):
                        st.link_button("📄 View Report", row["Report"])
                with col2:
                    st.metric("🏠 Health Score", f"{score}/100")
                    st.progress(score / 100)
    except Exception as e:
        st.error(f"Could not load Reports sheet: {e}")

    # ----------------------------- ADD CLIENT -----------------------------
    st.sidebar.markdown("---")
    st.sidebar.subheader("➕ Add Client")
    with st.sidebar.form("add_user"):
        new_name = st.text_input("Name")
        new_username = st.text_input("Username")
        new_password = st.text_input("Password", type="password")
        if st.form_submit_button("Create Client"):
            if new_name and new_username and new_password:
                try:
                    # Append in the order of actual columns
                    user_sheet.append_row([new_name, new_username, new_password])
                    st.success("✅ Client added successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to add client: {e}")
            else:
                st.error("Please fill all fields")

elif auth_status == False:
    st.error("❌ Incorrect username or password")
elif auth_status is None:
    st.warning("Please enter your login details")
