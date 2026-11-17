# Moot Court in Sutra AI Assistant

Moot Court is a mode of the existing case-aware Sutra chatbot. The sidebar AI Assistant and floating chat icon share the same hearing session. **Start Moot Court** opens setup inside the conversation. The same thread presents the hearing, simulated order and coaching.

## Setup and reuse

- Select an analysed case, language (English, Hindi, Hinglish or a tested Indic language), District/High Court/Supreme Court, jurisdiction where applicable, strict/inquisitive/neutral persona, voice, Petitioner/Appellant or Respondent, and optional practice hints.
- Reuse authentication and case ownership via the assistant router and CaseManager. Snapshot saved timeline, statements, contradictions, summary and source spans. Distinguish allegations from verified facts. Show incomplete case analysis before starting.
- Reuse the hybrid retriever and Judgment/JudgmentChunk records. Use TranslationAgent, VoiceBriefAgent and VoiceQAAgent conventions for terminology, spoken phrasing and provenance. The existing Vapi and local voice gateways contain placeholder paths and need a dedicated streaming adapter. Keep existing chat and agent defaults.
- The inspected checkout defaults to SQLite. Target Postgres with pgvector for production hybrid retrieval and retain SQLite for local development.

## Graph and turn lifecycle

Setup → snapshot case → listen → finalize lawyer turn → capture arguments → retrieve and verify authorities → update leaning → choose bench action → deliver judge response → listen.

Close hearing → freeze transcript → frame issues and draft simulated order → verify authorities again → score and coach → save and display report.

| Node | Responsibility |
|---|---|
| ArgumentNoteTaker | Extract distinct claims, issues, side, basis, as-spoken citations, sources, strength and rebuttal status. Link each point to its original turn and transcript span. |
| PrecedentRetriever | Return supporting and adverse database authorities with verified IDs, pinpoints, bench, treatment and applicability. |
| LeaningTracker | Apply deterministic issue-level updates and record the prior, new value, evidence and explanation. |
| CounterQuestionAgent | Choose one material gap, inconsistent assertion, adverse authority or unanswered bench question. Use the selected side and avoid gratuitous repetition. |
| JudgeAgent | Ask, challenge, invite continuation or close. Use one to three spoken sentences without markdown. Respect courtroom etiquette, language and court level. Persona shapes tone and interruptions. |
| SpeechStyleAnalyzer | Use transcript and timing to assess pace, fillers, pauses, interruption handling, politeness and clarity. Mark unavailable data explicitly. |
| VerdictAgent | Frame issues and produce a simulated decided or reserved order with reasoning per issue, relief and verified precedents applied. Reserve when material gaps prevent a reasoned disposition. |
| ScoringAgent | Apply the rubric, cite the specific turns supporting each rating and report coverage and uncertainty. |
| CoachAgent | Explain the selected side's strongest unused points, better answers to actual questions and missed authorities, including adverse cases to distinguish. |

State includes session and case IDs, authorized owner, case snapshot version, court and jurisdiction, language, voice, persona, side, hints, lifecycle, ordered turns, points, source references, verified authority IDs, open questions, issue weights and leaning history, audio timing and report. Publish a separate client projection that omits internal leaning.

Only finalized turns affect legal state. Partial transcripts are captions. Corrections supersede prior revisions and replay their downstream state. End on explicit close, agreed limits or a configured bench close after final submissions. On disconnect, pause and replay committed events on reconnect. Finalization is idempotent.

## Leaning and assessment

Initialize each issue at 50 on a 0–100 axis in favour of Petitioner/Appellant. Derive the selected lawyer's view from that axis. Combine issues using setup weights that reflect their importance to the disposition.

For each distinct point, rate argument strength (35%), precedent support (25%), statute fit (20%), factual consistency (15%) and bench responsiveness (5%), each on a 0–1 scale. Initial update magnitude is 10 × weighted merit × evidence confidence, signed toward the supported side. Deduct up to 4 for a material source-confirmed contradiction and up to 2 once for an unanswered material question after an opportunity to respond. Recompute when answered. Clamp to 0–100. Repeated points get zero incremental credit. Store evidence and reason for every change.

