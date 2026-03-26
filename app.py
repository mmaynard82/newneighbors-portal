import streamlit as st
import pandas as pd
import gspread
import requests
from google.oauth2.service_account import Credentials
import streamlit_authenticator as stauth

# ================== CONFIG ==================
st.set_page_config(page_title="New Neighbors Portal", layout="wide", page_icon="🏠")

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
    sheet = client.open("Users").sheet1
    values = sheet.get_all_values()
    headers = values[0]
    return pd.DataFrame(values[1:], columns=headers)

users_df = load_users()

credentials = {
    "usernames": {
        str(r["Username"]).strip(): {
            "name": r["Name"],
            "password": r["Password"],
            "role": r.get("Role","client")
        } for _, r in users_df.iterrows()
    }
}

authenticator = stauth.Authenticate(
    credentials,
    "cookie",
    "secret_key_123",
    7,
    auto_hash=False
)

# ================== LOGIN ==================
name, authentication_status, username = authenticator.login("main", "Login")

# ================== MAIN APP ==================
if authentication_status:

    authenticator.logout("Logout", "sidebar")
    st.sidebar.write(f"👋 Welcome {name}")

    role = credentials["usernames"][username]["role"]

    # ================== LOAD PROPERTIES ==================
    @st.cache_data(ttl=30)
    def load_properties():
        sheet = client.open("Properties").sheet1
        values = sheet.get_all_values()
        return pd.DataFrame(values[1:], columns=values[0])

    prop_df = load_properties()

    # ================== FILTER PROPERTIES ==================
    if role == "client":
        prop_df = prop_df[prop_df["Username"] == username]

    # ================== JOTFORM ==================
    @st.cache_data(ttl=60)
    def get_jotform():
        url = f"https://api.jotform.com/user/submissions?apiKey={st.secrets['JOTFORM_API_KEY']}"
        res = requests.get(url).json()

        records = []
        for sub in res["content"]:
            rec = {"CreatedAt": sub["created_at"]}
            for v in sub["answers"].values():
                rec[v["text"]] = v.get("answer", "")
            records.append(rec)

        df = pd.DataFrame(records)
        if not df.empty:
            df["CreatedAt"] = pd.to_datetime(df["CreatedAt"])
        return df

    insp_df = get_jotform()

    # ================== FILTER INSPECTIONS ==================
    if not insp_df.empty and "Username" in insp_df.columns:
        if role == "client":
            insp_df = insp_df[insp_df["Username"] == username]

    # ================== TABS ==================
    tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "🏠 Properties", "📝 Inspections"])

    # ================== DASHBOARD ==================
    with tab1:
        st.subheader("📊 Overview")

        col1, col2, col3 = st.columns(3)
        col1.metric("Properties", len(prop_df))
        col2.metric("Inspections", len(insp_df))

        if "Status" in insp_df.columns:
            col3.metric("Failed", (insp_df["Status"] == "Failed").sum())

        # Deal rot
        if "CreatedAt" in insp_df.columns:
            insp_df["Days Old"] = (pd.Timestamp.now() - insp_df["CreatedAt"]).dt.days
            old = insp_df[insp_df["Days Old"] > 7]

            st.markdown("### 🚨 Aging Inspections")
            if not old.empty:
                st.warning(f"{len(old)} inspections older than 7 days")
                st.dataframe(old)
            else:
                st.success("No aging inspections")

        # Chart
        if "Status" in insp_df.columns:
            st.bar_chart(insp_df["Status"].value_counts())

    # ================== PROPERTIES ==================
    with tab2:
        st.subheader("🏠 Properties")
        st.dataframe(prop_df, use_container_width=True)

    # ================== INSPECTIONS ==================
    with tab3:
        st.subheader("📝 Inspections")
        st.dataframe(insp_df, use_container_width=True)

# ================== LOGIN STATES ==================
elif authentication_status is False:
    st.error("❌ Incorrect username or password")
elif authentication_status is None:
    st.warning("👤 Please enter your login details")
