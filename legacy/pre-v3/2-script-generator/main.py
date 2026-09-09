"""
Phase 2: 스크립트 생성기
- GPT-4o 기반 바이럴 스크립트 생성
- "Jab, Jab, Jab, Right Hook" 전략 적용
- Info 모드: 스토리텔링 기반 몰입형 구조 ⭐ 개선
- Sales 모드: Agitation + Solution 대폭 확장
- 20~30% 확률로 Sales 모드 발동
"""

import os
import random
import logging
from flask import Flask, request, jsonify
from google.cloud import firestore
from openai import OpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 환경 변수
GCP_PROJECT = os.getenv("GCP_PROJECT_ID")
SALES_MODE_PROBABILITY = float(os.getenv("SALES_MODE_PROBABILITY", "0.25"))  # 기본 25%

# 클라이언트 초기화
db = firestore.Client(project=GCP_PROJECT)
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def generate_info_script(topic: str) -> dict:
    """
    Info 모드: 스토리텔링 기반 몰입형 스크립트 생성 ⭐ 대폭 개선
    
    Args:
        topic: 뉴스 토픽 제목
        
    Returns:
        {"script": str, "mode": "info", "hook": str}
    """
    try:
        logger.info(f"Info 모드 스크립트 생성: {topic}")
        
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a viral short-form video script writer for IT/Tech news. "
                        "Create HIGHLY ENGAGING 50-60 second scripts in Korean that capture "
                        "viewers' attention from start to finish.\n\n"
                        
                        "📖 STORYTELLING STRUCTURE (몰입형 구조):\n\n"
                        
                        "1. Hook - 충격적 질문/사실 (3-5초, 1-2문장):\n"
                        "   - 시청자의 기존 상식을 뒤집는 충격적인 사실\n"
                        "   - 또는 강렬한 질문으로 호기심 자극\n"
                        "   - 예시:\n"
                        "     ❌ '오늘은 AI 뉴스를 알려드릴게요' (지루함)\n"
                        "     ✅ '이 AI가 방금 의사 시험에서 인간을 이겼습니다' (충격)\n"
                        "     ✅ '당신이 지금 보는 영상, 실은 AI가 만든 거라면?' (호기심)\n\n"
                        
                        "2. Context Setup - 배경 설명 (8-12초, 2-3문장):\n"
                        "   - 왜 이게 중요한지, 어떤 배경이 있는지 설명\n"
                        "   - 시청자가 이해할 수 있도록 쉽게 풀어서\n"
                        "   - 구체적인 숫자, 사실, 비유 활용\n"
                        "   - 예시:\n"
                        "     '실제로 구글이 개발한 Med-PaLM 2는\n"
                        "      미국 의사 면허 시험에서 85% 이상의 정확도를 기록했습니다.\n"
                        "      이건 평균적인 의대생보다 높은 점수죠.'\n\n"
                        
                        "3. Conflict/Problem - 갈등/문제 제기 (10-15초, 3-4문장):\n"
                        "   - 이 기술/뉴스가 가져올 변화나 논란\n"
                        "   - '그런데', '하지만', '문제는' 같은 전환어 사용\n"
                        "   - 양면성이나 딜레마 제시로 긴장감 조성\n"
                        "   - 예시:\n"
                        "     '그런데 여기서 문제가 생깁니다.\n"
                        "      AI가 진단을 내리면, 잘못됐을 때 누가 책임질까요?\n"
                        "      의사? 개발자? 아니면 병원?\n"
                        "      더 무서운 건, AI가 편향된 데이터로 학습하면\n"
                        "      특정 인종이나 성별에게 잘못된 진단을 내릴 수도 있다는 거죠.'\n\n"
                        
                        "4. Resolution/Insight - 해결책/통찰 (15-20초, 4-5문장):\n"
                        "   - 전문가 의견, 실제 사례, 미래 전망 제시\n"
                        "   - 긍정적 가능성과 주의할 점 균형있게\n"
                        "   - 시청자에게 생각할 거리 제공\n"
                        "   - 예시:\n"
                        "     '전문가들은 이렇게 말합니다.\n"
                        "      AI는 의사를 대체하는 게 아니라 보조하는 도구가 될 거라고요.\n"
                        "      실제로 한국의 한 대학병원에서는\n"
                        "      AI가 의사가 놓친 암 초기 증상을 발견해 환자를 살린 사례도 있습니다.\n"
                        "      핵심은 AI를 어떻게 책임감 있게 활용하느냐죠.'\n\n"
                        
                        "5. Call-to-Action - 마무리 (5-7초, 2-3문장):\n"
                        "   - 시청자의 다음 행동 유도\n"
                        "   - 구독, 좋아요, 댓글 요청\n"
                        "   - 열린 질문으로 참여 유도\n"
                        "   - 예시:\n"
                        "     '여러분은 AI 의사에게 진료 받으실 건가요?\n"
                        "      댓글로 의견 남겨주세요!\n"
                        "      구독하시면 최신 IT 트렌드를 매일 받아보실 수 있습니다!'\n\n"
                        
                        "🎯 ENGAGEMENT TECHNIQUES (몰입 기법):\n"
                        "- ✅ 구체적인 숫자와 사실 사용 (예: '85% 정확도', '3초 만에')\n"
                        "- ✅ 생생한 비유와 예시 (예: '스마트폰 100만 대를 동시에 켠 것과 같은 전력')\n"
                        "- ✅ 질문 던지기 (예: '그렇다면 우리는 어떻게 해야 할까요?')\n"
                        "- ✅ '그런데', '하지만', '더 놀라운 건' 같은 전환어로 긴장감 유지\n"
                        "- ✅ '실제로', '놀랍게도', '믿기 힘들지만' 같은 강조어 사용\n"
                        "- ✅ 시청자에게 직접 말 걸기 (예: '여러분은 어떻게 생각하시나요?')\n\n"
                        
                        "❌ AVOID (피해야 할 것):\n"
                        "- ❌ 평범한 시작 ('오늘은 ~에 대해 알려드릴게요')\n"
                        "- ❌ 단순 나열식 정보 전달\n"
                        "- ❌ 전문 용어 남발 (쉽게 풀어서 설명)\n"
                        "- ❌ 지루한 통계 나열 (스토리에 녹여서)\n"
                        "- ❌ 일방적 주장 (양면성 제시)\n\n"
                        
                        "📏 FORMAT:\n"
                        "- Style: 대화체, 존댓말, 친근하면서도 전문적\n"
                        "- Tone: 열정적이고 호기심 넘치는\n"
                        "- Emojis: 1-2개만 자연스럽게 (과도하지 않게)\n"
                        "- Target length: 50-60 seconds spoken (280-350 characters Korean)\n"
                        "- Pacing: 빠르게 진행되지만 이해하기 쉽게\n\n"
                        
                        "🎬 VIRAL ELEMENTS:\n"
                        "- Hook에서 3초 안에 주목도 확보\n"
                        "- Conflict로 중간 이탈 방지\n"
                        "- Resolution으로 만족도 제공\n"
                        "- CTA로 구독/좋아요 유도\n"
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"토픽: {topic}\n\n"
                        "위의 5단계 스토리텔링 구조를 정확히 따라서\n"
                        "시청자가 끝까지 몰입해서 볼 수 있는\n"
                        "바이럴 숏폼 스크립트를 한국어로 작성해주세요.\n\n"
                        "⚠️ 중요:\n"
                        "- Hook은 반드시 충격적이거나 호기심 자극적이어야 함\n"
                        "- Conflict에서 긴장감 조성 필수\n"
                        "- 구체적인 숫자, 사례, 비유 풍부하게 사용\n"
                        "- 시청자에게 직접 말 걸듯이 작성"
                    )
                }
            ],
            temperature=0.85,
            max_tokens=500
        )
        
        script = response.choices[0].message.content.strip()
        
        # Hook 추출 (첫 문장)
        hook = script.split('.')[0] + '.'
        
        # 스크립트 길이 검증
        if len(script) < 250:
            logger.warning(f"Info 스크립트가 너무 짧음 ({len(script)}자). 최소 250자 권장.")
        
        return {
            "script": script,
            "mode": "info",
            "hook": hook,
            "word_count": len(script),
            "estimated_duration": len(script) * 0.15  # 한글 1자당 약 0.15초
        }
        
    except Exception as e:
        logger.error(f"Info 스크립트 생성 실패: {e}")
        raise