Weight authorities by applicability and treatment. Initial factors are 1.00 for applicable Supreme Court ratio, 0.75 for applicable jurisdictional High Court ratio in a subordinate court and 0.35 for persuasive authority. Account for territory, bench strength and later treatment. Flag overruled, stayed, editorial-only and treatment-unknown records. Persona and delivery never affect legal weighting. Hints show qualitative direction and a relevant open issue. [Constitution of India, Article 141](https://www.legislative.gov.in/static/uploads/2025/08/b9a933fb88c0a5afba254256bc55a3f0.pdf)

| Rubric dimension | Weight |
|---|---:|
| Legal reasoning and issue framing | 25% |
| Precedent identification and application | 20% |
| Statute selection and application | 15% |
| Factual accuracy and source use | 15% |
| Rebuttal quality | 15% |
| Responsiveness to the bench | 10% |

Use anchored 0–4 ratings with supporting turns. Show assessed coverage and mark insufficient evidence unassessed. Speech-style feedback is separate and carries no legal merit penalty. A probability range requires lawyer-rated calibration against simulated outcomes and validation on held-out cases across sides and court levels. Before calibration, label any band as an uncalibrated practice assessment or show insufficient evidence. Widen uncertainty for incomplete authority coverage, disputed facts, poor transcripts and short hearings. Internal leaning is not a real-world outcome forecast.

> Practice simulation. The order and scores are learning aids. They do not constitute legal advice or predict a real court outcome.

## Court-data contract and citation gate

During the hearing retrieve only stored judgments and chunks. Combine pgvector with lexical search and filter by court, year or date cutoff, jurisdiction and Act plus section. Query supporting and adverse propositions separately. Label lexical-only retrieval when embeddings are unavailable.

The data team supplies stable judgment IDs, canonical and neutral citations, aliases, title, court, jurisdiction, date, judges, bench size, proceeding, official source URL and hash, retrieval time, original text, paragraph/page spans, ratio and supporting spans, disposition, statutory version/effective dates, verification status and reviewer, later treatment links, chunk IDs and embedding model/version/dimension.

Pass only an allowlist of judgment and passage IDs to the model. Render canonical case names and citations server-side. Verify existence, pinpoint, source span and treatment before speech or display. Treat lawyer-supplied citations as unverified until matched. If there is no supported authority, say that none was found in the local database for the proposition.

## Voice and chat UX

- Use one provider contract for audio input, partial/final transcription, speech start/stop, synthesis chunks, cancellation and reconnect. LexAgent owns judge policy and approved text. Validate that Vapi plays only approved LexAgent responses. Disable free-form provider replies.
- Vapi is preferred when the lawyer opts into cloud voice. It processes audio and may process transcript and spoken text. Case files, retrieval and graph state stay local. Validate provider callbacks and retention settings. Strict local mode uses local STT/TTS or typed turns. [Vapi data flow](https://docs.vapi.ai/security-and-privacy/data-flow)
- Candidate local adapters are warmed faster-whisper or validated Indic STT, and a tested open-source Indic TTS adapter. Use per-language capability checks and real voice IDs. Preserve Hinglish code-switching, bias STT toward case terms and ask for confirmation of uncertain names, amounts or section numbers. [faster-whisper](https://github.com/SYSTRAN/faster-whisper) · [IndicF5](https://github.com/AI4Bharat/IndicF5)
- Target under 1.5 seconds p95 from end of speech to first audible response on warmed systems. Allocate 350 ms endpointing/final STT, 200 ms retrieval and verification, 650 ms first verified sentence and 300 ms first audio. Show Thinking on slow turns. VAD and manual Interrupt cancel generation and playback, discard queued chunks by turn ID and log what was heard. Treat silence as a pause before prompting. [Vapi speech configuration](https://docs.vapi.ai/customization/speech-configuration)
- In the existing chat, show mic waveform, Listening/Thinking/Judge speaking, whose turn it is, caption/transcript, Interrupt, optional hints and End hearing. If voice fails, show a real error and continue by text. The result has the order, practice range when supportable, rubric, turn-linked timeline, missed precedents, speaking feedback and transcript/PDF export.

## Storage and transport

| Surface | Design |
|---|---|
| Tables | moot_sessions, moot_turns, moot_points, moot_authority_links, moot_checkpoints, moot_reports. Store owner/case/snapshot, revisions/timing, points/rebuttals, canonical authority IDs, leaning audit trail and immutable report revision. |
| REST | Create session, end session, get transcript and get report under /moot-court/sessions. Authenticate and enforce ownership on each action. |
| WebSocket | /moot-court/ws/{session_id} uses a short-lived bound ticket. Envelope includes session ID, sequence, turn ID, event type and timestamp. Clients send audio frames, typed turn, interrupt, hints and resume. Server emits partial_transcript, final_transcript, judge_text, judge_audio for local streaming, barge_in, state_update, verdict and error. Vapi audio uses its voice transport. |
| Persistence | Serialize finalized turns per session and commit turn, points, authorities and checkpoint before acknowledgement. Enforce sequence and size limits. Replay committed events from the last acknowledged sequence. Keep raw audio in memory unless the lawyer explicitly opts into recording. |
| Repo layout | Transport under app/api/routers, graph under app/orchestrator, hearing agents under app/agents/moot_court, contracts under app/schemas, voice adapters under app/voice, and UI alongside Sutra chat. |

## Risks and pilot gates

| Risk | Control |
|---|---|
| Hallucinated law | Verified ID allowlist and exact source-span checks before any citation can be spoken. |
| Latency or provider outage | Warm-up probe, compact context, bounded deadlines, cancellation and text continuation. |
| Accent or citation errors | Multilingual transcription, vocabulary bias, transcript correction before assessment. |
| Overconfident scores | Anchored rubric, coverage and uncertainty; reserve disposition when appropriate. |
| Repetitive or biased bench | Track asked questions and open issues. Use side-swapped consistency tests and keep persona out of legal scoring. |

1. **Morning — text graph.** Verify a multi-turn case hearing, tenant isolation, replay, duplicate submissions, leaning direction and unknown-citation rejection. Confirm the statement-index adapter uses the schema's statements field.
2. **Midday — voice loop.** Verify one consented Vapi language with actual audio, interruption, partial/final ordering, silence, reconnect, provider outage and measured latency.
3. **Afternoon — shared chat.** Verify sidebar and floating chat open and resume the same session, with language, side, playback cancellation and text continuation.
4. **End of day — result.** Verify decided and reserved reports, scoring with turn references, side-specific coaching, export and existing-agent regression behavior.

The one-day target is a verified pilot. Full Indic voice coverage, hardware latency and statistically calibrated ranges require measured evidence before broad release.
