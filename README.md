# BookerAI (Flask) on Cloud Run with Google Sheets

This is a ready-to-deploy scaffold for a Python (Flask) app with an HTML frontend and Google Sheets storage.

## Quick Start

### 1) Local test
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export SHEET_ID="<YOUR_SHEET_ID>"
export SHEET_NAME="Barbers"

# For local dev, easiest is a service account JSON:
export GOOGLE_APPLICATION_CREDENTIALS="/absolute/path/sa.json"

python app.py
# open http://localhost:8080
```

### 2) Cloud Run (production)
- Create/select a GCP project and enable billing.
- Enable APIs:
  - Cloud Run Admin API
  - Cloud Build API
  - Secret Manager API (only needed for key-based)
  - Google Sheets API
  - Google Drive API
- Create a Cloud Run runtime service account and deploy with it.
- Share your Sheet with that service account (Editor).

Deploy:
```bash
PROJECT_ID="<YOUR_PROJECT>"
gcloud config set project $PROJECT_ID

gcloud services enable run.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com sheets.googleapis.com drive.googleapis.com

gcloud iam service-accounts create bookerai-runner --display-name="BookerAI Cloud Run runtime"
RUNNER_SA="bookerai-runner@${PROJECT_ID}.iam.gserviceaccount.com"

REGION="us-central1"
SERVICE="bookerai"

gcloud run deploy "$SERVICE"   --source .   --region "$REGION"   --allow-unauthenticated   --min-instances=1   --service-account "$RUNNER_SA"   --set-env-vars SHEET_ID=<YOUR_SHEET_ID>,SHEET_NAME=Barbers
```

### 3) Test
```bash
curl -s https://<YOUR_SERVICE_URL>/healthz
curl -s -X POST https://<YOUR_SERVICE_URL>/api/barbers   -H 'content-type: application/json'   -d '{"name":"Test Barber","email":"test@example.com","password":"secret","phone":"555-0000","location":"Lubbock","bio":"fade specialist"}'
```

### Notes
- The app reads Google credentials via the following priority:
  1. `SECRET_GCP_SA` (JSON string from Secret Manager)
  2. `GOOGLE_APPLICATION_CREDENTIALS` (file path to JSON key) — best for local dev
  3. **Application Default Credentials** — best on Cloud Run with the service account
- Keep secrets out of your repo. Use Secret Manager in production if you choose key-based.
