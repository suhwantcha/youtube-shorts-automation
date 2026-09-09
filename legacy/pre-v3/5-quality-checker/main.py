"""
Phase 5: Gmail 품질 검수 시스템
영상 생성 후 관리자에게 이메일을 보내 승인/거부를 받습니다.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google.cloud import firestore
from google.cloud import storage
import functions_framework

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 환경 변수
PROJECT_ID = os.environ.get('GCP_PROJECT_ID')
BUCKET_NAME = os.environ.get('STORAGE_BUCKET_NAME')
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'your-email@example.com')

# OAuth 인증 정보
GMAIL_CLIENT_ID = os.environ.get('GMAIL_CLIENT_ID')
GMAIL_CLIENT_SECRET = os.environ.get('GMAIL_CLIENT_SECRET')
GMAIL_REFRESH_TOKEN = os.environ.get('GMAIL_REFRESH_TOKEN')

# Firestore & Storage
db = firestore.Client()
storage_client = storage.Client()


def get_gmail_service():
    """Gmail API 서비스 생성"""
    creds = Credentials(
        token=None,
        refresh_token=GMAIL_REFRESH_TOKEN,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=GMAIL_CLIENT_ID,
        client_secret=GMAIL_CLIENT_SECRET
    )
    
    # 토큰 갱신
    if creds.expired:
        creds.refresh(Request())
    
    return build('gmail', 'v1', credentials=creds)


def create_approval_email(video_data: Dict[str, Any]) -> MIMEMultipart:
    """
    승인 요청 이메일 생성
    
    Args:
        video_data: 영상 메타데이터
            {
                "video_id": "video_xxx",
                "script_text": "...",
                "video_url": "https://...",
                "thumbnail_url": "https://...",
                "duration": 45.2,
                "mode": "info"
            }
    """
    video_id = video_data['video_id']
    script_text = video_data.get('script_text', 'N/A')
    video_url = video_data.get('video_url', '#')
    thumbnail_url = video_data.get('thumbnail_url', '')
    duration = video_data.get('duration', 0)
    mode = video_data.get('mode', 'info')
    
    # 승인/거부 링크 (Cloud Function 엔드포인트)
    base_url = os.environ.get('APPROVAL_BASE_URL', 'https://YOUR-FUNCTION-URL')
    approve_url = f"{base_url}/approve?video_id={video_id}&action=approve"
    reject_url = f"{base_url}/approve?video_id={video_id}&action=reject"
    
    # HTML 이메일 본문
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                       color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
            .content {{ background: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
            .video-info {{ background: white; padding: 15px; margin: 15px 0; border-left: 4px solid #667eea; }}
            .script {{ background: #fff; padding: 15px; margin: 15px 0; border: 1px solid #e0e0e0; 
                      border-radius: 4px; font-size: 14px; line-height: 1.8; }}
            .buttons {{ margin: 20px 0; text-align: center; }}
            .btn {{ display: inline-block; padding: 12px 30px; margin: 10px; text-decoration: none; 
                    border-radius: 5px; font-weight: bold; font-size: 16px; }}
            .btn-approve {{ background: #10b981; color: white; }}
            .btn-reject {{ background: #ef4444; color: white; }}
            .thumbnail {{ max-width: 100%; border-radius: 8px; margin: 15px 0; }}
            .badge {{ display: inline-block; padding: 4px 12px; border-radius: 12px; 
                     font-size: 12px; font-weight: bold; }}
            .badge-info {{ background: #3b82f6; color: white; }}
            .badge-sales {{ background: #f59e0b; color: white; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>🎬 새 영상 승인 요청</h2>
                <p>생성된 영상을 검토하고 승인/거부해주세요.</p>
            </div>
            
            <div class="content">
                <div class="video-info">
                    <h3>📊 영상 정보</h3>
                    <p><strong>Video ID:</strong> {video_id}</p>
                    <p><strong>모드:</strong> 
                        <span class="badge badge-{'sales' if mode == 'sales' else 'info'}">
                            {'💰 SALES' if mode == 'sales' else 'ℹ️ INFO'}
                        </span>
                    </p>
                    <p><strong>길이:</strong> {duration:.1f}초</p>
                    <p><strong>생성 시간:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>
                
                {'<img src="' + thumbnail_url + '" class="thumbnail" alt="Thumbnail">' if thumbnail_url else ''}
                
                <div class="script">
                    <h4>📝 스크립트</h4>
                    <p>{script_text}</p>
                </div>
                
                <div style="text-align: center; margin: 20px 0;">
                    <a href="{video_url}" style="color: #667eea; text-decoration: none; font-weight: bold;">
                        🎥 영상 미리보기
                    </a>
                </div>
                
                <div class="buttons">
                    <a href="{approve_url}" class="btn btn-approve">✅ 승인 (업로드)</a>
                    <a href="{reject_url}" class="btn btn-reject">❌ 거부 (삭제)</a>
                </div>
                
                <p style="color: #666; font-size: 12px; text-align: center; margin-top: 30px;">
                    승인하면 YouTube, TikTok, Instagram에 자동으로 업로드됩니다.<br>
                    거부하면 영상이 삭제되고 더이상 처리되지 않습니다.
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # 이메일 메시지 생성
    message = MIMEMultipart('alternative')
    message['To'] = ADMIN_EMAIL
    message['From'] = ADMIN_EMAIL
    message['Subject'] = f"[Tech Shorts] 새 영상 승인 요청 - {mode.upper()} 모드"
    
    # HTML 파트 추가
    html_part = MIMEText(html_body, 'html', 'utf-8')
    message.attach(html_part)
    
    return message


def send_email(service, message: MIMEMultipart) -> Dict[str, Any]:
    """Gmail API로 이메일 전송"""
    try:
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        send_message = service.users().messages().send(
            userId='me',
            body={'raw': raw_message}
        ).execute()
        
        logger.info(f"이메일 전송 성공: {send_message['id']}")
        return {'status': 'sent', 'message_id': send_message['id']}
    
    except Exception as e:
        logger.error(f"이메일 전송 실패: {str(e)}")
        raise


def handle_approval_decision(video_id: str, action: str) -> Dict[str, Any]:
    """
    승인/거부 처리
    
    Args:
        video_id: 영상 ID
        action: 'approve' 또는 'reject'
    """
    logger.info(f"승인 결정 처리: video_id={video_id}, action={action}")
    
    # Firestore에서 영상 정보 가져오기
    video_ref = db.collection('videos').document(video_id)
    video_doc = video_ref.get()
    
    if not video_doc.exists:
        raise ValueError(f"Video not found: {video_id}")
    
    if action == 'approve':
        # 승인: Phase 6 (업로드)로 진행
        video_ref.update({
            'approval_status': 'approved',
            'approved_at': firestore.SERVER_TIMESTAMP,
            'phase5_status': 'approved'
        })
        
        logger.info(f"✅ 영상 승인됨: {video_id}")
        return {'status': 'approved', 'message': '영상이 승인되어 업로드 대기열에 추가되었습니다.'}
    
    elif action == 'reject':
        # 거부: 영상 삭제 (옵션)
        video_ref.update({
            'approval_status': 'rejected',
            'rejected_at': firestore.SERVER_TIMESTAMP,
            'phase5_status': 'rejected'
        })
        
        logger.info(f"❌ 영상 거부됨: {video_id}")
        return {'status': 'rejected', 'message': '영상이 거부되었습니다. 더이상 처리되지 않습니다.'}
    
    else:
        raise ValueError(f"Invalid action: {action}")


@functions_framework.http
def quality_checker(request):
    """
    Cloud Function 엔트리포인트
    
    1. POST /send-approval: 승인 요청 이메일 전송
       입력: {video_id, script_text, video_url, ...}
    
    2. GET /approve?video_id=xxx&action=approve/reject: 승인/거부 처리
    """
    
    # Health Check
    if request.path == '/health':
        return json.dumps({'status': 'healthy', 'service': 'quality-checker'})
    
    # CORS 처리
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST',
            'Access-Control-Allow-Headers': 'Content-Type',
        }
        return ('', 204, headers)
    
    try:
        # 1. POST /send-approval: 이메일 전송
        if request.method == 'POST' and '/send-approval' in request.path:
            request_json = request.get_json(silent=True)
            if not request_json or 'video_id' not in request_json:
                return json.dumps({'error': 'Missing video_id'}), 400
            
            # 이메일 생성 및 전송
            gmail_service = get_gmail_service()
            email_message = create_approval_email(request_json)
            send_result = send_email(gmail_service, email_message)
            
            # Firestore 업데이트
            video_id = request_json['video_id']
            db.collection('videos').document(video_id).update({
                'approval_email_sent_at': firestore.SERVER_TIMESTAMP,
                'phase5_status': 'pending_approval'
            })
            
            response_data = {
                'status': 'success',
                'message': 'Approval email sent',
                'email_id': send_result['message_id']
            }
            return json.dumps(response_data), 200
        
        # 2. GET /approve: 승인/거부 처리
        elif request.method == 'GET' and '/approve' in request.path:
            video_id = request.args.get('video_id')
            action = request.args.get('action')
            
            if not video_id or not action:
                return """
                <html><body style="font-family: Arial; text-align: center; padding: 50px;">
                <h2>❌ 오류</h2>
                <p>video_id와 action 파라미터가 필요합니다.</p>
                </body></html>
                """, 400
            
            # 승인/거부 처리
            result = handle_approval_decision(video_id, action)
            
            # 사용자 친화적 HTML 응답
            if action == 'approve':
                html_response = """
                <html><body style="font-family: Arial; text-align: center; padding: 50px;">
                <h1 style="color: #10b981;">✅ 승인 완료!</h1>
                <p style="font-size: 18px;">영상이 승인되었습니다.</p>
                <p>곧 YouTube, TikTok, Instagram에 업로드됩니다.</p>
                <p style="color: #666; margin-top: 30px;">이 창을 닫아도 됩니다.</p>
                </body></html>
                """
            else:
                html_response = """
                <html><body style="font-family: Arial; text-align: center; padding: 50px;">
                <h1 style="color: #ef4444;">❌ 거부 완료</h1>
                <p style="font-size: 18px;">영상이 거부되었습니다.</p>
                <p>더이상 처리되지 않습니다.</p>
                <p style="color: #666; margin-top: 30px;">이 창을 닫아도 됩니다.</p>
                </body></html>
                """
            
            return html_response, 200
        
        else:
            return json.dumps({'error': 'Invalid endpoint'}), 404
    
    except Exception as e:
        logger.error(f"품질 검수 오류: {str(e)}", exc_info=True)
        return json.dumps({
            'status': 'error',
            'error': str(e)
        }), 500


if __name__ == '__main__':
    # 로컬 테스트용
    print("Phase 5: Quality Checker")
    print("=" * 50)
    
    test_video_data = {
        "video_id": "video_test_123",
        "script_text": "오늘은 AI 기술에 대해 알아봅니다...",
        "video_url": "https://example.com/video.mp4",
        "duration": 45.2,
        "mode": "info"
    }
    
    # 이메일 생성 테스트
    message = create_approval_email(test_video_data)
    print("이메일 제목:", message['Subject'])
    print("수신자:", message['To'])
    print("\n이메일 본문 생성 완료!")
