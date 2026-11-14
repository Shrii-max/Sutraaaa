"""Unit and integration test suite for Phase 3 Case-Level Reasoning Agents.

Follows Requirements:
1. TimelineAgent:
   - Timeline with mixed date formats (dd/mm/yyyy, Hindi month names, "dated 5th of March").
   - Conflicting dates flagged (same event with different dates in different docs).
   - Rules + LLM importance scoring (HIGH for incident, FIR, arrest, chargesheet, 161/164 statements, bail/orders).
   - UI timeline API JSON shape.
2. StatementIndexBuilder:
   - View of all victim/witness statements per case: who, role, when recorded, by whom, which section, summary.
3. ContradictionAgent:
   - Candidate pair generation by embeddings (same entity/event topic).
   - Contradiction detected on 2 synthetic statements.
   - Hallucinated snippet rejected by anti-hallucination verification.
   - ContradictionReport sorted by severity.
"""

import pytest
from app.schemas.source import SourceRef
from app.schemas.facts import StatementItem
from app.schemas.timeline import TimelineEvent
from app.agents.timeline import TimelineAgent, TimelineInput
from app.agents.statement_index import StatementIndexBuilder, StatementIndexInput
from app.agents.contradiction import ContradictionAgent, ContradictionInput
from app.llm.client import FakeLLMClient, FakeEmbedder


def test_timeline_agent_with_mixed_date_formats():
    """Verify TimelineAgent normalizes diverse date formats (Hindi months, English ordinals, numeric)."""
    facts = [
        {
            "event_id": "EV-001",
            "date_str": "dated 5th of March, 2023",
            "title": "Loan Agreement Signed",
            "description": "Complainant and accused executed commercial agreement.",
            "category": "contract",
            "source": SourceRef(document_id="doc-agr", page=1, char_start=0, char_end=30, snippet="Loan Agreement dated 5th of March, 2023"),
        },
        {
            "event_id": "EV-002",
            "date_str": "15 मार्च 2023",
            "title": "Dishonour of Cheque",
            "description": "Cheque dishonoured by bank with remark funds insufficient.",
            "category": "incident",
            "source": SourceRef(document_id="doc-chk", page=1, char_start=10, char_end=40, snippet="दिनांक 15 मार्च 2023 को चेक अनादरित"),
        },
        {
            "event_id": "EV-003",
            "date_str": "10/01/2022",
            "title": "First Meeting",
            "description": "Parties met at Delhi office.",
            "category": "meeting",
            "source": SourceRef(document_id="doc-meet", page=1, char_start=5, char_end=35, snippet="Meeting held on 10/01/2022"),
        },
        {
            "event_id": "EV-004",
            "date_str": "12 फ़रवरी 2023",
            "title": "Legal Demand Notice",
            "description": "Statutory notice sent under Section 138 NI Act.",
            "category": "notice",
            "source": SourceRef(document_id="doc-not", page=1, char_start=0, char_end=25, snippet="Notice dated 12 फ़रवरी 2023"),
        },
        {
            "event_id": "EV-005",
            "date_str": "20-01-2024",
            "title": "Filing of Plaint",
            "description": "Civil suit instituted before Senior Civil Judge.",
            "category": "filing",
            "source": SourceRef(document_id="doc-plaint", page=1, char_start=0, char_end=20, snippet="Plaint filed 20-01-2024"),
        },
    ]

    agent = TimelineAgent(llm_client=FakeLLMClient())
    timeline = agent.run(TimelineInput(case_id="case-mix-dates", facts=facts))

    # All 5 dates must be normalized to YYYY-MM-DD
    assert len(timeline.events) == 5
    normalized_dates = [e.normalized_date for e in timeline.events]
    expected_chronology = [
        "2022-01-10",  # 10/01/2022
        "2023-02-12",  # 12 फ़रवरी 2023
        "2023-03-05",  # dated 5th of March, 2023
        "2023-03-15",  # 15 मार्च 2023
        "2024-01-20",  # 20-01-2024
    ]
    assert normalized_dates == expected_chronology

    # Verify UI timeline JSON shape
    assert len(timeline.ui_timeline) == 5
    ui_item = timeline.ui_timeline[2]
    assert ui_item.date == "2023-03-05"
    assert ui_item.display_date == "05 Mar 2023"
    assert ui_item.doc_refs == ["doc-agr"]
    assert len(ui_item.source_snippets) >= 1
    assert "Loan Agreement" in ui_item.source_snippets[0]


