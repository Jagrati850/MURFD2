# Health Access Voice Agent — Voice for Bharat Challenge 2026 (Days 1 – 9)

A comprehensive, multilingual AI Voice Assistant built for the **Health Access Track** in India as part of the **Voice for Bharat Challenge 2026**.

Built with the fastest TTS API, **Murf Falcon** (voice: *Anisha* for Main Agent, *Pooja* for Specialist Agent), powered by **LiveKit Agents**, **Deepgram Nova-3** (multilingual STT), **Google Gemini 3.5 Flash Lite**, and a persistent **SQLite Database**.

---

## 🌟 Key Highlights Across Days 1 to 9

| Day | Feature | Description & Implementation | Primary Files |
| :--- | :--- | :--- | :--- |
| **Day 1** | **Starter Setup & Murf Integration** | Initialized LiveKit Cloud workspace with Murf Falcon TTS (Anisha voice), Deepgram STT, and Google Gemini LLM. | `backend/pyproject.toml`, `backend/src/agent.py` |
| **Day 2** | **Persona & Native Script Rules** | Configured empathetic health persona with strict health guardrails and native script enforcement (Hindi → Devanagari हिंदी, Tamil → Tamil, etc.). | `backend/src/agent.py` |
| **Day 3** | **3D Dark Orb UI & 5 Agent States** | Built interactive 3D Dark Orb UI (inspired by `dark-orb.aura.build`) supporting 5 distinct Agent States (*Ready*, *Connecting*, *Listening*, *Speaking*, *Ended*). | `frontend/components/app/dark-orb-visualizer.tsx`, `welcome-view.tsx` |
| **Day 4** | **Persistent Memory (SQLite)** | SQLite database (`user_memory`) storing caller preferences, past symptoms, age, ongoing conditions, and home district with explicit user consent protocol. | `backend/src/memory.py` |
| **Day 5** | **Live Domain Tools & Fallbacks** | OpenStreetMap health facility lookup (`find_nearby_health_centre`), Open-Meteo heat/AQI advisory (`check_local_health_advisory`), and symptom triage classifier (`assess_symptom_urgency`) with live timestamps and offline fallbacks. | `backend/src/health_tools.py`, `health-data-panel.tsx` |
| **Day 6** | **Outbound Calls & Reminders** | Outbound medication/vaccination reminder call scheduler tool (`tool_trigger_outbound_reminder`). | `backend/src/agent.py` |
| **Day 7** | **Human Escalation Protocol** | Doctor & ASHA Healthcare Worker escalation tool (`tool_create_human_escalation`) triggered for red-flag symptoms/doctor reviews with caller consent check and concise summary generation. | `backend/src/memory.py`, `backend/src/agent.py` |
| **Day 8** | **Call Analytics Dashboard** | SQLite `call_analytics` logging on session disconnect, Next.js `/api/analytics` API route, and an interactive UI Dashboard displaying Total Calls, Success/Failure metrics, Escalations, and Live SQLite Call History logs. | `frontend/app/api/analytics/route.ts`, `analytics-dashboard.tsx` |
| **Day 9** | **Specialist Agent Handoff** | Created a specialist agent (`ClinicAppointmentAgent` — voice: **Pooja**) and a handoff tool (`transfer_to_clinic_specialist`) allowing the Main Agent (voice: **Anisha**) to seamlessly transfer appointment booking context. | `backend/src/agent.py`, `memory.py` |

---

## 🔊 Murf Falcon TTS & Language Rules

- **Main Agent TTS**: `murf.TTS(voice="Anisha", style="Conversation", text_pacing=True)` — Warm, empathetic primary health assistant.
- **Specialist Agent TTS**: `murf.TTS(voice="Pooja", style="Conversation", text_pacing=True)` — Distinct, professional clinic appointment specialist.
- **STT Engine**: `deepgram.STT(model="nova-3", language="multi")` — automatically detects Indian languages.
- **Native Script Rule**: System prompt strictly enforces writing every language in its native script:
  - **Hindi** → Devanagari (e.g. नमस्ते, not "namaste")
  - **Tamil** → Tamil script
  - **Bengali** → Bengali script
  - **Marathi** → Devanagari script

---

## 🛠️ Detailed Breakdown by Challenge Days

### Day 4: Persistent Memory with Consent
- Stores user context across calls in `backend/data/health_memory.db`.
- **Consent Protocol**: The agent ALWAYS asks before saving: *"May I remember your name and district for next time?"*
- Tools: `lookup_user`, `save_user_memory`, `delete_user_memory`.

