#!/bin/bash

# ==============================================================================
# GCP Deployment and Configuration Script for Automated Weekly Email Reports
# ==============================================================================
# This script outlines the steps to deploy the Cloud Function and configure
# Cloud Scheduler for automated weekly traffic report emails.
#
# Before running, ensure you have:
# 1. Google Cloud SDK (gcloud CLI) installed and authenticated.
# 2. Your GCP project selected (`gcloud config set project YOUR_PROJECT_ID`).
# 3. Enabled Cloud Functions, Cloud Scheduler, and Cloud Firestore APIs in your GCP project.
# 4. Generated a Gmail App Password if using a Gmail sender account.
# ==============================================================================

echo "----------------------------------------------------------------------"
echo "Step 1: Deploy the Cloud Function"
echo "----------------------------------------------------------------------"
echo "This command deploys the 'send_weekly_report_cf' Cloud Function."
echo "IMPORTANT: Replace YOUR_SENDER_EMAIL, YOUR_APP_PASSWORD, and YOUR_GCP_PROJECT_ID"
echo "           with your actual values."
echo "           The TIMEZONE is set to America/Chicago by default, adjust if needed."

gcloud functions deploy send_weekly_report_cf \
  --runtime python39 \
  --trigger-http \
  --entry-point send_weekly_report_cf \
  --source . \
  --memory 256MB \
  --timeout 300s \
  --set-env-vars SENDER_EMAIL=arunprojectcse@gmail.com,SENDER_PASSWORD=fedceeiaixnumrtb,TIMEZONE=America/Chicago \
  --region us-south1 \
  --allow-unauthenticated \
  --project trafxcloud
gcloud functions deploy send_weekly_report_cf --runtime python39 --trigger-http --entry-point send_weekly_report_cf --source . --memory 256MB --timeout 300s --set-env-vars SENDER_EMAIL=arunprojectcse@gmail.com,SENDER_PASSWORD=fedceeiaixnumrtb,TIMEZONE=America/Chicago --region us-south1 --allow-unauthenticated --project trafxcloud
gcloud functions deploy send_weekly_report_cf --runtime python39 --trigger-http --entry-point send_weekly_report_cf --source . --memory 256MB --timeout 300s --set-env-vars

gcloud functions deploy send_weekly_report_cf --runtime python39 --trigger-http --entry-point send_weekly_report_cf --source . --memory 256MB --timeout 300s --set-env-vars "SENDER_EMAIL=arunprojectcse@gmail.com,SENDER_PASSWORD=fedceeiaixnumrtb,TIMEZONE=America/Chicago" --region us-south1 --allow-unauthenticated --project trafxcloud
echo ""
echo "----------------------------------------------------------------------"
echo "Step 2: Get the Cloud Function's HTTP Trigger URL"
echo "----------------------------------------------------------------------"
echo "After successful deployment, retrieve the Cloud Function's trigger URL."
echo "You can find this in the GCP Console under Cloud Functions -> 'send_weekly_report_cf' -> Trigger tab,"
echo "or by running the following command:"

echo "gcloud functions describe send_weekly_report_cf --region us-south1 --format='value(httpsTrigger.url)'"

echo ""
echo "Once you have the URL, save it. Example: https://us-south1-YOUR_GCP_PROJECT_ID.cloudfunctions.net/send_weekly_report_cf"
echo ""

gcloud scheduler jobs create http weekly-report-job --schedule "0 8 * * 1" --uri "https://us-south1-trafxcloud.cloudfunctions.net/send_weekly_report_cf" --http-method GET --time-zone "America/Chicago" --project trafxcloud

echo "----------------------------------------------------------------------"
echo "Step 3: Configure Cloud Scheduler"
echo "----------------------------------------------------------------------"
echo "This command creates a Cloud Scheduler job to trigger the Cloud Function weekly."
echo "The schedule is set for 08:00 AM every Monday (0 8 * * 1)."
echo "IMPORTANT: Replace YOUR_CLOUD_FUNCTION_HTTP_TRIGGER_URL and YOUR_GCP_PROJECT_ID"
echo "           with your actual values obtained from Step 2 and your project ID."

gcloud scheduler jobs create http weekly-report-job \
  --schedule "0 8 * * 1" \
  --uri "YOUR_CLOUD_FUNCTION_HTTP_TRIGGER_URL" \
  --http-method GET \
  --time-zone "America/Chicago" \
  --project YOUR_GCP_PROJECT_ID

echo ""
echo "----------------------------------------------------------------------"
echo "Permissions Reminder:"
echo "----------------------------------------------------------------------"
echo "Ensure the Cloud Function's service account (default: YOUR_GCP_PROJECT_ID@appspot.gserviceaccount.com)"
echo "has the necessary permissions to access Firestore (e.g., 'Cloud Datastore User' role)."
echo "You can manage these permissions in the GCP Console under IAM & Admin -> IAM."
echo ""
echo "Deployment steps complete. Please execute the commands in your terminal after replacing placeholders."
echo "----------------------------------------------------------------------"