def generate_sales_script(topic: str, product_info: dict = None) -> dict:
    """
    Sales 모드: 제품 광고 스크립트 생성 (Jab, Jab, Jab, Right Hook)
    Agitation + Solution Tease 대폭 확장
    
    Args:
        topic: 뉴스 토픽 제목
        product_info: 제품 정보 (선택)
            - name: 제품 이름
            - benefit: 핵심 혜택
            - cta: Call-to-action 문구
        
    Returns:
        {"script": str, "mode": "sales", "hook": str, "product": str}
    """
    try:
        logger.info(f"Sales 모드 스크립트 생성: {topic}")
        
        # 기본 제품 정보 (환경 변수에서 가져올 수도 있음)
        if not product_info:
            product_info = {
                "name": "IT 학습 솔루션",  # 예시
                "benefit": "하루 10분으로 최신 IT 트렌드를 완벽하게 이해하고 실무에 바로 적용",
                "cta": "지금 바로 고정 댓글에서 무료 체험판 받아가세요"
            }
        
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a conversion-focused sales script writer for IT/Tech products. "
                        "Create a 50-60 second script in Korean with the following EXPANDED structure:\n\n"
                        
                        "1. Problem Hook (3-5초, 1-2문장):\n"
                        "   - 시청자의 현실적인 고민/문제를 구체적으로 제기\n"
                        "   - 예: 'IT 트렌드를 따라가기 힘드시죠? 매일 쏟아지는 뉴스에 압도당하고 계신가요?'\n\n"
                        
                        "2. Agitation (15-20초, 4-6문장) ⭐ 대폭 확장:\n"
                        "   - 문제의 심각성을 구체적인 예시와 함께 깊이 있게 설명\n"
                        "   - 시청자가 겪는 실제 상황을 디테일하게 묘사\n"
                        "   - 예시:\n"
                        "     '하루만 놓쳐도 동료들과의 대화에서 뒤처진 느낌...\n"
                        "      회의 시간에 최신 기술 용어가 나오면 당황하게 되고,\n"
                        "      주말에 몰아서 공부하려 해도 어디서부터 시작해야 할지 막막합니다.\n"
                        "      결국 YouTube만 띄워놓고 정작 중요한 건 놓치게 되죠.\n"
                        "      이런 악순환이 반복되면서 점점 자신감도 떨어집니다.'\n\n"
                        
                        "3. Solution Tease (20-25초, 5-7문장) ⭐ 대폭 확장:\n"
                        "   - 해결책의 구체적인 메커니즘과 작동 방식 설명\n"
                        "   - 왜 이 방법이 효과적인지 논리적으로 제시\n"
                        "   - 실제 사용 시나리오와 결과를 생생하게 묘사\n"
                        "   - 예시:\n"
                        "     '그런데 하루 10분으로 이 모든 걸 해결하는 방법이 있습니다.\n"
                        "      매일 아침 출근길에 핵심만 쏙쏙 정리된 큐레이션을 받고,\n"
                        "      점심시간에는 5분짜리 실전 예제로 바로 적용해보고,\n"
                        "      퇴근 후에는 오늘 배운 내용을 복습 퀴즈로 확실하게 내 것으로 만듭니다.\n"
                        "      AI가 자동으로 내 학습 패턴을 분석해서\n"
                        "      꼭 필요한 내용만 딱 맞춰 추천해주기 때문에\n"
                        "      시간 낭비 없이 효율적으로 성장할 수 있습니다.'\n\n"
                        
                        "4. CTA (5-7초, 2-3문장):\n"
                        "   - 구체적인 혜택과 함께 명확한 행동 유도\n"
                        "   - 긴급성과 희소성 강조\n"
                        "   - 예: '지금 바로 고정 댓글에서 7일 무료 체험을 시작하세요.\n"
                        "           선착순 100명에게만 프리미엄 기능도 무료로 드립니다!'\n\n"
                        
                        "CRITICAL RULES:\n"
                        "- 제품 이름을 직접 언급하지 말 것 (플랫폼 정책)\n"
                        "- '이 방법', '이 시스템', '이 플랫폼' 같은 간접 표현 사용\n"
                        "- 구체적인 가격이나 링크는 넣지 말 것\n"
                        "- Agitation과 Solution은 각각 최소 4-6문장씩 작성\n"
                        "- 자연스럽게 정보 제공하는 것처럼 보이되, 설득력 있게\n"
                        "- 실제 사용 시나리오를 구체적으로 묘사\n\n"
                        
                        "Tone: 친근하고 도움이 되는 느낌, 존댓말 사용\n"
                        "Total length: 50-60 seconds when spoken (280-350 characters in Korean)"
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"토픽: {topic}\n"
                        f"제품 혜택: {product_info['benefit']}\n"
                        f"CTA: {product_info['cta']}\n\n"
                        "Sales 스크립트를 한국어로 작성해주세요.\n"
                        "⚠️ 중요: Agitation과 Solution Tease를 각각 4-6문장씩 풍부하게 작성하여\n"
                        "시청자가 충분히 납득하고 신뢰할 수 있도록 해주세요."
                    )
                }
            ],
            temperature=0.85,
            max_tokens=500
        )
        
        script = response.choices[0].message.content.strip()
        
        # Hook 추출
        hook = script.split('.')[0] + '.'
        
        # 스크립트 길이 검증
        if len(script) < 250:
            logger.warning(f"Sales 스크립트가 너무 짧음 ({len(script)}자). 최소 250자 권장.")
        
        return {
            "script": script,
            "mode": "sales",
            "hook": hook,
            "product": product_info['name'],
            "word_count": len(script),
            "estimated_duration": len(script) * 0.15  # 한글 1자당 약 0.15초
        }
        
    except Exception as e:
        logger.error(f"Sales 스크립트 생성 실패: {e}")
        raise


