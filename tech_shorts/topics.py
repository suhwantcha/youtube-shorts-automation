"""Shared topic catalog for discovery, UI and editorial context."""

_ROWS = [
    ('politics', '정치·국제정세', 'politics', 'worldnews'),
    ('society', '사회', 'society', 'news'),
    ('economy', '경제·산업', 'economy', 'Economics'),
    ('it', 'IT·테크', 'technology', 'technology+programming'),
    ('ai', 'AI', 'AI', 'artificial+MachineLearning'),
    ('science', '과학', 'science', 'science'),
    ('space', '우주·천문', 'astronomy', 'space'),
    ('film', '영화·드라마', 'entertainment', 'movies+television'),
    ('music', '음악', 'music', 'Music'),
    ('history', '역사', 'archaeology', 'history'),
    ('psychology', '심리·행동과학', 'psychology', 'psychology'),
    ('nature', '동물·자연', 'wildlife', 'nature'),
    ('environment', '환경·에너지', 'environment', 'environment+energy'),
    ('automotive', '자동차·모빌리티', 'automotive', 'cars'),
    ('food', '음식·문화', 'food', 'food'),
    ('travel', '여행·지리', 'travel', 'travel'),
    ('design', '건축·디자인', 'architecture', 'architecture+Design'),
]
CATEGORIES = {key: dict(id=key, label=label, english_query=english, reddit=reddit)
              for key, label, english, reddit in _ROWS}


def category_info(category="it"):
    if not isinstance(category, str) or category not in CATEGORIES:
        raise ValueError("지원하지 않는 분야입니다. 목록에서 분야를 선택해주세요.")
    return CATEGORIES[category]


def category_choices():
    return [{"id": c["id"], "label": c["label"]} for c in CATEGORIES.values()]
