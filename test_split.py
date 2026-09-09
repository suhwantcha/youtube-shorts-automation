# -*- coding: utf-8 -*-
"""Standalone test for subtitle splitting logic"""
import re

def _split_text_to_chunks(text, max_chars=40):
    if not text or not text.strip():
        return []
    text = text.strip()
    raw_sentences = re.split(r'(?<=[.?!])\\s*', text)
    raw_sentences = [s.strip() for s in raw_sentences if s.strip()]
    if not raw_sentences:
        return [text]
    chunks = []
    for sentence in raw_sentences:
        if len(sentence) <= max_chars:
            chunks.append(sentence)
        else:
            sub_parts = re.split(r'(?<=,)\\s*|(?<=\\s)(?=그런데|심지어|하지만|그래서|또한|만약|이게)', sentence)
            sub_parts = [p.strip() for p in sub_parts if p.strip()]
            if len(sub_parts) > 1:
                for part in sub_parts:
                    if len(part) <= max_chars:
                        chunks.append(part)
                    else:
                        words = part.split()
                        current = ""
                        for word in words:
                            test = (current + " " + word).strip() if current else word
                            if len(test) > max_chars and current:
                                chunks.append(current)
                                current = word
                            else:
                                current = test
                        if current:
                            chunks.append(current)
            else:
                words = sentence.split()
                current = ""
                for word in words:
                    test = (current + " " + word).strip() if current else word
                    if len(test) > max_chars and current:
                        chunks.append(current)
                        current = word
                    else:
                        current = test
                if current:
                    chunks.append(current)
    return chunks

# Test
texts = [
    "알고 계셨나요? 단 하나의 소행성이 전 세계 GDP보다 더 큰 가치를 가질 수 있다는 사실을요?",
    "심지어 이는 지구 상 모든 국가의 연간 GDP를 전부 더한 것보다 많은 금액입니다. 그런데 더 놀라운 건, 우리 태양계에는 이런 소행성이 약 1백만 개 이상 존재한다는 사실입니다.",
    "만약 우리가 이런 소행성을 채굴할 수 있다면, 지구의 금속 자원이 몇 천 배 이상 늘어날 수 있습니다. 이게 끝이 아닙니다! 소행성 채굴 기술이 발전하면 우주 건설 산업도 가능해지며, 지구의 자원 고갈 문제를 해결할 수 있는 길이 열립니다."
]

for i, text in enumerate(texts):
    print(f"\nSegment {i+1} ({len(text)} chars):")
    print(f"  Original: {text[:60]}...")
    chunks = _split_text_to_chunks(text)
    for j, c in enumerate(chunks):
        print(f"  -> [{len(c):2d} chars] {c}")
