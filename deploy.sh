#!/bin/bash

# Configuration
PROJECT_ID="bookerai-474300"
SERVICE_NAME="bookerai-app"
REGION="us-central1"  # Adjust if needed, e.g. us-east1

# Supabase Credentials
SUPABASE_URL="https://ctwjbibinzhhiftqlbow.supabase.co"
SUPABASE_KEY="sb_publishable_YppD7iwVYp29xtnZFPCK4w_ykGB5lUd"

echo "Deploying $SERVICE_NAME to $REGION..."

gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --allow-unauthenticated \
  --set-env-vars "SUPABASE_URL=$SUPABASE_URL,SUPABASE_KEY=$SUPABASE_KEY"

echo "Deployment complete!"
