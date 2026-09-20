from unittest.mock import Mock
import pytest
from tech_shorts import editorial
from tech_shorts.config import Settings

NOTES = "OpenAI and Hacktron reported two linked vulnerabilities. The issue was fixed in fourteen hours."
BRIEF = {"facts": [{"text": "Two linked flaws", "evidence": "two linked vulnerabilities"},
                    {"text": "Fixed in fourteen hours", "evidence": "fixed in fourteen hours"}],
         "names": [{"canonical": "OpenAI", "aliases": ["오픈에이아이"]},
                   {"canonical": "Hacktron", "aliases": ["해크트론"]}]}
DRAFT = {"title": "보안 사례", "body": "오픈에이아이와 해크트론의 두 취약점 사례입니다. 열네 시간 만에 수정 완료했습니다. " + "원인과 영향 범위를 설명합니다. " * 25,
         "mid_question": "그렇다면 결과는 어땠을까요?", "summary": "두 문제가 연결됐고 열네 시간 만에 수정됐습니다.",
         "engagement": "연결된 계정의 권한을 확인해 보셨나요?"}
REVIEW = {"coverage": [{"id":"F1","quote":"두 취약점"},{"id":"F2","quote":"열네 시간 만에 수정"}],
          "missing": [], "unsupported": [], "names_ok": True, "ending_ok": True,
          "jargon_ok": True, "unexplained_terms": [], "story_ok": True, "readability_ok": True}


def test_auto_review_preserves_names_all_facts_and_ending(monkeypatch):
    api=Mock(side_effect=[BRIEF,DRAFT,REVIEW])
    monkeypatch.setattr(editorial,"ask",api)
    result=editorial.generate("주제",NOTES,Settings())
    assert "OpenAI" in result["script"] and "Hacktron" in result["script"]
    assert "오픈에이아이" not in result["script"]
    assert result["script"].endswith(DRAFT["engagement"])
    assert DRAFT["summary"] not in result["script"]
    assert len(result["brief"]["facts"])==2
    assert api.call_count==3


def test_missing_fact_triggers_automatic_rewrite(monkeypatch):
    rejected={**REVIEW,"coverage": REVIEW["coverage"][:1],"missing":["F2"]}
    api=Mock(side_effect=[BRIEF,DRAFT,rejected,DRAFT,REVIEW])
    monkeypatch.setattr(editorial,"ask",api)
    editorial.generate("主題",NOTES,Settings())
    assert api.call_count==5
    assert "F2" in api.call_args_list[3].args[2]["feedback"]


def test_invented_review_quote_never_passes(monkeypatch):
    review={**REVIEW,"coverage":[{"id":"F1","quote":"NOT IN SCRIPT"},{"id":"F2","quote":"ALSO INVENTED"}]}
    monkeypatch.setattr(editorial,"ask",Mock(side_effect=[BRIEF,*([DRAFT,review]*3)]))
    with pytest.raises(ValueError,match="자동 검토"):
        editorial.generate("주제",NOTES,Settings())


def test_unverified_evidence_is_rejected(monkeypatch):
    monkeypatch.setattr(editorial,"ask",Mock(return_value={"facts":[{"text":"fake","evidence":"invented evidence"}]}))
    with pytest.raises(ValueError,match="원문"):
        editorial.brief("주제",NOTES,Settings())


def test_editorial_revision_reuses_brief(monkeypatch):
    dossier={**BRIEF,"facts":[{**f,"id":f"F{i+1}"} for i,f in enumerate(BRIEF["facts"])]}
    api=Mock(side_effect=[DRAFT,REVIEW]);monkeypatch.setattr(editorial,"ask",api)
    editorial.generate("주제",NOTES,Settings(),dossier=dossier,previous="이전 대본")
    assert api.call_count==2
    assert api.call_args_list[0].args[2]["previous"]=="이전 대본"


