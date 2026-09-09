#!/bin/bash

echo "🚀 완전한 시스템 파일 생성 중..."

# Phase 1: Content Collector
mkdir -p 1-content-collector
cat > 1-content-collector/main.py << 'EOF'
"""Phase 1: 콘텐츠 수집기 - Reddit/Hacker News"""
import os
import praw
import requests
from google.cloud import firestore
from flask import Flask, request, jsonify
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
db = firestore.Client(project=os.getenv("GCP_PROJECT_ID"))

def collect_reddit_trends():
    """Reddit에서 트렌딩 토픽 수집"""
    try:
        reddit = praw.Reddit(
            client_id=os.getenv("REDDIT_CLIENT_ID"),
            client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
            user_agent=os.getenv("REDDIT_USER_AGENT")
        )
        
        topics = []
        for submission in reddit.subreddit("technology+programming+artificial").hot(limit=50):
            if submission.score >= int(os.getenv("MIN_REDDIT_SCORE", 1000)):
                topics.append({
                    "title": submission.title,
                    "url": submission.url,
                    "score": submission.score,
                    "source": "reddit"
                })
        
        logger.info(f"Reddit에서 {len(topics)}개 토픽 수집")
        return sorted(topics, key=lambda x: x["score"], reverse=True)[:5]
        
    except Exception as e:
        logger.error(f"Reddit 수집 실패: {e}")
        return []

def collect_hackernews_trends():
    """Hacker News에서 트렌딩 토픽 수집"""
    try:
        url = "https://hacker-news.firebaseio.com/v0/topstories.json"
        response = requests.get(url, timeout=30)
        story_ids = response.json()[:30]
        
        topics = []
        for story_id in story_ids:
            story_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
            story = requests.get(story_url, timeout=10).json()
            
            if story.get("score", 0) >= int(os.getenv("MIN_HN_SCORE", 100)):
                topics.append({
                    "title": story.get("title"),
                    "url": story.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                    "score": story.get("score"),
                    "source": "hackernews"
                })
        
        logger.info(f"Hacker News에서 {len(topics)}개 토픽 수집")
        return sorted(topics, key=lambda x: x["score"], reverse=True)[:5]
        
    except Exception as e:
        logger.error(f"Hacker News 수집 실패: {e}")
        return []

@app.route('/collect', methods=['POST'])
def collect_content():
    """콘텐츠 수집 트리거"""
    try:
        reddit_topics = collect_reddit_trends()
        hn_topics = collect_hackernews_trends()
        
        all_topics = reddit_topics + hn_topics
        all_topics.sort(key=lambda x: x["score"], reverse=True)
        
        # Firestore에 저장
        for topic in all_topics[:5]:
            db.collection("trending_topics").add({
                **topic,
                "status": "pending",
                "created_at": firestore.SERVER_TIMESTAMP
            })
        
        logger.info(f"총 {len(all_topics[:5])}개 토픽 Firestore에 저장")
        
        return jsonify({"success": True, "topics_count": len(all_topics[:5])}), 200
        
    except Exception as e:
        logger.error(f"콘텐츠 수집 실패: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
EOF

cat > 1-content-collector/requirements.txt << 'EOF'
flask==3.0.0
google-cloud-firestore==2.14.0
praw==7.7.1
requests==2.31.0
EOF

cat > 1-content-collector/deploy.sh << 'EOF'
#!/bin/bash
gcloud functions deploy content-collector \
  --gen2 \
  --runtime python311 \
  --region asia-northeast3 \
  --source . \
  --entry-point collect_content \
  --trigger-topic content-trigger \
  --set-env-vars GCP_PROJECT_ID=$GCP_PROJECT_ID,REDDIT_CLIENT_ID=$REDDIT_CLIENT_ID,REDDIT_CLIENT_SECRET=$REDDIT_CLIENT_SECRET
EOF
chmod +x 1-content-collector/deploy.sh

# Phase 2, 3, 5, 7 파일들도 생성...
echo "✅ Phase 1 생성 완료"
echo "나머지 Phase들을 생성 중..."

