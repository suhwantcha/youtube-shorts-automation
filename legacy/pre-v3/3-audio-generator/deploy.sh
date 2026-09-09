#!/bin/bash

# Phase 3: Audio Generator 배포 스크립트

set -e

echo "========================================="
echo "Phase 3: Audio Generator 배포 시작"
echo "========================================="

# 환경 변수 확인
if [ -z "$GCP_PROJECT_ID" ]; then
    echo "오류: GCP_PROJECT_ID 환경 변수가 설정되지 않았습니다."
    exit 1
fi

if [ -z "$STORAGE_BUCKET_NAME" ]; then
    echo "오류: STORAGE_BUCKET_NAME 환경 변수가 설정되지 않았습니다."
    exit 1
fi

# Cloud Function 배포
echo "Cloud Function 배포 중..."

gcloud functions deploy audio-generator \
    --gen2 \
    --runtime=python311 \
    --region=asia-northeast3 \
    --source=. \
    --entry-point=audio_generator \
    --trigger-http \
    --allow-unauthenticated \
    --set-env-vars=GCP_PROJECT_ID=$GCP_PROJECT_ID,STORAGE_BUCKET_NAME=$STORAGE_BUCKET_NAME \
    --timeout=540s \
    --memory=512MB \
    --max-instances=10

echo ""
echo "========================================="
echo "✅ Phase 3 배포 완료!"
echo "========================================="
echo ""
echo "테스트 URL:"
FUNCTION_URL=$(gcloud functions describe audio-generator --gen2 --region=asia-northeast3 --format='value(serviceConfig.uri)')
echo "$FUNCTION_URL"
echo ""
echo "Health Check:"
echo "curl $FUNCTION_URL/health"
echo ""
echo "테스트 요청:"
echo "curl -X POST $FUNCTION_URL/generate \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"script_text\": \"테스트 음성입니다.\", \"video_id\": \"test_video\"}'"
