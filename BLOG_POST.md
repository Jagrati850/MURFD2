# Building an Autonomous Multilingual Health Access Voice Agent in 10 Days with Murf Falcon

> **#VoiceForBharat Challenge 2026** | **Health Access Track**  
> Built with **Murf Falcon** — the fastest TTS API in the industry.

---

## 📸 Showcase Gallery: System & Live Dashboard in Action

Here is a visual walk-through of the Health Access Voice Agent built over the 10-day challenge:

### 1. Hero Interface & 3D Dark Orb Visualizer (Day 3)
![Hero Landing Page & 3D Dark Orb Canvas](docs/images/hero-landing.png)
*Figure 1: Main Landing Page featuring the interactive 3D WebGL Dark Orb visualizer.*

### 2. Six Pillars of Agentic Health Access
![Five Pillars of Health Access](docs/images/five-pillars.png)
*Figure 2: Core architectural pillars of the Health Access Assistant.*

### 3. Live Active Call Audio Visualizer
![Live Active Call Audio Visualizer](docs/images/live-call-visualizer.png)
*Figure 3: Active Voice Session interface with live audio visualizer.*

### 4. Day 8/9 Call Analytics & Specialist Handoff Dashboard
![Day 8/9 Call Analytics & Specialist Handoff Dashboard](docs/images/analytics-dashboard.png)
*Figure 4: Call Analytics & Specialist Handoff Dashboard showing Total Calls, Success Ratio, Escalations, and Specialist Appointments.*

### 5. Live SQLite Call Logs & Triage Records
![Live Call Logs in SQLite](docs/images/live-sqlite-call-logs.png)
*Figure 5: Live SQLite Call Analytics & Triage Logs.*

---

## 📌 Executive Summary & 10-Day Milestone Journey

Over 10 days, I engineered an autonomous, multilingual **Health Access Voice Assistant** designed for Indian healthcare. The system evaluates symptom urgency, queries live Primary Health Centres (PHCs) and weather/AQI advisories, remembers user preferences with consent, schedules outbound reminders, escalates emergencies to human ASHA workers/doctors, tracks call analytics, and executes context-inherited agent handoffs to a specialist booking agent.

### 🌟 10-Day Building Milestones:

- **Day 1: Starter Setup & Murf Integration**
  - Tech Stack: Murf Falcon API (Anisha voice), Deepgram Nova-3, LiveKit Agents.
  - Outcome: Ultra-low latency voice pipeline initialized over WebRTC.

- **Day 2: Persona & Native Script Mirroring**
  - Tech Stack: System Prompt, Devanagari Hindi (नमस्ते).
  - Outcome: Strict native script mirroring so Murf Falcon speaks with an authentic Indian accent instead of an English accent.

- **Day 3: 3D Dark Orb UI & 5 Agent States**
  - Tech Stack: Next.js 15, TailwindCSS, WebGL Shader, Framer Motion.
  - Outcome: Dynamic state feedback across *Ready*, *Connecting*, *Listening*, *Speaking*, and *Ended*.

- **Day 4: Persistent Memory & Consent Protocol**
  - Tech Stack: SQLite (WAL Mode), `user_memory` table.
  - Outcome: Consent-first preference & symptom tracking across sessions.

- **Day 5: Live Domain Tools & Fallbacks**
  - Tech Stack: OpenStreetMap Overpass, Open-Meteo, Local Triage Rules.
  - Outcome: Real-time domain lookups with graceful offline fallback handling.

- **Day 6: Outbound Call Reminders**
  - Tech Stack: `tool_trigger_outbound_reminder`, LiveKit Telephony.
  - Outcome: Automated follow-up check-ins & medication reminders.

- **Day 7: Human Escalation Protocol**
  - Tech Stack: `tool_create_human_escalation`, `human_escalations` table.
  - Outcome: 112 emergency redirection & concise ASHA helper summaries.

- **Day 8: Call Analytics Dashboard**
  - Tech Stack: SQLite `call_analytics`, Next.js `/api/analytics`.
  - Outcome: Total Calls, Success %, Failure, and Escalation tracking.

- **Day 9: Specialist Agent Handoff**
  - Tech Stack: `ClinicAppointmentAgent` (Voice: Pooja), `transfer_to_clinic_specialist`.
  - Outcome: Context-inherited handoff to specialist with audible voice switch.

- **Day 10: Technical Retrospective & Open Source**
  - Tech Stack: Complete Documentation & Public GitHub Repository.
  - Outcome: Open-source release & community deployment guide.

---

## 🏗️ System Architecture & Workflow Diagrams

### 1. End-to-End Voice & Tool Execution Workflow

