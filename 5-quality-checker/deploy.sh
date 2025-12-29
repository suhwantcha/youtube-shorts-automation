#!/bin/bash

# Phase 5: Quality Checker 배포 스크립트

set -e

echo "========================================="
echo "Phase 5: Quality Checker 배포 시작"
echo "========================================="

# 환경 변수 확인
if [ -z "$GCP_PROJECT_ID" ]; then
    echo "오류: GCP_PROJECT_ID 환경 변수가 설정되지 않았습니다."
    exit 1
fi

if [ -z "$GMAIL_CLIENT_ID" ] || [ -z "$GMAIL_REFRESH_TOKEN" ]; then
    echo "⚠️  경고: Gmail OAuth 인증 정보가 설정되지 않았습니다."
    echo "    GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN을 설정하세요."
fi

# Cloud Function 배포
echo "Cloud Function 배포 중..."

gcloud functions deploy quality-checker \
    --gen2 \
    --runtime=python311 \
    --region=asia-northeast3 \
    --source=. \
    --entry-point=quality_checker \
    --trigger-http \
    --allow-unauthenticated \
    --set-env-vars=GCP_PROJECT_ID=$GCP_PROJECT_ID,STORAGE_BUCKET_NAME=$STORAGE_BUCKET_NAME,ADMIN_EMAIL=$ADMIN_EMAIL,GMAIL_CLIENT_ID=$GMAIL_CLIENT_ID,GMAIL_CLIENT_SECRET=$GMAIL_CLIENT_SECRET,GMAIL_REFRESH_TOKEN=$GMAIL_REFRESH_TOKEN \
    --timeout=60s \
    --memory=256MB \
    --max-instances=5

echo ""
echo "========================================="
echo "✅ Phase 5 배포 완료!"
echo "========================================="
echo ""
FUNCTION_URL=$(gcloud functions describe quality-checker --gen2 --region=asia-northeast3 --format='value(serviceConfig.uri)')
echo "Function URL: $FUNCTION_URL"
echo ""
echo "이제 .env 파일에 다음을 추가하세요:"
echo "APPROVAL_BASE_URL=$FUNCTION_URL"
echo ""
echo "Health Check:"
echo "curl $FUNCTION_URL/health"
echo ""
echo "테스트 이메일 전송:"
echo "curl -X POST $FUNCTION_URL/send-approval \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"video_id\": \"test_123\", \"script_text\": \"테스트\", \"video_url\": \"https://example.com\", \"duration\": 30, \"mode\": \"info\"}'"
