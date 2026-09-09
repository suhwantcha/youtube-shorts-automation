#!/bin/bash
gcloud functions deploy content-collector \
  --gen2 \
  --runtime python311 \
  --region asia-northeast3 \
  --source . \
  --entry-point collect_content \
  --trigger-topic content-trigger \
  --set-env-vars GCP_PROJECT_ID=$GCP_PROJECT_ID,REDDIT_CLIENT_ID=$REDDIT_CLIENT_ID,REDDIT_CLIENT_SECRET=$REDDIT_CLIENT_SECRET
