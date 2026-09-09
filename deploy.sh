#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
: "${STORAGE_BUCKET_NAME:?Set STORAGE_BUCKET_NAME}"
: "${SHORTS_SERVICE_ACCOUNT:?Set the Cloud Run service account email}"
: "${SHORTS_SECRETS:?Set Secret Manager bindings: SHORTS_API_TOKEN=studio-token:latest,OPENAI_API_KEY=openai-key:latest,PEXELS_API_KEY=pexels-key:latest}"
REGION="${REGION:-asia-northeast3}"
SERVICE_NAME="${SERVICE_NAME:-tech-shorts-studio}"
case ",${SHORTS_SECRETS}," in
  *,SHORTS_API_TOKEN=*) ;;
  *) echo 'SHORTS_SECRETS must bind SHORTS_API_TOKEN.' >&2; exit 1 ;;
esac
gcloud run deploy "$SERVICE_NAME" --project "$GCP_PROJECT_ID" --region "$REGION" \
  --source . --service-account "$SHORTS_SERVICE_ACCOUNT" \
  --allow-unauthenticated --memory 4Gi --cpu 2 --timeout 3600 \
  --min-instances 1 --max-instances 1 --concurrency 8 --no-cpu-throttling \
  --set-env-vars "SHORTS_BACKEND=firestore,SHORTS_SYNC_GCS=true,GCP_PROJECT_ID=$GCP_PROJECT_ID,STORAGE_BUCKET_NAME=$STORAGE_BUCKET_NAME,GCS_SIGNING_SERVICE_ACCOUNT=$SHORTS_SERVICE_ACCOUNT" \
  --set-secrets "$SHORTS_SECRETS"
SERVICE_URL="$(gcloud run services describe "$SERVICE_NAME" --project "$GCP_PROJECT_ID" --region "$REGION" --format='value(status.url)')"
gcloud run services update "$SERVICE_NAME" --project "$GCP_PROJECT_ID" --region "$REGION" \
  --update-env-vars "SHORTS_BASE_URL=$SERVICE_URL"
printf 'Studio: %s\n' "$SERVICE_URL"