@app.route('/generate-script', methods=['POST'])
def generate_script():
    """
    스크립트 생성 엔드포인트
    
    Request Body:
    {
        "topic_id": "Firestore trending_topics 문서 ID",
        "force_mode": "info" | "sales" (선택, 강제 모드 지정)
    }
    """
    try:
        data = request.get_json()
        topic_id = data.get("topic_id")
        force_mode = data.get("force_mode")  # 테스트용
        
        if not topic_id:
            return jsonify({"error": "topic_id가 필요합니다"}), 400
        
        # Firestore에서 토픽 정보 가져오기
        topic_ref = db.collection("trending_topics").document(topic_id)
        topic_doc = topic_ref.get()
        
        if not topic_doc.exists:
            return jsonify({"error": "토픽을 찾을 수 없습니다"}), 404
        
        topic_data = topic_doc.to_dict()
        topic_title = topic_data.get("title")
        
        # 모드 결정 ⭐ Jab, Jab, Jab, Right Hook 전략
        if force_mode:
            mode = force_mode
            logger.info(f"강제 모드: {mode}")
        else:
            # 20~30% 확률로 Sales 모드
            random_value = random.random()
            mode = "sales" if random_value < SALES_MODE_PROBABILITY else "info"
            logger.info(f"자동 모드 선택: {mode} (확률: {random_value:.2f})")
        
        # 스크립트 생성
        if mode == "sales":
            result = generate_sales_script(topic_title)
        else:
            result = generate_info_script(topic_title)
        
        # Firestore에 저장
        script_ref = db.collection("scripts").add({
            **result,
            "topic_id": topic_id,
            "topic_title": topic_title,
            "status": "pending_audio",
            "created_at": firestore.SERVER_TIMESTAMP
        })
        
        script_id = script_ref[1].id
        
        # 토픽 상태 업데이트
        topic_ref.update({"status": "script_generated"})
        
        logger.info(f"스크립트 생성 완료 [{mode}]: {script_id} ({result.get('word_count')}자, {result.get('estimated_duration', 0):.1f}초)")
        
        return jsonify({
            "success": True,
            "script_id": script_id,
            "mode": mode,
            "script": result["script"],
            "hook": result["hook"],
            "word_count": result.get("word_count"),
            "estimated_duration": result.get("estimated_duration", 0)
        }), 200
        
    except Exception as e:
        logger.error(f"스크립트 생성 실패: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/stats', methods=['GET'])
def get_stats():
    """
    스크립트 생성 통계
    
    Returns:
        Info vs Sales 모드 비율, 평균 길이 등
    """
    try:
        scripts = db.collection("scripts").stream()
        
        stats = {
            "total": 0,
            "info": 0,
            "sales": 0,
            "avg_length_info": 0,
            "avg_length_sales": 0,
            "avg_duration_info": 0,
            "avg_duration_sales": 0
        }
        
        info_lengths = []
        sales_lengths = []
        info_durations = []
        sales_durations = []
        
        for script in scripts:
            data = script.to_dict()
            stats["total"] += 1
            mode = data.get("mode", "info")
            stats[mode] += 1
            
            word_count = data.get("word_count", 0)
            duration = data.get("estimated_duration", 0)
            
            if mode == "info":
                info_lengths.append(word_count)
                info_durations.append(duration)
            else:
                sales_lengths.append(word_count)
                sales_durations.append(duration)
        
        stats["info_percentage"] = (stats["info"] / stats["total"] * 100) if stats["total"] > 0 else 0
        stats["sales_percentage"] = (stats["sales"] / stats["total"] * 100) if stats["total"] > 0 else 0
        
        stats["avg_length_info"] = sum(info_lengths) / len(info_lengths) if info_lengths else 0
        stats["avg_length_sales"] = sum(sales_lengths) / len(sales_lengths) if sales_lengths else 0
        
        stats["avg_duration_info"] = sum(info_durations) / len(info_durations) if info_durations else 0
        stats["avg_duration_sales"] = sum(sales_durations) / len(sales_durations) if sales_durations else 0
        
        return jsonify(stats), 200
        
    except Exception as e:
        logger.error(f"통계 조회 실패: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