def test_timeline_agent_conflicting_dates_flagged():
    """Verify TimelineAgent flags date conflicts when the same event topic has different dates across docs."""
    facts = [
        {
            "event_id": "EV-FIR",
            "date_str": "10-03-2023",
            "title": "Incident Occurrence",
            "description": "Robbery incident occurred at complainant office.",
            "category": "incident",
            "document_id": "doc-fir-01",
            "source": SourceRef(document_id="doc-fir-01", page=1, char_start=0, char_end=30, snippet="Occurrence on 10-03-2023"),
        },
        {
            "event_id": "EV-WITNESS",
            "date_str": "12-03-2023",
            "title": "Incident Occurrence",
            "description": "Eyewitness alleges robbery incident occurred at night.",
            "category": "incident",
            "document_id": "doc-statement-01",
            "source": SourceRef(document_id="doc-statement-01", page=1, char_start=0, char_end=30, snippet="Incident on 12-03-2023"),
        },
    ]

    agent = TimelineAgent(llm_client=FakeLLMClient())
    timeline = agent.run(TimelineInput(case_id="case-conflict-test", facts=facts))

    # Must flag date conflict
    assert timeline.has_conflicts is True
    assert len(timeline.date_conflicts) == 1

    conflict = timeline.date_conflicts[0]
    assert conflict.event_topic == "OCCURRENCE"
    assert conflict.date_a == "2023-03-10"
    assert conflict.date_b == "2023-03-12"
    assert conflict.doc_id_a == "doc-fir-01"
    assert conflict.doc_id_b == "doc-statement-01"

    # UI items should carry conflict markers
    assert any(ui.is_conflict for ui in timeline.ui_timeline)
    assert any(ui.conflict_notes is not None for ui in timeline.ui_timeline)


def test_timeline_agent_importance_scoring():
    """Verify importance scoring rules classify core criminal events as HIGH and routine dates as LOW."""
    facts = [
        {
            "event_id": "E-HIGH-1",
            "date_str": "2023-01-01",
            "title": "Arrest of Accused",
            "description": "Accused was arrested and taken into police remand.",
            "category": "arrest",
            "source": SourceRef(document_id="d1", page=1, char_start=0, char_end=10, snippet="Arrest on 2023-01-01"),
        },
        {
            "event_id": "E-HIGH-2",
            "date_str": "2023-01-05",
            "title": "Statement under Section 161 CrPC",
            "description": "Statement of eye witness recorded under section 161 CrPC.",
            "category": "statement",
            "source": SourceRef(document_id="d2", page=1, char_start=0, char_end=10, snippet="161 statement on 2023-01-05"),
        },
        {
            "event_id": "E-LOW",
            "date_str": "2023-02-01",
            "title": "Court Adjournment",
            "description": "Matter adjourned on request of counsel, next date of peshi fixed.",
            "category": "procedural",
            "source": SourceRef(document_id="d3", page=1, char_start=0, char_end=10, snippet="Adjourned on 2023-02-01"),
        },
    ]

    agent = TimelineAgent(llm_client=FakeLLMClient())
    timeline = agent.run(TimelineInput(case_id="case-imp-test", facts=facts))

    imp_map = {e.event_id: e.importance for e in timeline.events}
    assert imp_map["E-HIGH-1"] == "HIGH"
    assert imp_map["E-HIGH-2"] == "HIGH"
    assert imp_map["E-LOW"] == "LOW"


def test_statement_index_builder():
    """Verify StatementIndexBuilder compiles victim and witness statements with section and short content summary."""
    statements = [
        StatementItem(
            statement_type="164",
            speaker="Pooja Sharma",
            role="victim",
            recorded_on="15-05-2023",
            recorded_by="Metropolitan Magistrate, Saket Courts",
            content="I was deceived by the accused who promised to deliver gold ornaments after taking advance money.",
            source=SourceRef(document_id="doc-164", page=1, char_start=0, char_end=50, snippet="I was deceived by the accused"),
            confidence=0.95,
        ),
        StatementItem(
            statement_type="161",
            speaker="Mohan Lal",
            role="eye_witness",
            recorded_on="16-05-2023",
            recorded_by="Sub-Inspector Devender",
            content="I saw the victim hand over a packet of cash to the accused outside the metro station.",
            source=SourceRef(document_id="doc-161", page=1, char_start=0, char_end=50, snippet="I saw the victim hand over a packet"),
            confidence=0.92,
        ),
    ]

    fake_llm = FakeLLMClient({
        "_LLMStatementSummaryPayload": {
            "summary": "Victim alleges advance payment taken under false promise of gold delivery.",
            "normalized_role": "victim",
            "statutory_section": "Section 164 CrPC",
        }
    })

    builder = StatementIndexBuilder(llm_client=fake_llm)
    index = builder.run(StatementIndexInput(case_id="case-statements-01", statements=statements))

    assert index.total_statements == 2
    assert index.victim_count == 1
    assert index.witness_count == 1

    item1 = index.statements[0]
    assert item1.speaker == "Pooja Sharma"
    assert item1.role == "victim"
    assert item1.recorded_on == "2023-05-15"
    assert "Section 164 CrPC" in item1.section
    assert len(item1.summary) > 10
    assert item1.source_ref.document_id == "doc-164"

    item2 = index.statements[1]
    assert item2.speaker == "Mohan Lal"
    assert item2.role == "eye_witness"
    assert item2.recorded_on == "2023-05-16"
    assert "Section 161 CrPC" in item2.section


