"""
Data Lineage – Streamlit App
=============================
Connects to Fabric SQL endpoint via pytds (pure Python, no ODBC driver needed).
Renders the React DAG visualisation in an iframe via st.components.

Deploy on Streamlit Cloud:
  1. Push to GitHub
  2. Create app on share.streamlit.io
  3. Set secrets: FABRIC_SERVER, FABRIC_DATABASE, AZURE_CLIENT_ID,
     AZURE_TENANT_ID, AZURE_CLIENT_SECRET (or use DefaultAzureCredential)
"""

import json
import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path

st.set_page_config(page_title="Data Lineage", layout="wide", initial_sidebar_state="collapsed")

# Hide Streamlit chrome for full-screen experience
st.markdown("""<style>
    #MainMenu, header, footer, .stDeployButton, [data-testid="stToolbar"] {display:none !important;}
    .stMainBlockContainer {padding:0 !important; max-width:100% !important;}
    iframe {border:none !important;}
</style>""", unsafe_allow_html=True)

# --- Config from secrets ---
FABRIC_SERVER = st.secrets.get("FABRIC_SERVER", "")
FABRIC_DATABASE = st.secrets.get("FABRIC_DATABASE", "")


def get_connection():
    """Connect to Fabric SQL endpoint using pytds + Azure AD token."""
    from azure.identity import DefaultAzureCredential, ClientSecretCredential

    # Use service principal if secrets are set, otherwise DefaultAzureCredential
    if st.secrets.get("AZURE_CLIENT_ID") and st.secrets.get("AZURE_CLIENT_SECRET"):
        credential = ClientSecretCredential(
            tenant_id=st.secrets["AZURE_TENANT_ID"],
            client_id=st.secrets["AZURE_CLIENT_ID"],
            client_secret=st.secrets["AZURE_CLIENT_SECRET"],
        )
    else:
        credential = DefaultAzureCredential()

    token = credential.get_token("https://database.windows.net/.default").token

    import pytds
    return pytds.connect(
        dsn=FABRIC_SERVER,
        port=1433,
        database=FABRIC_DATABASE,
        auth=pytds.login.AzureAuth(token),
    )


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
if FABRIC_SERVER and FABRIC_DATABASE:
    try:
        lineage_data = fetch_lineage()
    except Exception as e:
        st.toast(f"Could not connect to Fabric: {e}", icon="⚠️")

# --- Inject data into HTML ---
if lineage_data:
    inject_script = f"<script>window.__LINEAGE_API_DATA__ = {json.dumps(lineage_data)};</script>"
    html_content = html_content.replace(
        "window.__LINEAGE_API_DATA__ = null;",
        f"window.__LINEAGE_API_DATA__ = {json.dumps(lineage_data)};",
    )

# --- Render ---
components.html(html_content, height=900, scrolling=False)
