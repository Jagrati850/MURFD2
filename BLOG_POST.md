# Building an Autonomous Multilingual Health Access Voice Agent in 10 Days with Murf Falcon

> **#VoiceForBharat Challenge 2026** | **Health Access Track**
> Built with **Murf Falcon** — the fastest TTS API in the industry.

---

## 📸 Showcase Gallery: System & Live Dashboard in Action

Here is a visual walk-through of the Health Access Voice Agent built over the 10-day challenge:

### 1. Hero Interface & 3D Dark Orb Visualizer (Day 3)
![Hero Landing Page & 3D Dark Orb Canvas](C:\Users\gupta\.gemini\antigravity-ide\brain\d669ca31-e88b-4e91-a46c-4c46a4132eea\media__1786808633884.png)

### 2. Five Pillars of Agentic Health Access
![Five Pillars of Health Access](C:\Users\gupta\.gemini\antigravity-ide\brain\d669ca31-e88b-4e91-a46c-4c46a4132eea\media__1786808670009.png)

### 3. Live Active Call Audio Visualizer
![Live Active Call Audio Visualizer](C:\Users\gupta\.gemini\antigravity-ide\brain\d669ca31-e88b-4e91-a46c-4c46a4132eea\media__1786808730050.png)

### 4. Day 8/9 Call Analytics & Specialist Handoff Dashboard
![Day 8/9 Call Analytics & Specialist Handoff Dashboard](C:\Users\gupta\.gemini\antigravity-ide\brain\d669ca31-e88b-4e91-a46c-4c46a4132eea\media__1786808535476.png)

### 5. Live SQLite Call Logs & Triage Records
![Live Call Logs in SQLite](C:\Users\gupta\.gemini\antigravity-ide\brain\d669ca31-e88b-4e91-a46c-4c46a4132eea\media__1786808579875.png)

---

## 🌟 The Vision: Why Voice First for Health Access?

Healthcare accessibility in rural and semi-urban India faces critical challenges — long travel distances, shortage of medical specialists, and literacy barriers with traditional text-based medical apps.

Voice is the most natural, inclusive interface for India. Over the last 10 days, I set out to build an **autonomous, privacy-conscious Health Access Voice Assistant** that can:
- Understand symptoms spoken in Indian languages (Hindi, Tamil, Bengali, Marathi, Hinglish).
- Evaluate symptom urgency using deterministic triage rules.
- Locate nearby Primary Health Centres (PHCs) and check weather/air quality advisories live.
- Remember returning users with explicit consent.
- Schedule outbound follow-up calls and medication reminders.
- Escalate red-flag emergencies to human ASHA workers/doctors.
- Hand off clinic appointment bookings to a specialist agent with an audible voice change!

The secret sauce behind this fluid experience is **Murf Falcon** — the fastest Text-to-Speech API — delivering instantaneous, human-like voice synthesis with zero audible lag.

---

## 🛠️ The Tech Stack

- **TTS (Text-to-Speech)**: **Murf Falcon API** (*Anisha* voice for Main Agent, *Pooja* voice for Specialist Agent).
- **STT (Speech-to-Text)**: Deepgram Nova-3 (`language="multi"`).
- **LLM Engine**: Google Gemini 3.5 Flash Lite.
- **Real-Time Transport**: LiveKit Agents Framework (WebRTC / WebSockets).
- **Database**: SQLite (WAL Mode) for persistent memory, human escalations, call analytics, and specialist appointments.
- **Frontend UI**: Next.js 15, TailwindCSS, and a WebGL 3D Shader Dark Orb Visualizer.

---

## 🚀 The 10-Day Building Journey

### Days 1–3: Starter Setup, Native Scripts & 3D Dark Orb UI
I started by setting up the LiveKit pipeline with **Murf Falcon TTS (Anisha voice)**. To ensure natural pronunciation for Indian languages, I enforced strict native script rules in the system prompt — forcing Hindi to be written in Devanagari (e.g. नमस्ते instead of romanized "namaste").

