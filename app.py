import streamlit as st
import pandas as pd
import gspread
import requests
from google.oauth2.service_account import Credentials
import streamlit_authenticator as stauth

# ================== CONFIG ==================
st.set_page_config(page_title="New Neighbors Portal", layout="wide", page_icon="🏠")

# ================== BRANDING / CSS ==================
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>
.stApp {
    background-color: #f5f7fb;
    font-family: 'Inter', sans-serif;
}

/* Headers */
h1, h2, h3 {
    color: #1e3a8a;
    font-weight: 600;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #1e3a8a;
}
section[data-testid="stSidebar"] * {
    color: white !important;
}

/* Buttons */
.stButton>button {
    background-color: #1e3a8a;
    color: white;
    border-radius: 8px;
    padding: 8px 16px;
    border: none;
}
.stButton>button:hover {
    background-color: #1d4ed8;
}

/* Cards */
[data-testid="stMetric"] {
    background-color: white;
    padding: 15px;
    border-radius: 10px;
    border: 1px solid #e5e7eb;
}

/* Tables */
[data-testid="stDataFrame"] {
    background-color: white;
    border-radius: 10px;
    padding: 10px;
}
</style>
""", unsafe_allow_html=True)

# ================== HEADER ==================
col1, col2 = st.columns([1,6])
with col1:
    st.image("logo.png", width=80)
with col2:
    st.markdown("""
    <h2 style='margin-bottom:0;'>New Neighbors Portal</h2>
    <span style='color:gray;'>Property Monitoring Dashboard</span>
    """, unsafe_allow_html=True)

# ================== GOOGLE SHEETS ==================
@st.cache_resource
def get_client():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
    )
    return gspread.authorize(creds)

client = get_client()

# ================== LOAD USERS ==================
@st.cache_data(ttl=10)
def load_users():
    try:
        sheet = client.open("Users").sheet1
        values = sheet.get_all_values()
        headers = [h.strip() for h in values[0]]
        return pd.DataFrame(values[1:], columns=headers)
    except:
        return pd.DataFrame(columns=["Name","Username","Password","Role"])

users_df = load_users()

# ================== AUTH ==================
credentials = {"usernames": {}}

for _, row in users_df.iterrows():
    username = str(row.get("Username","")).strip()
    if username:
        credentials["usernames"][username] = {
            "name": row.get("Name"),
            "password": row.get("Password"),
            "role": str(row.get("Role","client")).lower()
        }

authenticator = stauth.Authenticate(
    credentials,
    "cookie",
    "secure_key_123",
    7,
    auto_hash=False
)

# ================== LOGIN ==================
st.markdown("<h3 style='text-align:center;'>Client Portal Login</h3>", unsafe_allow_html=True)
name, authentication_status, username = authenticator.login("main", "Login")

# ================== MAIN ==================
if authentication_status:

    authenticator.logout("Logout", "sidebar")
    st.sidebar.write(f"👋 Welcome {name}")

    role = credentials["usernames"][username]["role"]

    # ================== LOAD PROPERTIES ==================
    @st.cache_data(ttl=30)
    def load_properties():
        try:
            sheet = client.open("Properties").sheet1
            values = sheet.get_all_values()

            headers = [h.strip() for h in values[0] if h]
            rows = [r[:len(headers)] for r in values[1:]]

            df = pd.DataFrame(rows, columns=headers)
            df.columns = [c.strip() for c in df.columns]
            return df
        except:
            return pd.DataFrame()

    prop_df = load_properties()

    if role == "client" and "Username" in prop_df.columns:
        prop_df = prop_df[
            prop_df["Username"].astype(str).str.strip() == username
        ]

    # ================== JOTFORM ==================
    @st.cache_data(ttl=60)
    def get_jotform():
        api_key = st.secrets.get("JOTFORM_API_KEY")
        if not api_key:
            return pd.DataFrame()

        try:
            url = f"https://api.jotform.com/user/submissions?apiKey={api_key}"
            res = requests.get(url)

            if res.status_code != 200:
                return pd.DataFrame()

            data = res.json()
            records = []

            for sub in data.get("content", []):
                rec = {"CreatedAt": sub.get("created_at")}

                for v in sub.get("answers", {}).values():
                    rec[v.get("text","")] = v.get("answer","")

                records.append(rec)

            df = pd.DataFrame(records)

            if not df.empty:
                df["CreatedAt"] = pd.to_datetime(df["CreatedAt"], errors="coerce")

            return df

        except:
            return pd.DataFrame()

    insp_df = get_jotform()

    if not insp_df.empty and "Username" in insp_df.columns:
        if role == "client":
            insp_df = insp_df[
                insp_df["Username"].astype(str).str.strip() == username
            ]

    # ================== TABS ==================
    tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "🏠 Properties", "📝 Inspections"])

    # ================== DASHBOARD ==================
    with tab1:
        st.subheader("📊 Overview")

        col1, col2, col3 = st.columns(3)
        col1.metric("🏠 Properties", len(prop_df))
        col2.metric("📝 Inspections", len(insp_df))

        if "Status" in insp_df.columns:
            col3.metric("❌ Failed", (insp_df["Status"] == "Failed").sum())

        # Aging
        if "CreatedAt" in insp_df.columns and not insp_df.empty:
            insp_df["Days Old"] = (pd.Timestamp.now() - insp_df["CreatedAt"]).dt.days
            old = insp_df[insp_df["Days Old"] > 7]

            st.markdown("### 🚨 Aging Inspections")
            if not old.empty:
                st.error(f"{len(old)} inspections need attention")
                st.dataframe(old)
            else:
                st.success("All inspections up to date")

        if "Status" in insp_df.columns:
            st.bar_chart(insp_df["Status"].value_counts())

    # ================== PROPERTIES ==================
    with tab2:
        st.subheader("🏠 Your Properties")

        if prop_df.empty:
            st.info("No properties found.")
        else:
            st.dataframe(prop_df, use_container_width=True)

    # ================== INSPECTIONS ==================
    with tab3:
        st.subheader("📝 Inspections")

        if insp_df.empty:
            st.info("No inspections found.")
        else:
            st.dataframe(insp_df, use_container_width=True)

# ================== LOGIN STATES ==================
elif authentication_status is False:
    st.error("❌ Incorrect username or password")

elif authentication_status is None:
    st.warning("👤 Please enter your login details")
