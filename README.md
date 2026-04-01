# Data Lineage – Streamlit App

Interactive visualization of Supply Chain data lineage.  
Reads real-time from `utl_pipeline_metadata` table via ODBC (Fabric SQL endpoint).  
Built with Streamlit + Cytoscape DAG visualization.

---

## Prerequisites

| Requirement | How to get it |
|---|---|
| **Python 3.10+** | https://www.python.org/downloads/ |
| **ODBC Driver 17 or 18 for SQL Server** | https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server |
| **Azure CLI** (for local authentication) | https://learn.microsoft.com/en-us/cli/azure/install-azure-cli |

---

## Setup (one-time)

### 1. Install ODBC Driver

Download and install from the link above. Verify:

```
python -c "import pyodbc; print([d for d in pyodbc.drivers() if 'SQL Server' in d])"
```

### 2. Create virtual environment

```
cd lineage_app
python -m venv .venv
```

Activate:

- **Windows (cmd):** `.venv\Scripts\activate`
- **Windows (PowerShell):** `.venv\Scripts\Activate.ps1`
- **Mac/Linux:** `source .venv/bin/activate`

### 3. Install dependencies

```
pip install -r requirements.txt
```

### 4. Configure secrets

Copy the example file and fill in your values:

```
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Edit `.streamlit/secrets.toml`:

```toml
FABRIC_SERVER = "your-server.datawarehouse.fabric.microsoft.com"
FABRIC_DATABASE = "your_database"

# Service Principal (optional – for Streamlit Cloud)
AZURE_TENANT_ID = ""
AZURE_CLIENT_ID = ""
AZURE_CLIENT_SECRET = ""
```

### 5. Login to Azure (local development)

```
az login
```

Sign in with your account. The app uses `DefaultAzureCredential` which picks up your `az login` session automatically.  
On Streamlit Cloud, use Service Principal credentials in secrets instead.

---

## Run

```
streamlit run app.py
```

The app opens automatically at **http://localhost:8501**.

---

## Deploy on Streamlit Cloud

1. Push repo to GitHub
2. Create app on [share.streamlit.io](https://share.streamlit.io)
3. `packages.txt` already includes `unixodbc-dev` (required for pyodbc on Linux)
4. Add secrets via **Settings > Secrets** (same format as `secrets.toml`)

---

## Features

- **Real-time ODBC**: Reads lineage from `utl_pipeline_metadata` (cached 5 minutes)
- **DAG visualization**: Left-to-right flow: Raw → BRZ/REF → SLV → GLD
- **Click a node**: Highlights full upstream/downstream chain
- **Filter by layer**: Click layer buttons (BRZ, SLV, GLD, etc.)
- **Search**: Filter nodes by name
- **Auto-detect ODBC driver**: Supports both Driver 17 and 18

---

## File Structure

```
lineage_app/
  app.py                        # Streamlit app (ODBC + iframe rendering)
  requirements.txt              # Python dependencies
  packages.txt                  # System packages for Streamlit Cloud
  README.md                     # This file
  .streamlit/
    config.toml                 # Streamlit config (headless mode)
    secrets.toml.example        # Template for secrets
  templates/
    lineage.html                # React UI (Cytoscape DAG visualization)
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `No module named 'pyodbc'` | Run `pip install -r requirements.txt` |
| `ODBC Driver not found` | Install ODBC Driver 17 or 18 (see Prerequisites) |
| `DefaultAzureCredential failed` | Run `az login` and try again |
| Toast "Could not connect to Fabric" | Check secrets config and that Fabric endpoint is reachable |
| App shows but no data | Verify `FABRIC_SERVER` and `FABRIC_DATABASE` in secrets |
