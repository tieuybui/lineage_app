"""
Data Lineage – Streamlit App
=============================
Connects to Fabric SQL endpoint via pyodbc (ODBC Driver 17/18) + Azure AD token.
Renders the React DAG visualisation in an iframe via st.components.

Deploy on Streamlit Cloud:
  1. Push to GitHub
  2. Create app on share.streamlit.io
  3. Add packages.txt with: unixodbc-dev
  4. Set secrets: FABRIC_SERVER, FABRIC_DATABASE, AZURE_CLIENT_ID,
     AZURE_TENANT_ID, AZURE_CLIENT_SECRET
"""

import json
import struct
import hmac
import hashlib
from datetime import datetime, timedelta
import streamlit as st
import streamlit.components.v1 as components
from streamlit_cookies_controller import CookieController
from pathlib import Path

st.set_page_config(page_title="Data Lineage", layout="wide", initial_sidebar_state="collapsed")

cookie_controller = CookieController()

AUTH_COOKIE_NAME = "lineage_auth_token"
AUTH_COOKIE_DAYS = 30


def _make_token(email: str, password: str) -> str:
    """Create a deterministic auth token from credentials."""
    return hashlib.sha256(f"lineage:{email}:{password}".encode()).hexdigest()


def _get_expected_token():
    correct_email = st.secrets.get("LOGIN_EMAIL", "")
    correct_password = st.secrets.get("LOGIN_PASSWORD", "")
    return correct_email, correct_password, _make_token(correct_email, correct_password)


def check_login():
    """Show login form and verify credentials. Persists auth via browser cookie."""
    correct_email, correct_password, expected_token = _get_expected_token()

    # Already authenticated this session → ensure cookie is persisted
    if st.session_state.get("authenticated"):
        saved_token = cookie_controller.get(AUTH_COOKIE_NAME)
        if not saved_token or str(saved_token) != expected_token:
            cookie_controller.set(
                AUTH_COOKIE_NAME,
                expected_token,
                expires=datetime.now() + timedelta(days=AUTH_COOKIE_DAYS),
            )
        return True

    # Check saved cookie from previous session
    saved_token = cookie_controller.get(AUTH_COOKIE_NAME)
    if saved_token and hmac.compare_digest(str(saved_token), expected_token):
        st.session_state["authenticated"] = True
        return True

    # Show login form
    with st.container():
        st.markdown("<h2 style='text-align:center; margin-top:15vh;'>🔐 Data Lineage Login</h2>", unsafe_allow_html=True)
        _, col2, _ = st.columns([1, 1, 1])
        with col2:
            with st.form("login_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login", use_container_width=True)

            if submitted:
                if (
                    hmac.compare_digest(email.strip(), correct_email)
                    and hmac.compare_digest(password, correct_password)
                ):
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Email hoặc mật khẩu không đúng.")
    return False


if not check_login():
    st.stop()

# Hide Streamlit chrome for full-screen experience
st.markdown("""<style>
    #MainMenu, header, footer, .stDeployButton, [data-testid="stToolbar"] {display:none !important;}
    .stMainBlockContainer {padding:0 !important; max-width:100% !important;}
    iframe {border:none !important;}

</style>""", unsafe_allow_html=True)

# --- Config from secrets ---
FABRIC_SERVER = st.secrets.get("FABRIC_SERVER", "")
FABRIC_DATABASE = st.secrets.get("FABRIC_DATABASE", "")
SQL_COPT_SS_ACCESS_TOKEN = 1256

# --- Detect ODBC Driver ---
ODBC_DRIVER = None
try:
    import pyodbc
    for drv in ["ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server"]:
        if drv in pyodbc.drivers():
            ODBC_DRIVER = drv
            break
except Exception:
    pass


def get_connection():
    """Connect to Fabric SQL endpoint using pyodbc + Azure AD token."""
    from azure.identity import DefaultAzureCredential, ClientSecretCredential

    if st.secrets.get("AZURE_CLIENT_ID", "").strip() and st.secrets.get("AZURE_CLIENT_SECRET", "").strip():
        credential = ClientSecretCredential(
            tenant_id=st.secrets["AZURE_TENANT_ID"],
            client_id=st.secrets["AZURE_CLIENT_ID"],
            client_secret=st.secrets["AZURE_CLIENT_SECRET"],
        )
    else:
        credential = DefaultAzureCredential()

    token = credential.get_token("https://database.windows.net/.default").token
    token_bytes = token.encode("utf-16-le")
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)

    conn_str = (
        f"DRIVER={{{ODBC_DRIVER}}};"
        f"Server={FABRIC_SERVER},1433;"
        f"Database={FABRIC_DATABASE};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=no"
    )
    return pyodbc.connect(conn_str, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})


@st.cache_data(ttl=300)
def fetch_lineage():
    """Fetch lineage data from Fabric and return {nodes, edges} dict."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT table_name, layer, source_tables, load_type, status,
               CAST(last_load_date AS VARCHAR) AS last_load_date,
               rows_loaded
        FROM dbo.utl_pipeline_metadata
        WHERE source_tables IS NOT NULL
        ORDER BY layer, table_name
    """)
    columns = [col[0] for col in cursor.description]
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()

    nodes, edges, seen = [], [], set()

    for r in rows:
        tn = r["table_name"]
        nodes.append({
            "id": tn,
            "layer": r["layer"] or "unknown",
            "load_type": r["load_type"] or "",
            "status": r["status"] or "",
            "last_load_date": r["last_load_date"] or "",
            "rows_loaded": r["rows_loaded"] or 0,
        })
        seen.add(tn)

        if r["source_tables"]:
            for src in r["source_tables"].split(","):
                src = src.strip()
                if src.startswith("[external]"):
                    ext_id = src.replace("[external] ", "ext:")
                    if ext_id not in seen:
                        nodes.append({"id": ext_id, "layer": "external", "load_type": "", "status": "", "last_load_date": "", "rows_loaded": 0})
                        seen.add(ext_id)
                    edges.append({"source": ext_id, "target": tn})
                else:
                    if src not in seen:
                        nodes.append({"id": src, "layer": "orphan", "load_type": "", "status": "", "last_load_date": "", "rows_loaded": 0})
                        seen.add(src)
                    edges.append({"source": src, "target": tn})

    return {"nodes": nodes, "edges": edges}


# --- Load HTML template ---
html_path = Path(__file__).parent / "templates" / "lineage.html"
html_content = html_path.read_text(encoding="utf-8")

# --- Try to fetch live data from Fabric ---
lineage_data = None
if FABRIC_SERVER and FABRIC_DATABASE and ODBC_DRIVER:
    try:
        lineage_data = fetch_lineage()
    except Exception as e:
        st.toast(f"Could not connect to Fabric: {e}", icon="⚠️")

# --- Inject data into HTML ---
if lineage_data:
    html_content = html_content.replace(
        "window.__LINEAGE_API_DATA__ = null;",
        f"window.__LINEAGE_API_DATA__ = {json.dumps(lineage_data)};",
    )

# --- Render ---
components.html(html_content, height=900, scrolling=False)
