# Data Lineage Web App

Interactive visualization of Supply Chain data lineage.  
Reads real-time from `utl_pipeline_metadata` table via ODBC (Fabric SQL endpoint).

![DAG layout: Raw → BRZ/REF → SLV → GLD]

---

## Prerequisites

| Requirement | How to get it |
|---|---|
| **Python 3.10+** | https://www.python.org/downloads/ |
| **ODBC Driver 18 for SQL Server** | https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server |
| **Azure CLI** (for authentication) | https://learn.microsoft.com/en-us/cli/azure/install-azure-cli |

---

## Setup (one-time)

### 1. Install ODBC Driver 18

Download and install from the link above. Verify it's installed:

```
python -c "import pyodbc; print([d for d in pyodbc.drivers() if '18' in d])"
```

Expected output: `['ODBC Driver 18 for SQL Server']`

### 2. Create virtual environment

```
cd lineage_web
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

### 4. Login to Azure

```
az login
```

This opens a browser window. Sign in with your Ashley Furniture account.  
The app uses `DefaultAzureCredential` which picks up your `az login` session automatically.

---

## Run

```
python app.py
```

Open **http://127.0.0.1:5000** in your browser.

---

## Features

- **Real-time ODBC**: Reads lineage from `utl_pipeline_metadata` on each load
- **DAG visualization**: Left-to-right flow: Raw → BRZ/REF → SLV → GLD
- **Click a node**: Highlights full upstream/downstream chain
- **Filter by layer**: Click layer buttons in the header (BRZ, SLV, GLD, etc.)
- **Search**: Click the search icon to filter nodes by name
- **Refresh ODBC**: Click to reload data from Fabric
- **Import**: Paste lineage text manually
- **Extract**: Pull notebook definitions directly from Fabric API (browser auth)
- **AI Chat**: Ask questions about lineage (requires free Groq API key)
- **Export**: Download lineage as JSON

---

## Configuration

Edit `app.py` lines 21-22 if your Fabric endpoint or database differs:

```python
FABRIC_SERVER = "your-endpoint.datawarehouse.fabric.microsoft.com"
DATABASE      = "SupplyChain_Lakehouse"
```

To find your SQL endpoint: Fabric Portal → Workspace → Lakehouse → Settings → SQL analytics endpoint.

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `No module named 'pyodbc'` | Run `pip install -r requirements.txt` |
| `ODBC Driver 18 not found` | Install ODBC Driver 18 (see Prerequisites) |
| `DefaultAzureCredential failed` | Run `az login` and try again |
| Page shows "Loading from ODBC..." forever | Check that `az login` is done and Fabric endpoint is reachable |
| `Connection refused` on http://127.0.0.1:5000 | Make sure `python app.py` is running in a terminal |

---

## File Structure

```
lineage_web/
  app.py                  # Flask backend (ODBC connection + JSON API)
  requirements.txt        # Python dependencies
  README.md               # This file
  templates/
    lineage.html          # React UI (Cytoscape DAG visualization)
```
