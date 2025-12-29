#!/bin/bash

# Phase 4: Video Editor 배포 스크립트

echo "🚀 Phase 4: Video Editor (Cloud Run) 배포 중..."

# 프로젝트 ID 확인
if [ -z "$GCP_PROJECT_ID" ]; then
    echo "❌ GCP_PROJECT_ID 환경 변수가 설정되지 않았습니다."
    exit 1
fi

# 서비스 이름
SERVICE_NAME="video-editor"
REGION="asia-northeast3"

echo "📦 Docker 이미지 빌드 중..."

# Cloud Build를 사용하여 이미지 빌드 및 배포
gcloud builds submit --tag gcr.io/$GCP_PROJECT_ID/$SERVICE_NAME

echo "🚢 Cloud Run에 배포 중..."

gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$GCP_PROJECT_ID/$SERVICE_NAME \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 600s \
  --set-env-vars GCP_PROJECT_ID=$GCP_PROJECT_ID,STORAGE_BUCKET_NAME=$STORAGE_BUCKET_NAME,PEXELS_API_KEY=$PEXELS_API_KEY,OPENAI_API_KEY=$OPENAI_API_KEY

echo "✅ Phase 4 배포 완료!"

# 서비스 URL 출력
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')
echo "🔗 서비스 URL: $SERVICE_URL"

# 헬스 체크 및 폰트 확인
echo ""
echo "🔍 헬스 체크 및 한글 폰트 확인 중..."
curl -s $SERVICE_URL/health | python3 -m json.tool
