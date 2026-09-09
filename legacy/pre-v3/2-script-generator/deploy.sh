#!/bin/bash

# Phase 2: Script Generator 배포 스크립트

echo "🚀 Phase 2: Script Generator 배포 중..."

gcloud functions deploy script-generator \
  --gen2 \
  --runtime python311 \
  --region asia-northeast3 \
  --source . \
  --entry-point generate_script \
  --trigger-http \
  --allow-unauthenticated \
  --set-env-vars GCP_PROJECT_ID=$GCP_PROJECT_ID,OPENAI_API_KEY=$OPENAI_API_KEY,SALES_MODE_PROBABILITY=0.25 \
  --timeout=300s \
  --memory=512MB

echo "✅ Phase 2 배포 완료!"
