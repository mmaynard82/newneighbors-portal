import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import streamlit_authenticator as stauth

st.set_page_config(page_title="New Neighbors Portal", layout="wide", page_icon="🏠")

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

# ================== GOOGLE SHEETS ==================
@st.cache_resource
def get_gspread_client():
    creds_info = st.secrets["gcp_service_account"]
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_info(creds_info, scopes=scope)
    return gspread.authorize(credentials)

client = get_gspread_client()

# ================== LOAD USERS ==================
@st.cache_data(ttl=10)
def load_users():
    try:
        spreadsheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1LmmZNAT0jFVHY1ZqseyiS9kzrFnbLB3ak2abDRTH6Ms")
        worksheet = spreadsheet.sheet1
        values = worksheet.get_all_values()
        if not values or len(values) < 2:
            st.sidebar.warning("No data in Users sheet")
            return pd.DataFrame(columns=["Name","Username","Password","Role"])
        
        headers = [str(c).strip() for c in values[0]]
        df = pd.DataFrame(values[1:], columns=headers)
        st.sidebar.success(f"✅ Loaded {len(df)} user(s)")
        return df
    except Exception as e:
        st.error(f"Failed to load Users sheet: {e}")
        return pd.DataFrame(columns=["Name","Username","Password","Role"])

users_df = load_users()

# ================== BUILD CREDENTIALS ==================
# Ensure 'usernames' is the top-level key
credentials = {"usernames": {}}

for idx, row in users_df.iterrows():
    username = str(row.get("Username", "")).strip()
    password_hash = str(row.get("Password", "")).strip()
    
    if username:
        credentials["usernames"][username] = {
            "name": str(row.get("Name", username)).strip(),
            "password": password_hash,
            "email": "user@example.com" # Some versions require an email field
        }

# ================== AUTHENTICATOR ==================
authenticator = stauth.Authenticate(
    credentials, # Pass the WHOLE dictionary
    "new_neighbors_portal", # cookie name
    "signature_key", # cookie key
    30, # cookie expiry
    auto_hash=False # Keep this False since you are hashing manually
)
# ================== LOGIN ==================
name, authentication_status, username = authenticator.login("main", "Login")

# Force Re-hash Button
st.sidebar.markdown("### 🔧 Admin Tools")
if st.sidebar.button("🔐 Force Re-hash ALL passwords"):
    with st.spinner("Re-hashing..."):
        try:
            sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1LmmZNAT0jFVHY1ZqseyiS9kzrFnbLB3ak2abDRTH6Ms").sheet1
            data = sheet.get_all_values()
            headers = data[0]
            rows = data[1:]
            pw_idx = headers.index("Password")
            
            updated = []
            for row in rows:
                new_row = list(row)
                current = str(new_row[pw_idx]).strip()
                if current:
                    new_hash = stauth.Hasher([current]).generate()[0]
                    new_row[pw_idx] = new_hash
                updated.append(new_row)
            
            sheet.clear()
            sheet.update([headers] + updated)
            st.sidebar.success("✅ All passwords re-hashed!")
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Re-hash error: {e}")

# ================== MAIN APP ==================
if authentication_status:
    authenticator.logout("Logout", "sidebar")
    st.sidebar.image("logo.png", width=120)
    st.sidebar.write(f"**Welcome, {name}**")
    st.success(f"✅ Logged in successfully as **{username}**")
    
    # Add your Properties code here later

elif authentication_status is False:
    st.error("❌ Incorrect username or password")
    st.sidebar.error("Login failed — check the Debug Info above for clues")

elif authentication_status is None:
    st.warning("👤 Please enter your login details")
