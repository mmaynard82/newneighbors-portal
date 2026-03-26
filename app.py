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
</style>
""", unsafe_allow_html=True)

# ================== HEADER ==================
st.title("🏠 New Neighbors Property Portal")

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
        rows = values[1:]

        df = pd.DataFrame(rows, columns=headers)
        return df
    except Exception as e:
        st.error(f"Users load error: {e}")
        return pd.DataFrame(columns=["Name","Username","Password","Role"])

users_df = load_users()

# ================== BUILD CREDENTIALS ==================
credentials = {"usernames": {}}

for _, row in users_df.iterrows():
    username = str(row.get("Username","")).strip()
    password = str(row.get("Password","")).strip()
    name = str(row.get("Name","")).strip()
    role = str(row.get("Role","client")).strip().lower()

    if username:
        credentials["usernames"][username] = {
            "name": name,
            "password": password,
            "role": role
        }

# ================== AUTH ==================
authenticator = stauth.Authenticate(
    credentials,
    "cookie",
    "secret_key_123",
    7,
    auto_hash=False
)

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

        except Exception as e:
            st.error(f"Properties load error: {e}")
            return pd.DataFrame()

    prop_df = load_properties()

    # ================== FILTER PROPERTIES ==================
    if role == "client" and "Username" in prop_df.columns:
        prop_df = prop_df[
            prop_df["Username"].astype(str).str.strip() == username
        ]

    # ================== JOTFORM ==================
    @st.cache_data(ttl=60)
    def get_jotform():
        try:
            url = f"https://api.jotform.com/user/submissions?apiKey={st.secrets['JOTFORM_API_KEY']}"
            res = requests.get(url)

            if res.status_code != 200:
                return pd.DataFrame()

            data = res.json()
            if "content" not in data:
                return pd.DataFrame()

            records = []

            for sub in data["content"]:
                rec = {"CreatedAt": sub.get("created_at")}

                answers = sub.get("answers", {})
                for v in answers.values():
                    question = v.get("text", "")
                    answer = v.get("answer", "")
                    rec[question] = answer

                records.append(rec)

            df = pd.DataFrame(records)

            if not df.empty and "CreatedAt" in df.columns:
                df["CreatedAt"] = pd.to_datetime(df["CreatedAt"], errors="coerce")

            return df

        except Exception as e:
            st.warning(f"Jotform error: {e}")
            return pd.DataFrame()

    insp_df = get_jotform()

    # ================== FILTER INSPECTIONS ==================
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

        st.metric("Properties", len(prop_df))
        st.metric("Inspections", len(insp_df))

        if "Status" in insp_df.columns:
            st.metric("Failed", (insp_df["Status"] == "Failed").sum())

        if "CreatedAt" in insp_df.columns and not insp_df.empty:
            insp_df["Days Old"] = (pd.Timestamp.now() - insp_df["CreatedAt"]).dt.days
            old = insp_df[insp_df["Days Old"] > 7]

            st.markdown("### 🚨 Aging Inspections")
            if not old.empty:
                st.warning(f"{len(old)} inspections older than 7 days")
                st.dataframe(old)
            else:
                st.success("No aging inspections")

    # ================== PROPERTIES ==================
    with tab2:
        st.subheader("🏠 Properties")

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
    st.warning("👤 Please enter login details")
