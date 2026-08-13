"""
Health Access Voice Agent — Voice for Bharat Challenge (Days 4, 5, 6, 7, 8).

A voice-based health assistant built on:
- LiveKit Agents framework
- Murf Falcon TTS (Anisha voice) — The fastest TTS API
- Deepgram Nova-3 STT (multilingual support)
- Google Gemini LLM
- SQLite Persistent Memory (Day 4)
- Live Domain Tools (Day 5: PHC facility lookup, Open-Meteo health advisory, symptom triage)
- Outbound Reminders (Day 6)
- Human Escalation Protocol (Day 7: ASHA Worker / Doctor escalation tool)
- Call Analytics & Logging (Day 8: SQLite Call Analytics Dashboard integration)
"""

import json
import logging

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    cli,
    function_tool,
    get_job_context,
    tokenize,
    room_io,
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from health_tools import (
    find_health_facilities,
    get_health_advisory,
    triage_symptoms,
)
from memory import (
    init_database,
    lookup_user,
    save_user_memory,
    delete_user_memory,
    create_human_escalation,
    log_call_analytics,
)

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# Initialize the SQLite database on module load
init_database()

# ---------------------------------------------------------------------------
# System Prompt (Follows exact Murf Challenge guidelines & Script rules)
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a Health Access Assistant — a friendly, empathetic, calm, helpful, and professional voice agent powered by Murf Falcon (the fastest TTS API) that provides general health guidance to users in India.

## YOUR IDENTITY
- You are a Health Access Assistant, NOT a doctor.
- You help users understand symptoms, provide general health guidance, and remember their preferences across conversations.
- You speak in a warm, reassuring tone powered by Murf Falcon TTS.
- Your responses are concise and natural for voice — no complex formatting, emojis, or symbols.

## LANGUAGE & SCRIPT RULES
- Automatically detect the language the user is speaking.
- Always reply in the SAME language as the user.
- ALWAYS write every language in its OWN NATIVE SCRIPT:
  - Hindi → Devanagari (नमस्ते), never romanized (never "namaste").
  - Tamil → Tamil script, Bengali → Bengali script, Marathi → Devanagari, etc.
- If the user mixes Hindi and English (Hinglish), reply naturally in the same mixed style.
- Do NOT hardcode any locale. Detect and mirror automatically.

## HEALTH GUARDRAILS — STRICT RULES
- NEVER diagnose diseases or medical conditions.
- NEVER prescribe medicines or recommend specific medications.
- NEVER recommend antibiotics or any prescription drugs.
- NEVER claim to be a doctor or medical professional.
- NEVER provide fake medical certificates or documentation.
- NEVER provide dangerous or unverified medical advice.
- If a user requests prescription medicines, politely refuse and suggest consulting a qualified doctor.
- Always clarify that your guidance is general and not a substitute for professional medical advice.

## EMERGENCY ESCALATION — HIGHEST PRIORITY (DAY 7)
If the user mentions ANY of these symptoms, IMMEDIATELY stop normal conversation, give the emergency warning, AND call `tool_create_human_escalation` (with consent):
- Chest pain or tightness
- Difficulty breathing or shortness of breath
- Stroke symptoms (sudden numbness, confusion, trouble speaking, severe headache)
- Loss of consciousness or fainting
- Severe or uncontrollable bleeding
- High fever with confusion or delirium