On the frontend, I built a 3D WebGL Dark Orb particle visualizer supporting 5 distinct Agent States: `Ready`, `Connecting`, `Listening`, `Speaking`, and `Ended`.

### Day 4: Persistent Memory with Consent Protocol
To make the agent remember returning users across calls, I built an SQLite storage engine (`user_memory` table). The agent strictly obeys a **Consent-First Protocol** — asking permission (*"May I remember your name and district for next time?"*) before saving any context.

### Day 5: Live Domain Tools & Graceful Offline Fallbacks
Instead of guessing or hallucinating facts, the agent uses three live tools:
1. `find_nearby_health_centre`: Live OpenStreetMap Overpass lookup for nearby hospitals and PHCs.
2. `check_local_health_advisory`: Live Open-Meteo temperature, heat index, and air quality (AQI) readings.
3. `assess_symptom_urgency`: Local deterministic triage sorting symptoms into `red` (emergency), `amber` (see doctor), or `green` (self-care).

If a rural network drops and an API times out, the agent gracefully admits failure out loud (*"The live map directory could not be reached..."*), reads a bundled offline hospital list, and provides official Indian helplines (112, 108).

### Day 6: Outbound Calls & Reminders
Added `tool_trigger_outbound_reminder` allowing the agent to schedule follow-up check-in calls for medication compliance or vaccination alerts.

### Day 7: Emergency Escalation to ASHA Workers / Doctors
AI should never try to handle critical emergencies alone. When red-flag symptoms (chest pain, stroke signs, severe breathlessness) are detected, the agent:
1. Delivers an immediate emergency warning and 112 helpline instructions.
2. Obtains caller permission and creates an escalation record in the `human_escalations` table with a concise summary for ASHA workers/doctors.

### Day 8: Call Analytics Dashboard
Built a live Call Analytics Dashboard backed by a Next.js `/api/analytics` route. Every call outcome (`success`, `failed`, `escalated`) and duration is automatically recorded upon disconnection, displaying live performance metrics and SQLite call logs.

### Day 9: Specialist Agent Handoff (`ClinicAppointmentAgent`)
One agent shouldn't try to do everything. I created a dedicated **Clinic & Appointment Specialist** (`ClinicAppointmentAgent`) with a distinct Murf Falcon voice (**Pooja**). 

When a user asks to book a doctor slot, the Main Agent (voice: **Anisha**) invokes `transfer_to_clinic_specialist`. The conversation transfers seamlessly — inheriting previous caller context — while switching the voice to **Pooja** and rendering a purple **`DAY 9 HANDOFF`** card on screen!

---

## ⚡ Challenges Faced & Solutions

1. **Eliminating Startup Latency**:
   - *Problem*: Heavy turn-detector imports were causing a 50-second startup lag before registering the worker.
   - *Fix*: Optimized plugin imports in `agent.py`, bringing startup and worker registration down to **under 1 second**!

2. **Flawless Indian Pronunciation**:
   - *Problem*: Romanized Hindi caused TTS engines to speak with an English accent.
   - *Fix*: Enforcing Devanagari script (हिंदी) allowed Murf Falcon to deliver authentic, natural Indian voice responses.

---

## 💻 How to Run the Project

```bash
# 1. Clone the repo
git clone https://github.com/Jagrati850/MURFD2.git
cd MURFD2

# 2. Configure .env.local in backend and frontend

# 3. Start Backend & Frontend using PowerShell
.\start_app.ps1

# Or start manually:
# Terminal 1 (Backend): cd backend && uv run python src/agent.py dev
# Terminal 2 (Frontend): cd frontend && pnpm dev
```

Open `http://localhost:3000` in your browser!

---

## 🔗 Repository & Conclusion

Building this voice agent proved how transformative **low-latency TTS APIs like Murf Falcon** are for building real-world, accessible AI solutions in India.

- 📦 **GitHub Repository**: [https://github.com/Jagrati850/MURFD2.git](https://github.com/Jagrati850/MURFD2.git)
- 🎙️ **Built for**: Voice for Bharat Challenge 2026 by Murf AI

*Thank you for following along on this 10-day journey!*
