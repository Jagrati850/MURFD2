# Building an Autonomous Multilingual Health Access Voice Agent in 10 Days with Murf Falcon

*A complete technical retrospective on building a full-stack, voice-first health assistant for India — featuring persistent memory, live domain tools, emergency human escalations, call analytics, and specialist agent handoffs.*

---

## 🚀 Introduction & The Mission

Healthcare access in rural and semi-urban India faces significant structural hurdles: geographic distance, medical personnel shortages, and language barriers across diverse regional dialects. For millions of citizens, written digital interfaces present high literacy friction, making **natural voice interactions** the most inclusive medium for receiving timely health guidance.

Over the last 10 days, as part of the **#VoiceForBharat Challenge 2026**, I built the **Health Access Voice Agent** — an autonomous, privacy-conscious voice AI capable of evaluating symptoms, locating nearby Primary Health Centres (PHCs), assessing weather and air-quality advisories, scheduling outbound reminders, escalating emergencies to human ASHA workers/doctors, and seamlessly handing off appointment bookings to a specialist agent.

Crucially, the entire voice pipeline is powered by **Murf Falcon** — the fastest Text-to-Speech (TTS) API in the industry — ensuring ultra-low latency, fluid turn-taking, and natural human-like voice synthesis.

---

## 🏗️ System Architecture & Tech Stack

The solution connects real-time audio streaming, LLM reasoning, live domain tools, and persistent SQLite storage.

```
                  ┌──────────────────────────────────────────────┐
                  │    User Browser / WebGL Dark Orb UI         │
                  └──────────────────────┬───────────────────────┘
                                         │  WebRTC / WebSockets
                                         ▼
                  ┌──────────────────────────────────────────────┐
                  │        LiveKit Real-Time Transport           │
                  └──────┬───────────────────────────────┬───────┘
                         │ Audio Stream                  │ Audio Output
                         ▼                               │
          ┌─────────────────────────────┐  ┌─────────────┴───────────────┐
          │ Deepgram Nova-3 STT         │  │ Murf Falcon TTS             │
          │ (Multilingual Speech-to-Text)│  │ (Anisha / Pooja Voices)     │
          └──────────────┬──────────────┘  └─────────────▲───────────────┘
                         │ Transcribed Text              │ Synthesized Audio
                         ▼                               │
          ┌──────────────────────────────────────────────┴───────────────┐
          │ Google Gemini 3.5 Flash Lite LLM (Agentic Reasoning)         │
          └──────┬───────────────────────────────┬───────────────────────┘
                 │ Data Lookups                  │ Memory & Logs
                 ▼                               ▼
  ┌─────────────────────────────┐  ┌─────────────────────────────────────┐
  │ Live External APIs          │  │ SQLite Database (WAL Mode)          │
  │ - OpenStreetMap (Facilities)│  │ - user_memory (Preferences)        │
  │ - Open-Meteo (AQI/Weather)  │  │ - human_escalations (ASHA Alerts)   │
  │ - India Post (PIN Codes)    │  │ - call_analytics (Metrics & Logs)  │
  └─────────────────────────────┘  │ - clinic_appointments (Handoffs)  │
                                   └─────────────────────────────────────┘
```

### Core Technologies
- **Speech-to-Text (STT)**: Deepgram Nova-3 (`language="multi"`) for automatic Indian language detection.
- **Large Language Model (LLM)**: Google Gemini 3.5 Flash Lite for fast tool calling and reasoning.
- **Text-to-Speech (TTS)**: **Murf Falcon API** (*Anisha* voice for Main Agent, *Pooja* voice for Specialist Agent) with sentence tokenization and text pacing.
- **Real-Time Transport**: LiveKit Agents Framework for WebRTC audio transport.
- **Persistent Storage**: SQLite with WAL (Write-Ahead Logging) mode for concurrent memory and analytics reads/writes.
- **Frontend UI**: Next.js 15, TailwindCSS, and a WebGL 3D Shader Dark Orb Visualizer (inspired by `dark-orb.aura.build`).

---

## 🎨 Frontend Architecture & 3D Dark Orb UI

The application features a sleek dark aesthetic designed to provide immediate visual feedback across **5 Agent States**: `Ready`, `Connecting`, `Listening`, `Speaking`, and `Ended`.

### Key Features
1. **Symptom Triage**: Deterministic offline categorization of symptom urgency.
2. **Native Script Mirror**: Automatic transcription and vocal response in native scripts (Hindi Devanagari, Tamil, Marathi).
3. **Persistent Memory**: Consent-based user preference tracking across calls.
4. **Emergency Escalation**: Immediate warning & 112 redirection for red-flag symptoms.
5. **ASHA Helper Support**: Automated context generation for community health workers.
6. **Consent Protection**: Strict protocol ensuring no user data is stored without explicit consent.

---

## 🛠️ Detailed 10-Day Building Retrospective

### Day 4: Persistent Memory with Explicit Consent
To make conversations personal without compromising privacy, I implemented SQLite persistent storage (`user_memory` table) backed by a **Consent-First Protocol**. The agent must explicitly ask permission (*"May I remember your name and district for next time?"*) before invoking `save_user_memory`.

```python
@function_tool()
async def tool_save_user_memory(
    self,
    context: RunContext,
    user_id: str,
    preferred_name: str = "",
    preferred_language: str = "",
    previous_symptoms: str = "",
    home_district: str = "",
) -> dict:
    """Save user information ONLY AFTER the user gives explicit consent."""
    symptoms_list = [s.strip() for s in previous_symptoms.split(",") if s.strip()] if previous_symptoms else None
    return save_user_memory(
        user_id=user_id,
        preferred_name=preferred_name or None,
        preferred_language=preferred_language or None,
        previous_symptoms=symptoms_list,
        home_district=home_district or None,
    )
```