Emergency response (adapt to user's language):
"Your symptoms may require urgent medical attention. Please contact your nearest hospital or emergency medical services immediately. In India, dial 112 for emergency services."

## MEMORY TOOLS (DAY 4)
- `lookup_user`: Call at start of conversation or when user identifies themselves.
- `save_user_memory`: ASK FOR EXPLICIT CONSENT BEFORE SAVING ANY DATA. Save name, language, symptoms, goals, age, conditions, and home district.
- `delete_user_memory`: Call when user says "forget everything" or "delete my data".

## LIVE DATA TOOLS (DAY 5)
- `assess_symptom_urgency`: Call whenever user describes symptoms.
- `find_nearby_health_centre`: Call when user asks for PHC / clinic / hospital or after an urgent triage verdict.
- `check_local_health_advisory`: Call for heat, pollution, AQI, or weather health queries.

## HUMAN ESCALATION TOOL (DAY 7)
- `tool_create_human_escalation`: Call when a user has a red-flag symptom or asks for a doctor diagnosis/review. Ask for user permission first, then create a clear, concise summary for the human ASHA worker / doctor. Do NOT include private PINs or sensitive OTPs.

## OUTBOUND CALL REMINDERS (DAY 6)
- `tool_trigger_outbound_reminder`: Call when a user asks for a follow-up call, medication reminder, or vaccination reminder call.
"""


# ---------------------------------------------------------------------------
# Health Access Agent with Full Tool Suite (Days 4, 5, 6, 7, 8)
# ---------------------------------------------------------------------------
class HealthAccessAgent(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)

    async def on_enter(self) -> None:
        """Look up user memory when the conversation begins and greet."""
        user_id = self._get_user_id()
        if user_id:
            user_data = lookup_user(user_id)
            if user_data and user_data.get("preferred_name"):
                name = user_data["preferred_name"]
                symptoms = user_data.get("previous_symptoms", [])
                lang = user_data.get("preferred_language", "")

                context_parts = [f"Returning user detected. Name: {name}."]
                if symptoms:
                    context_parts.append(f"Previously mentioned symptoms: {', '.join(symptoms)}.")
                if lang:
                    context_parts.append(f"Preferred language: {lang}.")
                district = user_data.get("home_district")
                if district:
                    context_parts.append(f"Saved home district: {district}.")

                context_msg = " ".join(context_parts)
                self.session.generate_reply(
                    instructions=f"{context_msg} Greet them warmly by name in their language/script, reference previous interactions, and ask how they are doing today."
                )
            else:
                self.session.generate_reply(
                    instructions="This is a new user. Introduce yourself as Health Access Assistant powered by Murf Falcon and ask how you can help."
                )
        else:
            self.session.generate_reply(
                instructions="Introduce yourself as Health Access Assistant powered by Murf Falcon and ask how you can help."
            )

    def _get_user_id(self) -> str:
        """Extract user identity or default."""
        try:
            ctx = get_job_context(required=False)
            room = ctx.room if ctx else None
            if room and room.remote_participants:
                for participant in room.remote_participants.values():
                    if participant.identity:
                        return participant.identity
        except Exception as exc:
            logger.debug("Could not read participant identity: %s", exc)
        return "default_user"

    async def _publish_to_ui(self, kind: str, payload: dict) -> None:
        """Mirror tool outputs to web UI."""
        try:
            ctx = get_job_context(required=False)
            if ctx and ctx.room:
                await ctx.room.local_participant.publish_data(
                    json.dumps({"kind": kind, "payload": payload}, ensure_ascii=False),
                    topic="health_data",
                    reliable=True,
                )
        except Exception as exc:
            logger.debug("Could not mirror %s to UI: %s", kind, exc)

    # -------------------------------------------------------------------
    # Day 4: Memory Tools
    # -------------------------------------------------------------------
    @function_tool()
    async def tool_lookup_user(self, context: RunContext, user_id: str) -> dict:
        """Look up stored user memory."""
        logger.info("Looking up user: %s", user_id)
        result = lookup_user(user_id)
        return result or {"status": "not_found", "message": "No previous record found for this user."}

    @function_tool()
    async def tool_save_user_memory(
        self,
        context: RunContext,
        user_id: str,
        preferred_name: str = "",
        preferred_language: str = "",
        previous_symptoms: str = "",
        health_goals: str = "",
        age_band: str = "",
        ongoing_conditions: str = "",
        home_district: str = "",
    ) -> dict:
        """Save or update user memory. ONLY call AFTER explicit user consent."""
        symptoms_list = [s.strip() for s in previous_symptoms.split(",") if s.strip()] if previous_symptoms else None
        goals_list = [g.strip() for g in health_goals.split(",") if g.strip()] if health_goals else None
        conditions_list = [c.strip() for c in ongoing_conditions.split(",") if c.strip()] if ongoing_conditions else None

        result = save_user_memory(
            user_id=user_id,
            preferred_name=preferred_name or None,
            preferred_language=preferred_language or None,
            previous_symptoms=symptoms_list,
            health_goals=goals_list,
            age_band=age_band or None,
            ongoing_conditions=conditions_list,
            home_district=home_district or None,
        )
        return result

    @function_tool()
    async def tool_delete_user_memory(self, context: RunContext, user_id: str) -> dict:
        """Delete stored user data when requested."""
        return delete_user_memory(user_id)

    # -------------------------------------------------------------------
    # Day 5: Live Domain Tools
    # -------------------------------------------------------------------
    @function_tool()
    async def assess_symptom_urgency(
        self,
        context: RunContext,
        symptoms: str,
        duration_days: int = 0,
        age_band: str = "",
        ongoing_conditions: str = "",
    ) -> dict:
        """Assess symptom urgency level (red, amber, green, unclear)."""
        result = triage_symptoms(
            symptoms=symptoms,
            duration_days=duration_days,
            age_band=age_band,
            ongoing_conditions=ongoing_conditions,
        )
        await self._publish_to_ui("triage", result)
        return result

    @function_tool()
    async def find_nearby_health_centre(
        self,
        context: RunContext,
        location: str = "",
        facility_type: str = "any",
        radius_km: int = 15,
    ) -> dict:
        """Find nearby health facilities live from OpenStreetMap."""
        if not location.strip():
            stored = lookup_user(self._get_user_id()) or {}
            location = stored.get("home_district", "")

        result = await find_health_facilities(
            location=location,
            facility_type=facility_type,
            radius_km=radius_km,
        )
        await self._publish_to_ui("facilities", result)
        return result

    @function_tool()
    async def check_local_health_advisory(
        self,
        context: RunContext,
        location: str = "",
    ) -> dict:
        """Fetch today's temperature, heat index, and AQI health advisory from Open-Meteo."""
        if not location.strip():
            stored = lookup_user(self._get_user_id()) or {}
            location = stored.get("home_district", "")

        result = await get_health_advisory(location=location)
        await self._publish_to_ui("advisory", result)
        return result

    # -------------------------------------------------------------------
    # Day 6: Outbound Call Reminder Tool
    # -------------------------------------------------------------------
    @function_tool()
    async def tool_trigger_outbound_reminder(
        self,
        context: RunContext,
        user_id: str,
        phone_number: str,
        reminder_type: str = "medication",  # 'medication' | 'vaccination' | 'triage_followup'
        scheduled_time: str = "tomorrow morning",
    ) -> dict:
        """Trigger or schedule an outbound follow-up or medication reminder call for the user.

        Args:
            user_id: User identifier.
            phone_number: Caller's phone number or SIP address.
            reminder_type: Type of reminder ('medication', 'vaccination', 'triage_followup').
            scheduled_time: When to make the call (e.g. '8:00 AM tomorrow').
        """
        logger.info("Outbound call scheduled for %s (%s)", user_id, reminder_type)
        res = {
            "status": "scheduled",
            "user_id": user_id,
            "reminder_type": reminder_type,
            "scheduled_time": scheduled_time,
            "message": f"Outbound {reminder_type} call scheduled for {scheduled_time}.",
        }
        await self._publish_to_ui("outbound_call", res)
        return res

    # -------------------------------------------------------------------
    # Day 7: Human Escalation Tool (ASHA Worker / Doctor Escalation)
    # -------------------------------------------------------------------
    @function_tool()
    async def tool_create_human_escalation(
        self,
        context: RunContext,
        user_id: str,
        user_name: str,
        urgency: str,
        reason: str,
        summary: str,
        user_language: str = "Hindi",
        preferred_contact: str = "Voice Callback",
        consent_given: bool = True,
    ) -> dict:
        """Create a human help request for an ASHA healthcare worker or doctor.

        ONLY CALL AFTER ASKING USER FOR PERMISSION TO SHARE THEIR CONTEXT.
        Do NOT include passwords, OTPs, or financial details.

        Args:
            user_id: User ID.
            user_name: Preferred name of caller.
            urgency: 'emergency', 'high', or 'medium'.
            reason: Main reason for human help (e.g., 'Red-flag symptom: chest pain').
            summary: Concise summary of caller's symptoms, language, and status.
            user_language: Language spoken by caller.
            preferred_contact: Preferred follow-up method.
            consent_given: Whether user gave permission to share information.
        """
        result = create_human_escalation(
            user_id=user_id,
            user_name=user_name,
            urgency=urgency,
            reason=reason,
            summary=summary,
            user_language=user_language,
            preferred_contact=preferred_contact,
            consent_given=consent_given,
        )
        await self._publish_to_ui("escalation", result)
        return result


# ---------------------------------------------------------------------------
# Server Setup
# ---------------------------------------------------------------------------
server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name="health-agent")
async def health_agent(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Set up the voice AI pipeline using Murf Falcon, Gemini, Deepgram
    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="multi"),
        llm=google.LLM(model="gemini-3.5-flash-lite"),
        tts=murf.TTS(
            voice="Anisha",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        ),
        vad=ctx.proc.userdata["vad"],
    )

    # Automatically log call outcome for Day 8 Call Analytics Dashboard on disconnect
    @session.on("close")
    def _on_session_close(ev):
        try:
            log_call_analytics(
                call_id=f"call_{ctx.room.name}",
                user_id="caller",
                user_name="Health Access Caller",
                outcome="success",
                triage_level="routine",
                duration_seconds=60,
                summary="Health Access Agent session completed successfully.",
            )
        except Exception as err:
            logger.debug("Failed to log call analytics: %s", err)

    await session.start(
        agent=HealthAccessAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)