def test_contradiction_agent_detected_on_synthetic_statements():
    """Verify ContradictionAgent identifies genuine factual contradictions between 2 statements with SourceRefs."""
    stmt_a = (
        "Mera naam Rajesh Verma hai. Maine dekha ki accused Sunil Gupta ke haath mein ek bada silver kitchen knife tha "
        "aur usne complainant par sadak ke kinare hamla kiya."
    )
    stmt_b = (
        "Mera naam Sunita Devi hai. Maine dekha ki accused Sunil Gupta ke haath mein ek black revolver pistol thi "
        "aur usne complainant par car ke andar se goli chalayi."
    )

    statements = [
        {
            "statement_id": "ST-A",
            "speaker": "Rajesh Verma",
            "doc_type": "statement_161",
            "content": stmt_a,
            "document_id": "doc-stmt-a",
            "source": SourceRef(document_id="doc-stmt-a", page=1, char_start=0, char_end=len(stmt_a), snippet=stmt_a),
        },
        {
            "statement_id": "ST-B",
            "speaker": "Sunita Devi",
            "doc_type": "statement_161",
            "content": stmt_b,
            "document_id": "doc-stmt-b",
            "source": SourceRef(document_id="doc-stmt-b", page=1, char_start=0, char_end=len(stmt_b), snippet=stmt_b),
        },
    ]

    canned_llm_response = {
        "judgment": "contradictory",
        "severity": "HIGH",
        "category": "WEAPON_DISCREPANCY",
        "reason": "Direct conflict on murder weapon: Rajesh claims silver kitchen knife while Sunita claims black revolver pistol.",
        "quote_a": "accused Sunil Gupta ke haath mein ek bada silver kitchen knife tha",
        "quote_b": "accused Sunil Gupta ke haath mein ek black revolver pistol thi",
        "confidence": 0.94,
    }

    fake_llm = FakeLLMClient({
        "_LLMPairContradictionResult": canned_llm_response,
        "contradictory": canned_llm_response,
    })

    agent = ContradictionAgent(llm_client=fake_llm, embedder=FakeEmbedder())
    report = agent.run(ContradictionInput(case_id="case-contradiction-01", statements=statements))

    assert len(report.contradictions) == 1
    assert report.has_severe_contradictions is True

    c = report.contradictions[0]
    assert c.severity == "HIGH"
    assert c.category == "WEAPON_DISCREPANCY"
    assert "silver kitchen knife" in c.statement_a
    assert "black revolver pistol" in c.statement_b
    assert "weapon" in c.description.lower()

    # Verify SourceRefs point to exact snippet locations
    assert c.source_a.document_id == "doc-stmt-a"
    assert stmt_a[c.source_a.char_start:c.source_a.char_end] == c.source_a.snippet
    assert c.source_b.document_id == "doc-stmt-b"
    assert stmt_b[c.source_b.char_start:c.source_b.char_end] == c.source_b.snippet


def test_contradiction_agent_rejects_hallucinated_snippets():
    """Anti-hallucination check (Hard Rule 2): Drop reported contradictions where quoted snippets do not exist in source."""
    stmt_a = "Complainant arrived at Saket police station at 11:00 AM."
    stmt_b = "Accused was seen standing near the metro gate at 11:30 AM."

    statements = [
        {
            "statement_id": "ST-1",
            "speaker": "Complainant",
            "doc_type": "fir",
            "content": stmt_a,
            "document_id": "doc-1",
            "source": SourceRef(document_id="doc-1", page=1, char_start=0, char_end=len(stmt_a), snippet=stmt_a),
        },
        {
            "statement_id": "ST-2",
            "speaker": "Eyewitness",
            "doc_type": "statement_161",
            "content": stmt_b,
            "document_id": "doc-2",
            "source": SourceRef(document_id="doc-2", page=1, char_start=0, char_end=len(stmt_b), snippet=stmt_b),
        },
    ]

    # LLM hallucinates quotes that do NOT exist in either statement
    hallucinated_llm_response = {
        "judgment": "contradictory",
        "severity": "HIGH",
        "category": "HALLUCINATED_CLAIM",
        "reason": "Accused was supposedly riding a blue helicopter according to fake testimony.",
        "quote_a": "Accused escaped on a blue military helicopter",  # NOT in stmt_a!
        "quote_b": "Accused fled in a yellow submarine",           # NOT in stmt_b!
        "confidence": 0.90,
    }

    fake_llm = FakeLLMClient({
        "_LLMPairContradictionResult": hallucinated_llm_response,
        "contradictory": hallucinated_llm_response,
    })

    agent = ContradictionAgent(llm_client=fake_llm, embedder=FakeEmbedder())
    report = agent.run(ContradictionInput(case_id="case-hallucination-test", statements=statements))

    # Anti-hallucination check MUST drop the contradiction
    assert len(report.contradictions) == 0
    assert report.has_severe_contradictions is False
    assert "dropped 1 items failing anti-hallucination snippet checks" in report.audit_notes