```text
[ Caller Voice Input ]
          │
          ▼
[ LiveKit Real-Time WebRTC Transport ]
          │
          ▼
[ Deepgram Nova-3 STT (Multilingual) ]
          │  Transcribed Text
          ▼
[ Google Gemini 3.5 Flash Lite LLM ] ──► [ Intent Evaluator ]
          │
          ├──► Symptom Mentioned   ──► assess_symptom_urgency Tool
          ├──► Facility Lookup    ──► find_nearby_health_centre Tool
          ├──► Weather / AQI      ──► check_local_health_advisory Tool
          ├──► Emergency Red-Flag ──► tool_create_human_escalation ──► [ SQLite DB ]
          └──► Appointment Booking──► transfer_to_clinic_specialist
                                               │
                                               ▼
                                  [ ClinicAppointmentAgent ]
                                    (Voice: Pooja - Murf Falcon)
                                               │
                                               ▼
                                  [ Audio Output to Caller ]
```

### 2. Day 9 Specialist Agent Handoff Sequence

```text
1. Caller: "I want to book an appointment at the clinic"
2. Main Agent (Voice: Anisha): Executes transfer_to_clinic_specialist with chat_ctx.copy()
3. System: Publishes "handoff" event to UI data channel (renders purple DAY 9 HANDOFF card)
4. Specialist Agent (Voice: Pooja): Takes over conversation seamlessly with inherited caller context
5. Specialist Agent: "Namaste! I am your Clinic Specialist (Voice: Pooja). Let's book your slot."
6. Caller: "Book for tomorrow at 10 AM"
7. Specialist Agent: Invokes tool_book_clinic_appointment -> Saves record to SQLite clinic_appointments table
8. System: Confirms appointment (Token ID: apt_7ab986ff)
```

---

## 🛠️ Domain Tools & Fallback Strategy (Day 5)

- **`find_nearby_health_centre`**:
  - *Purpose*: Finds hospitals, PHCs, and clinics near district/PIN code.
  - *Source*: OpenStreetMap Overpass & Nominatim API (Live).
  - *Fallback*: 8s timeout; falls back to offline list `health_facilities.json` + speaks fallback note out loud.

- **`check_local_health_advisory`**:
  - *Purpose*: Fetches temperature, heat index & US AQI air quality.
  - *Source*: Open-Meteo Weather & Air Quality API (Live).
  - *Fallback*: 8s timeout; speaks plain fallback note & heat precautions.

- **`assess_symptom_urgency`**:
  - *Purpose*: Sorts symptoms into Red, Amber, Green urgency bands.
  - *Source*: Local deterministic ruleset (`health_tools.py`).
  - *Fallback*: Runs offline; deterministic checklist ensuring high-risk symptoms trigger emergency warning.

---

## 📊 Database Schema Architecture (SQLite WAL Mode)

- **`user_memory`**: Stores `user_id`, `preferred_name`, `preferred_language`, `previous_symptoms`, `health_goals`, `age_band`, `ongoing_conditions`, `home_district`.
- **`human_escalations`**: Stores `escalation_id`, `user_id`, `user_name`, `urgency`, `reason`, `summary`, `user_language`, `status`.
- **`call_analytics`**: Stores `call_id`, `user_id`, `user_name`, `outcome`, `triage_level`, `duration_seconds`, `summary`, `timestamp`.
- **`clinic_appointments`**: Stores `appointment_id`, `user_id`, `user_name`, `facility_name`, `preferred_date`, `time_slot`, `contact_number`, `status`.

---

## 🔊 Voice Pipeline & Agent Persona Specification

- **Main Health Access Agent**:
  - TTS Engine: **Murf Falcon API** (Voice: **Anisha**)
  - Role: Warm, empathetic primary health assistant.
  - Primary Tools: `assess_symptom_urgency`, `find_nearby_health_centre`, `check_local_health_advisory`, `transfer_to_clinic_specialist`.

- **Specialist Clinic Agent**:
  - TTS Engine: **Murf Falcon API** (Voice: **Pooja**)
  - Role: Professional doctor appointment scheduler.
  - Primary Tools: `tool_book_clinic_appointment`, `tool_check_appointment_slots`.

---

## ⚡ Technical Challenges & Engineering Solutions

1. **Eliminating Startup Delay (From 56s down to <1s)**:
   - *Problem*: Pre-importing heavy transformer models in `agent.py` was causing a 56-second process initialization delay.
   - *Fix*: Optimized plugin imports in `agent.py`, allowing the LiveKit worker to register with LiveKit Cloud in **0.5 seconds**.

2. **Flawless Indian Accent Synthesis via Native Script Mirroring**:
   - *Problem*: English-romanized Hindi ("namaste aap kaise hain") was synthesized with an English accent.
   - *Fix*: Enforced strict Devanagari script rules in system prompts (e.g. नमस्ते), producing clear, authentic Indian pronunciation with Murf Falcon.

---

## 💻 Developer Setup & Running Locally

```bash
# 1. Clone Repository
git clone https://github.com/Jagrati850/MURFD2.git
cd MURFD2

# 2. Configure .env.local in backend and frontend

# 3. Launch both services using PowerShell:
.\start_app.ps1
```

- **GitHub Repository**: [https://github.com/Jagrati850/MURFD2.git](https://github.com/Jagrati850/MURFD2.git)
- **Built for**: Voice for Bharat Challenge 2026 by Murf AI
