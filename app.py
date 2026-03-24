import streamlit as st
import pandas as pd
import streamlit_authenticator as stauth
import gspread
from google.oauth2.service_account import Credentials
from streamlit_authenticator.utilities.hasher import Hasher

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
    creds_info = st.secrets["gcp_service_account"]
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = Credentials.from_service_account_info(creds_info, scopes=scope)
    return gspread.authorize(credentials)

client = get_gspread_client()

# ----------------------------- LOAD USERS -----------------------------
try:
    user_sheet = client.open("Users").sheet1
    values = user_sheet.get_all_values()
    
    if not values or len(values) < 2:
        st.warning("No users in sheet yet. Add some using the sidebar form.")
        names = usernames = passwords = []
    else:
        headers = [str(col).strip() for col in values[0]]
        users_data = pd.DataFrame(values[1:], columns=headers)
        
        st.sidebar.info(f"Columns found: {list(users_data.columns)}")
        
        names = users_data["Name"].dropna().astype(str).tolist()
        usernames = users_data["Username"].dropna().astype(str).tolist()
        passwords = users_data["Password"].dropna().astype(str).tolist()

except Exception as e:
    st.error(f"Failed to load Users sheet: {e}")
    st.stop()

# ----------------------------- HASH PASSWORDS & CREDENTIALS -----------------------------
hashed_passwords = Hasher(passwords).generate() if passwords else []

credentials = {
    "usernames": {
        user: {"name": name, "password": pwd}
        for user, name, pwd in zip(usernames, names, hashed_passwords)
    }
}

# ----------------------------- AUTHENTICATOR -----------------------------
authenticator = stauth.Authenticate(
    credentials=credentials,
    cookie_name="portal_cookie",
    cookie_key="abc123_super_secret_change_me",   # ← Change this to a long random string later
    cookie_expiry_days=1
)

# ----------------------------- LOGIN -----------------------------
authentication_status = authenticator.login(location="main")

name = st.session_state.get("name")
username = st.session_state.get("username")

# ----------------------------- HEALTH SCORE -----------------------------
def get_health_score(status):
    status = str(status).lower()
    if status == "excellent": return 95
    elif status == "good": return 85
    elif status == "needs attention": return 70
    elif status == "critical": return 50
    return 75

# ----------------------------- MAIN APP -----------------------------
if authentication_status:
    # ✅ Logout button ONLY appears when user is logged in
    authenticator.logout("Logout", "sidebar")
    
    st.sidebar.image("logo.png", width=120)
    st.sidebar.write(f"**Welcome {name}**")

    # Load Reports
    try:
        report_sheet = client.open("Reports").sheet1
        values = report_sheet.get_all_values()
        if values:
            data = pd.DataFrame(values[1:], columns=[str(c).strip() for c in values[0]])
        else:
            data = pd.DataFrame()

        user_data = data[data.get("Client", pd.Series()).astype(str).str.lower() == str(username).lower()]

        st.subheader("📍 Your Properties")
        if user_data.empty:
            st.info("No properties found for your account yet.")
        else:
            for _, row in user_data.iterrows():
                score = get_health_score(row.get("Status", ""))
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
        st.error(f"Could not load Reports: {e}")

    # ----------------------------- ADD CLIENT -----------------------------
    st.sidebar.markdown("---")
    st.sidebar.subheader("➕ Add Client")
    with st.sidebar.form("add_user"):
        new_name = st.text_input("Name")
        new_username = st.text_input("Username")
        new_password = st.text_input("Password", type="password")
        if st.form_submit_button("Create Client"):
            if new_name and new_username and new_password:
                user_sheet.append_row([new_name, new_username, new_password])
                st.success("✅ Client added! Refresh the page to log in.")
                st.rerun()
            else:
                st.error("Please fill all fields")

elif authentication_status == False:
    st.error("❌ Incorrect username or password")
else:
    st.warning("👤 Please enter your login details")