### Day 5: Live Domain Tools & Graceful Fallbacks
- **Live Health Facilities**: Queries OpenStreetMap Nominatim + Overpass API live for hospitals, clinics, and PHCs.
- **Live Weather & Air Quality**: Queries Open-Meteo API for real-time temperature, feels-like heat, and US AQI.
- **Offline Triage**: Local deterministic ruleset categorizes symptoms into `red` (emergency), `amber` (doctor review), or `green` (self-care).
- **Graceful Failure**: If live APIs time out, the agent speaks an honest fallback message out loud and uses a local hand-built fallback list (`health_facilities.json`).

### Day 6: Outbound Calls & Follow-up Reminders
- Enables scheduling outbound follow-up calls for medication reminders or post-triage check-ins.

### Day 7: Know When to Ask for Human Help (Human Escalations)
- When a caller reports red-flag symptoms (chest pain, severe shortness of breath, stroke signs) or asks for a doctor diagnosis:
  1. Delivers emergency warning and 112 helpline details.
  2. Asks for caller consent to share context with a doctor/ASHA worker.
  3. Creates an escalation record in `human_escalations` table with a concise summary (urgency, symptoms, language preference) excluding passwords/PINs.

### Day 8: Call Analytics Dashboard
- Automatically records every call outcome into SQLite `call_analytics` table upon disconnection.
- Next.js API `/api/analytics` queries SQLite backend directly.
- **Dashboard UI (`/analytics`)**:
  - **Total Calls** counter
  - **Successful Calls** metric with percentage badge
  - **Failed / Early Disconnects** metric
  - **Human Escalations (Day 7)** counter
  - **Specialist Bookings (Day 9)** counter
  - **Completion Ratio Bar** & **Live Call Logs Table**

### Day 9: Specialist Agent Handoff (`ClinicAppointmentAgent`)
- **Specialist Agent**: `ClinicAppointmentAgent` (Voice: **Pooja**).
- **Handoff Tool**: `transfer_to_clinic_specialist(self, context: RunContext)`.
- **Seamless Context Transfer**: Uses `chat_ctx=self.chat_ctx.copy(exclude_instructions=True)` so the specialist inherits all caller details (name, symptoms, district) spoken to the main agent!
- **Specialist Tools**:
  - `tool_book_clinic_appointment`: Books a doctor consultation slot at a clinic/PHC and saves to SQLite `clinic_appointments` table.
  - `tool_check_appointment_slots`: Checks available morning/afternoon doctor consultation slots.

---

## 🚀 How to Run the Project

### Prerequisites
- Python 3.10+ & `uv` package manager
- Node.js 18+ & `pnpm`

### 1. Configure Environment Variables
Copy `.env.example` to `.env.local` in both `backend` and `frontend` folders:

**Backend (`backend/.env.local`)**:
```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
MURF_API_KEY=your_murf_api_key
DEEPGRAM_API_KEY=your_deepgram_api_key
GOOGLE_API_KEY=your_gemini_api_key
```

**Frontend (`frontend/.env.local`)**:
```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
AGENT_NAME=health-agent
```

### 2. Start Backend & Frontend
Run the one-click launcher or start in separate terminals:

**Option A: One-Click Launcher (PowerShell)**
```powershell
.\start_app.ps1
```

**Option B: Separate Terminals**
```bash
# Terminal 1: Backend
cd backend
uv run python src/agent.py dev

# Terminal 2: Frontend
cd frontend
pnpm dev
```

Open **`http://localhost:3000`** in your browser!

---

## 🧪 Testing Guide

| Action / Prompt | Expected Agent Behavior |
| :--- | :--- |
| **"I want to book an appointment at the clinic"** | Main Agent (voice: **Anisha**) triggers `transfer_to_clinic_specialist` -> Handoff to Specialist Agent (voice: **Pooja**). |
| **Specialist Interaction ("Tomorrow at 10 AM")** | Specialist (voice: **Pooja**) calls `tool_book_clinic_appointment`, confirms booking, and saves record to SQLite. |
| **"मुझे तीन दिन से बुखार है"** | Triage → `amber`, facility lookup, answered in Devanagari Hindi. |
| **"I am having severe chest pain"** | Triage → `red`, emergency guidance + 112 call + Human Escalation created. |
| **"Nearest hospital near 221005?"** | Live OpenStreetMap lookup for PIN 221005, returning real facilities. |
| **Click "Analytics Dashboard" Tab** | Displays live Day 8/9 metrics, success rates, specialist bookings, and SQLite call logs. |

---

## 🛡️ Health Guardrails
- **Not a Doctor**: Clarifies general guidance only.
- **No Prescriptions**: Never prescribes or names specific medications.
- **Emergency Redirection**: Chest pain, stroke signs, unconsciousness, severe bleeding, or self-harm trigger immediate emergency responses and dial 112 instructions.
- **Consent-First**: Data saved only after explicit caller approval.

---

## 📝 License
Built for the **Voice for Bharat Challenge 2026** by Murf AI.