---

### Day 5: Domain Tools & Graceful Fallback Architecture
Instead of hallucinating healthcare facts, the agent uses three dedicated data tools:
1. **`find_nearby_health_centre`**: Live OpenStreetMap Overpass & Nominatim lookup for hospitals, clinics, and PHCs.
2. **`check_local_health_advisory`**: Live Open-Meteo weather, heat index, and air quality (AQI) readings.
3. **`assess_symptom_urgency`**: Local deterministic triage sorting symptoms into `red` (emergency), `amber` (see doctor), or `green` (self-care).

#### Handling Offline Network Failures Gracefully
In rural areas, API connections drop. If a live API lookup times out (8s limit), the system gracefully degrades:
1. Speaks an honest fallback message out loud (*"The live map service could not be reached..."*).
2. Uses a bundled offline district list (`health_facilities.json`).
3. Provides official Indian helplines (112, 108, 104) so the caller is never left in silence.

---

### Day 6: Outbound Calls & Reminders
Added `tool_trigger_outbound_reminder` allowing the agent to schedule follow-up check-in calls for medication compliance, vaccination schedules, or post-triage updates.

---

### Day 7: Human Escalation Protocol (ASHA Workers / Doctors)
AI agents should not attempt to solve critical medical crises alone. When a caller reports red-flag symptoms (chest pain, severe shortness of breath, stroke signs) or requests a doctor review:
1. The agent delivers an immediate emergency warning and 112 helpline details.
2. Asks for caller consent to share context with a doctor or ASHA worker.
3. Invokes `tool_create_human_escalation` to record a concise summary in the `human_escalations` table (excluding PINs/passwords).

---

### Day 8: Call Analytics Dashboard
To monitor performance and triage distribution, I built a live Call Analytics Dashboard backed by a Next.js API route (`/api/analytics`) that queries SQLite directly.

#### Live SQLite Call Logs
Every call outcome (`success`, `failed`, `escalated`) and duration is automatically recorded upon room disconnection.

---

### Day 9: Specialist Agent Handoff (`ClinicAppointmentAgent`)
One agent shouldn't try to handle everything. I created a dedicated **Clinic & Appointment Specialist** (`ClinicAppointmentAgent`) with a distinct Murf Falcon voice (**Pooja**) to take over when users want to book doctor consultation slots.

```python
# Handoff Tool in Main Agent (Voice: Anisha)
@function_tool()
async def transfer_to_clinic_specialist(self, context: RunContext) -> tuple[Agent, str]:
    """Transfer user to the Clinic & Appointment Specialist (Voice: Pooja) for doctor slot bookings."""
    specialist = ClinicAppointmentAgent(
        chat_ctx=self.chat_ctx.copy(exclude_instructions=True)
    )
    return specialist, "Transferring you to our Clinic and Appointment Specialist now."
```

#### Why This Handoff Pattern Works Seamlessly:
- **Context Inheritance**: `chat_ctx.copy(exclude_instructions=True)` passes the user's name, symptoms, and district spoken earlier directly to the specialist agent.
- **Audible Voice Switch**: Main Agent speaks in **Anisha** (Murf Falcon); Specialist Agent speaks in **Pooja** (Murf Falcon).
- **Visual Handoff Badge**: LiveKit data channel publishes a `handoff` payload rendering a purple **`DAY 9 HANDOFF`** card on screen!

---

## ⚡ Challenges Faced & Lessons Learned

1. **Eliminating Startup Latency**:
   - *Problem*: Heavy turn-detector imports were triggering PyTorch initialization delays (~50 seconds) before registering the agent worker with LiveKit Cloud.
   - *Fix*: Optimized plugin imports in `agent.py`, reducing worker registration speed to **under 1 second**.

2. **Native Script Compliance**:
   - *Problem*: Standard LLMs often reply in Romanized Hindi ("namaste main aapki madad kar sakta hoon"), which Murf Falcon pronounces with an English accent.
   - *Fix*: System prompt rules explicitly enforce writing in native scripts (Devanagari Hindi: नमस्ते). Murf Falcon synthesizes native script text with flawless Indian pronunciation.

3. **Consent & Safety Guardrails**:
   - Hardcoded strict guardrails forbidding disease diagnosis or prescription advice, ensuring the agent remains a safe triage assistant.

---

## 💻 How to Run & Deploy (Step-by-Step Guide)

### 1. Clone the Repository
```bash
git clone https://github.com/Jagrati850/MURFD2.git
cd MURFD2
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env.local` in both `backend` and `frontend` directories:

**Backend (`backend/.env.local`)**:
```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
MURF_API_KEY=your_murf_api_key
DEEPGRAM_API_KEY=your_deepgram_api_key
GOOGLE_API_KEY=your_gemini_api_key
```

### 3. Run Backend & Frontend

**Option A: PowerShell Launcher**
```powershell
.\start_app.ps1
```

**Option B: Manual Terminals**
```bash
# Terminal 1: Backend Agent
cd backend
uv run python src/agent.py dev

# Terminal 2: Frontend Next.js
cd frontend
pnpm install
pnpm dev
```

Open `http://localhost:3000` to interact with your agent live!

---

## 🏆 Final Thoughts & Repository Link

Building a multilingual voice agent for health access demonstrated the immense power of **low-latency TTS APIs like Murf Falcon** paired with modern real-time WebRTC frameworks. Voice AI is transforming accessibility in India, allowing citizens to interact with life-saving healthcare resources in their own mother tongue.

- **GitHub Repository**: [https://github.com/Jagrati850/MURFD2.git](https://github.com/Jagrati850/MURFD2.git)
- **Built for**: Voice for Bharat Challenge 2026 by Murf AI
