# VoiceFlow External Voice Platform Contract

**Version:** 1.0  
**Classification:** Internal Integration Interface  
**Protocol:** REST / HTTP JSON & Binary Audio Streaming

---

## 1. Overview
VoiceFlow is the self-hosted speech processing platform utilized by LexAgent for text-to-speech (TTS) synthesis of case briefs and speech-to-text (STT) transcription of spoken inquiries from advocates.

All communication between LexAgent and VoiceFlow occurs over local or private network routes (`VOICEFLOW_BASE_URL`) authenticated via a shared secret (`VOICEFLOW_API_KEY`).

---

## 2. Security & Network Boundary
1. **Network Boundary**: VoiceFlow is accessible only over loopback (`localhost`, `127.0.0.1`) or private RFC 1918 subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`). Cloud metadata service IPs (e.g. `169.254.169.254`) and external public routings are strictly blocked to prevent Server-Side Request Forgery (SSRF).
2. **Authentication**: All requests must contain the header:
   ```http
   Authorization: Bearer <VOICEFLOW_API_KEY>
   ```
3. **Data Privacy**: No audio is persisted on disk when `VOICE_STORE_AUDIO=false`. Audio buffers are held in memory during the request cycle and discarded immediately.

---

## 3. API Endpoints

### 3.1 Speech Synthesis (TTS)
Synthesizes spoken legal scripts into PCM WAV or MP3 audio streams.

- **Method**: `POST`
- **Path**: `/v1/tts/synthesize`
- **Request Headers**:
  - `Content-Type: application/json`
  - `Authorization: Bearer <VOICEFLOW_API_KEY>`
- **Request Body**:
  ```json
  {
    "text": "The accused was granted regular bail under Section four twenty of the Indian Penal Code.",
    "voice_id": "hi-IN-Standard-A",
    "language": "hi",
    "audio_format": "wav",
    "speaking_rate": 1.0
  }
  ```
- **Response**:
  - **Status**: `200 OK`
  - **Content-Type**: `audio/wav` or `audio/mpeg`
  - **Body**: Raw audio binary stream.
- **Latency Budget**: $< 2000\text{ ms}$ for scripts up to 500 words.

### 3.2 Speech Transcription (STT)
Transcribes spoken user audio into plain text for query grounding.

- **Method**: `POST`
- **Path**: `/v1/stt/transcribe`
- **Request Headers**:
  - `Content-Type: multipart/form-data` or `application/json`
  - `Authorization: Bearer <VOICEFLOW_API_KEY>`
- **Request Body (Multipart)**:
  - `file`: binary audio data (`audio/wav`, `audio/mpeg`, `audio/webm`)
  - `language`: optional ISO code (e.g., `hi`, `en`, `mr`)
- **Response**:
  - **Status**: `200 OK`
  - **Content-Type**: `application/json`
  - **Body**:
    ```json
    {
      "text": "Was the chargesheet filed within sixty days?",
      "detected_language": "en",
      "confidence": 0.94
    }
    ```
- **Latency Budget**: $< 1500\text{ ms}$ for utterances up to 30 seconds.

### 3.3 Healthcheck
- **Method**: `GET`
- **Path**: `/v1/health`
- **Response**:
  - **Status**: `200 OK`
  - **Body**: `{"status": "ok", "service": "VoiceFlow", "version": "2.0"}`

---

## 4. Error Handling & Fallbacks
| HTTP Status | Condition | LexAgent Behavior |
|---|---|---|
| `400 Bad Request` | Unsupported audio format or empty text | Abort with 400 error to user |
| `401 Unauthorized` | Invalid `VOICEFLOW_API_KEY` | Log security alarm, raise 502 Bad Gateway |
| `429 Too Many Requests` | VoiceFlow worker saturation | Retry with exponential backoff (2 attempts) |
| `500 Internal Error` / Timeout | VoiceFlow failure | Fallback to textual transcript or return degraded response |
