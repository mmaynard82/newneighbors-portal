import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import streamlit_authenticator as stauth

# ================== PAGE CONFIG ==================
st.set_page_config(
    page_title="New Neighbors Portal",
    layout="wide",
    page_icon="🏠"
)

# ================== CUSTOM STYLE ==================
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

# ================== GOOGLE SHEETS CONNECTION ==================
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

# ================== LOAD USERS ==================
@st.cache_data(ttl=30)
def load_users():
    try:
        # CHANGE THIS URL ONLY IF YOUR USERS SHEET ID CHANGES
        spreadsheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1LmmZNAT0jFVHY1ZqseyiS9kzrFnbLB3ak2abDRTH6Ms")
        st.sidebar.success("✅ Connected to Users spreadsheet")
        
        worksheet = spreadsheet.sheet1
        values = worksheet.get_all_values()
        
        if not values or len(values) < 2:
            st.sidebar.warning("Users sheet is empty or has no data rows")
            return pd.DataFrame(columns=["Name", "Username", "Password", "Role"])
        
        headers = [str(c).strip() for c in values[0]]
        df = pd.DataFrame(values[1:], columns=headers)
        
        st.sidebar.success(f"✅ Loaded {len(df)} users")
        return df
        
    except Exception as e:
        st.error(f"❌ Error loading Users sheet: {str(e)}")
        st.sidebar.error(f"Debug: {type(e).__name__} - {str(e)}")
        return pd.DataFrame(columns=["Name", "Username", "Password", "Role"])

users_df = load_users()

# ================== BUILD CREDENTIALS ==================
credentials = {"usernames": {}}

for _, row in users_df.iterrows():
    username = str(row.get("Username", "")).strip()
    if not username:
        continue
    
    password = str(row.get("Password", "")).strip()
    name = str(row.get("Name", username)).strip()
    role = str(row.get("Role", "client")).strip().lower()
    
    if not (password.startswith("$2b$") or password.startswith("$2a$") or password.startswith("$2y$")):
        st.warning(f"⚠️ Password for user **{username}** is not hashed yet.")
    
    credentials["usernames"][username] = {
        "name": name,
        "password": password,
        "role": role
    }

# ================== AUTHENTICATOR ==================
authenticator = stauth.Authenticate(
    credentials,
    cookie_name="new_neighbors_portal",
    cookie_key="NewNeighborsPortal2026_x7K9pL2mQ8vR4tY6uZ3wA5bC7dE9fG1hJ",   # Change this to your own long random string
    cookie_expiry_days=7,
    auto_hash=False
)

# ================== LOGIN ==================
name, authentication_status, username = authenticator.login("main", "Login")

# ================== RE-HASH BUTTON (visible before login) ==================
st.sidebar.markdown("### 🔧 Admin Tools")
if st.sidebar.button("🔐 Re-hash ALL passwords in sheet (one-time only)"):
    with st.spinner("Re-hashing passwords... Please wait"):
        try:
            # Use the same URL as above
            sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1LmmZNAT0jFVHY1ZqseyiS9kzrFnbLB3ak2abDRTH6Ms").sheet1
            data = sheet.get_all_values()
            
            if len(data) < 2:
                st.sidebar.error("No users found in sheet")
            else:
                headers = data[0]
                rows = data[1:]
                try:
                    pw_idx = headers.index("Password")
                except ValueError:
                    st.sidebar.error("Password column not found")
                    pw_idx = None
                
                if pw_idx is not None:
                    updated = []
                    for row in rows:
                        new_row = list(row)
                        current_pw = str(new_row[pw_idx]).strip()
                        # Hash only if it's not already a bcrypt hash
                        if not (current_pw.startswith("$2") and len(current_pw) > 50):
                            new_hash = stauth.Hasher([current_pw]).generate()[0]
                            new_row[pw_idx] = new_hash
                        updated.append(new_row)
                    
                    sheet.clear()
                    sheet.update([headers] + updated)
                    st.sidebar.success("✅ All passwords re-hashed successfully!")
                    st.cache_data.clear()
                    st.rerun()
        except Exception as e:
            st.sidebar.error(f"Re-hash failed: {e}")

# ================== MAIN APP ==================
if authentication_status:
    authenticator.logout("Logout", "sidebar")
    
    st.sidebar.image("logo.png", width=120)
    st.sidebar.write(f"**Welcome, {name}**")
    
    role = credentials["usernames"][username]["role"]
    
    # Load Properties
    try:
        # Replace with your Properties sheet URL if different
        prop_spreadsheet = client.open_by_url("https://docs.google.com/spreadsheets/d/18A7jnCqSsk1ojD5Wr_66BlmOK3kGZl0P1sn2zRMhgD8/edit?gid=0#gid=0")
        prop_values = prop_spreadsheet.sheet1.get_all_values()
        if len(prop_values) > 1:
            prop_df = pd.DataFrame(prop_values[1:], columns=prop_values[0])
        else:
            prop_df = pd.DataFrame()
    except Exception:
        st.warning("Could not load Properties sheet.")
        prop_df = pd.DataFrame()
    
    # Filter by role
    if role == "client" and not prop_df.empty and "Username" in prop_df.columns:
        user_props = prop_df[prop_df["Username"] == username]
    else:
        user_props = prop_df.copy()
    
    st.subheader("📍 My Properties")
    if not user_props.empty:
        st.dataframe(user_props, use_container_width=True)
    else:
        st.info("No properties assigned to you yet.")
    
    # Admin: Add User
    if role == "admin":
        st.sidebar.markdown("---")
        st.sidebar.subheader("➕ Add New User")
        with st.sidebar.form("add_user_form", clear_on_submit=True):
            new_name = st.text_input("Full Name")
            new_username = st.text_input("Username")
            new_password = st.text_input("Password", type="password")
            new_role = st.selectbox("Role", ["client", "admin"])
            
            if st.form_submit_button("Create User"):
                if new_name and new_username and new_password:
                    if new_username in credentials["usernames"]:
                        st.error("Username already exists!")
                    else:
                        hashed_pw = stauth.Hasher([new_password]).generate()[0]
                        user_sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1LmmZNAT0jFVHY1ZqseyiS9kzrFnbLB3ak2abDRTH6Ms").sheet1
                        user_sheet.append_row([new_name, new_username, hashed_pw, new_role])
                        st.success(f"✅ User **{new_username}** created!")
                        st.cache_data.clear()
                        st.rerun()
                else:
                    st.error("Please fill all fields")

elif authentication_status is False:
    st.error("❌ Incorrect username or password")
elif authentication_status is None:
    st.warning("👤 Please enter your login details")

# Footer
st.caption("New Neighbors Property Portal • Secure Login via Google Sheets")