def test_source_paragraph_ids_restore_original_evidence(monkeypatch):
    monkeypatch.setattr(editorial,"ask",Mock(return_value={"facts":[{"text":"Facts from separate paragraphs","source_ids":[0,2]}],"names":[]}))
    result=editorial.brief("topic","First original paragraph.\nMiddle paragraph.\nLast original paragraph.",Settings())
    assert result["facts"][0]["evidence"]=="First original paragraph.\nLast original paragraph."


def test_fact_sections_cannot_omit_a_required_fact():
    dossier={"facts":[{"id":"F1"},{"id":"F2"}],"names":[]}
    data={**DRAFT,"fact_sections":[{"id":"F1","narration":"첫 번째 사실"}]}
    with pytest.raises(ValueError,match="모든 핵심 사실"):
        editorial.compose(data,dossier)


def test_audience_questions_are_required_but_not_overused():
    dossier={"facts":[],"names":[]}
    with pytest.raises(ValueError,match="질문"):
        editorial.compose({**DRAFT,"mid_question":""},dossier)
    with pytest.raises(ValueError,match="최대 3개"):
        editorial.compose({**DRAFT,"body":DRAFT["body"]+" 왜일까요? 어떨까요? 될까요?"},dossier)


def test_short_ending_can_finish_with_advice_without_summary():
    draft = {k: v for k, v in DRAFT.items() if k != "summary"}
    draft["engagement"] = "여러분의 계정은 안전한가요? 접근 권한을 확인해 봐도 좋겠습니다."
    script, summary, ending = editorial.compose(draft, {"facts": [], "names": []})
    assert summary == "" and script.endswith(draft["engagement"])


def test_unexplained_specialist_terms_trigger_rewrite(monkeypatch):
    rejected = {**REVIEW, "jargon_ok": False, "unexplained_terms": ["ImageMagick"]}
    api = Mock(side_effect=[BRIEF, DRAFT, rejected, DRAFT, REVIEW])
    monkeypatch.setattr(editorial, "ask", api)
    editorial.generate("주제", NOTES, Settings())
    assert "ImageMagick" in api.call_args_list[3].args[2]["feedback"]


def test_natural_glossary_paraphrase_is_allowed_in_composition():
    dossier = {"facts": [], "names": [], "technical_terms": [
        {"term": "SSO", "aliases": [], "explanation": "여러 서비스에 한 번에 로그인하는 방식"}]}
    text = "SSO는 한 번 로그인해서 여러 서비스를 쓰는 방식입니다. "
    script, _, _ = editorial.compose({**DRAFT, "body": text + DRAFT["body"]}, dossier)
    assert text in script


def test_question_is_placed_before_answer_not_section_midpoint():
    dossier = {"facts": [{"id": f"F{i}"} for i in range(1, 5)], "names": []}
    sections = [{"id": f"F{i}", "narration": f"사실{i}. " + "원인과 영향을 설명합니다. " * 8} for i in range(1, 5)]
    script, _, _ = editorial.compose({**DRAFT, "body": "사건이 발생했습니다.",
        "fact_sections": sections, "mid_before_id": "F4"}, dossier)
    assert DRAFT["mid_question"] + " 사실4." in script
    with pytest.raises(ValueError, match="mid_before_id"):
        editorial.compose({**DRAFT, "fact_sections": sections, "mid_before_id": "F9"}, dossier)


@pytest.mark.parametrize("flag", ["story_ok", "readability_ok"])
def test_story_and_jargon_density_failures_trigger_rewrite(monkeypatch, flag):
    api = Mock(side_effect=[BRIEF, DRAFT, {**REVIEW, flag: False}, DRAFT, REVIEW])
    monkeypatch.setattr(editorial, "ask", api)
    editorial.generate("주제", NOTES, Settings())
    assert flag in api.call_args_list[3].args[2]["feedback"]


def test_selected_category_reaches_the_writer(monkeypatch):
    api = Mock(side_effect=[BRIEF, DRAFT, REVIEW])
    monkeypatch.setattr(editorial, "ask", api)
    editorial.generate("주제", NOTES, Settings(), category="history")
    assert api.call_args_list[1].args[2]["category"] == "역사"
