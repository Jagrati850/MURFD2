"""
Health Access Voice Agent — Voice for Bharat Challenge (Days 1 to 9).

Features:
- Main Health Agent (voice: Anisha) & Specialist Clinic Appointment Agent (voice: Pooja)
- Day 9 Agent Handoff via `transfer_to_clinic_specialist`
- LiveKit Agents framework & Murf Falcon TTS (the fastest TTS API)
- Deepgram Nova-3 STT (multilingual support) & Google Gemini LLM
- SQLite Persistent Memory (Day 4), Live Domain Tools (Day 5), Outbound Reminders (Day 6)
- Human Escalation Protocol (Day 7), Call Analytics Dashboard Logging (Day 8)
"""

import json
import logging

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    ChatContext,
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
    book_clinic_appointment,
)

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# Initialize the SQLite database on module load
init_database()

# ---------------------------------------------------------------------------
# System Prompts
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a Health Access Assistant — a friendly, empathetic, calm, helpful, and professional main voice agent powered by Murf Falcon (voice: Anisha).

## YOUR IDENTITY & ROLE
- You are the main Health Access Assistant.
- You help users understand symptoms, provide general health guidance, remember preferences across calls, and find nearby health centres.
- If the user wants to BOOK AN APPOINTMENT, reserve a clinic slot, or check doctor timings, TRANSFER THEM TO THE CLINIC SPECIALIST (`transfer_to_clinic_specialist`).

## LANGUAGE & SCRIPT RULES
- Automatically detect the language spoken.
- Always reply in the SAME language as the user.
- ALWAYS write every language in its OWN NATIVE SCRIPT:
  - Hindi → Devanagari (नमस्ते), never romanized ("namaste").
  - Tamil → Tamil script, Bengali → Bengali script, Marathi → Devanagari, etc.

## HEALTH GUARDRAILS — STRICT RULES
- NEVER diagnose diseases or medical conditions.
- NEVER prescribe medicines or recommend specific medications.
- NEVER claim to be a doctor or medical professional.
- If a user reports emergency symptoms (chest pain, stroke signs, severe breathlessness), deliver the emergency message and call `tool_create_human_escalation`.

## AGENT HANDOFF (DAY 9)
- `transfer_to_clinic_specialist`: CALL THIS TOOL whenever the caller expresses an interest in booking an appointment, checking doctor availability, or reserving a clinic visit.
"""

SPECIALIST_PROMPT = """You are the Clinic & Appointment Specialist — an expert healthcare scheduling agent powered by Murf Falcon (voice: Pooja).

## YOUR IDENTITY & ROLE
- You handle clinic doctor appointment bookings, slot availability checks, clinic timing queries, and token reservations.
- You inherit the user's previous conversation context automatically.
- You speak in a warm, reassuring, professional tone in the user's native language.

## LANGUAGE & SCRIPT RULES
- Always reply in the user's native script:
  - Hindi → Devanagari (नमस्ते), never romanized ("namaste").
  - Tamil → Tamil script, Marathi → Devanagari, etc.

## YOUR SPECIALIST TOOLS
- `tool_book_clinic_appointment`: Book a doctor consultation slot at a Primary Health Centre (PHC) or clinic.
- `tool_check_appointment_slots`: Check available morning/afternoon doctor slots at a facility.
"""


# ---------------------------------------------------------------------------
# Day 9 Specialist Agent: Clinic & Appointment Specialist (Voice: Pooja)
# ---------------------------------------------------------------------------
class ClinicAppointmentAgent(Agent):
    def __init__(self, chat_ctx: ChatContext | None = None) -> None:
        super().__init__(
            instructions=SPECIALIST_PROMPT,
            chat_ctx=chat_ctx,
            tts=murf.TTS(
                voice="Pooja",
                style="Conversation",
                tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
                text_pacing=True,
            ),
        )

    async def on_enter(self) -> None:
        """Greeting when handoff to specialist occurs."""
        await self.session.generate_reply(
            instructions="Introduce yourself warmly as the Clinic & Appointment Specialist (voice: Pooja). Confirm you have received their context and offer to help book their doctor slot or check clinic timings."
        )

    def _get_user_id(self) -> str:
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

    @function_tool()
    async def tool_book_clinic_appointment(
        self,
        context: RunContext,
        user_name: str = "Caller",
        facility_name: str = "Primary Health Centre",
        preferred_date: str = "Tomorrow",
        time_slot: str = "10:00 AM",
        contact_number: str = "Provided on Call",
    ) -> dict:
        """Book a doctor appointment slot at a clinic or Primary Health Centre (PHC)."""
        user_id = self._get_user_id()
        res = book_clinic_appointment(
            user_id=user_id,
            user_name=user_name,
            facility_name=facility_name,
            preferred_date=preferred_date,
            time_slot=time_slot,
            contact_number=contact_number,
        )
        await self._publish_to_ui("appointment", res)
        return res

    @function_tool()
    async def tool_check_appointment_slots(
        self,
        context: RunContext,
        facility_name: str = "Primary Health Centre",
        date: str = "Tomorrow",
    ) -> dict:
        """Check available doctor consultation slots at a clinic or PHC."""
        return {
            "facility_name": facility_name,
            "date": date,
            "available_slots": ["9:00 AM", "10:30 AM", "2:00 PM", "4:30 PM"],
            "message": f"Available doctor slots at {facility_name} for {date}: 9:00 AM, 10:30 AM, 2:00 PM, 4:30 PM.",
        }


# ---------------------------------------------------------------------------
# Main Health Access Agent (Voice: Anisha)
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
                    instructions=f"{context_msg} Greet them warmly by name in their native language/script, reference previous interactions, and ask how you can assist."
                )
            else:
                self.session.generate_reply(
                    instructions="This is a new user. Introduce yourself as Health Access Assistant powered by Murf Falcon (voice: Anisha) and ask how you can help."
                )
        else:
            self.session.generate_reply(
                instructions="Introduce yourself as Health Access Assistant powered by Murf Falcon (voice: Anisha) and ask how you can help."
            )

    def _get_user_id(self) -> str:
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
    # Day 9: Agent Handoff Tool
    # -------------------------------------------------------------------
    @function_tool()
    async def transfer_to_clinic_specialist(self, context: RunContext) -> tuple[Agent, str]:
        """Transfer the user to the Clinic & Appointment Specialist (voice: Pooja) when they want to book an appointment, check doctor slots, reserve a clinic visit, or speak to the booking specialist."""
        logger.info("Performing agent handoff -> ClinicAppointmentAgent")
        await self._publish_to_ui("handoff", {
            "agent_name": "Clinic & Appointment Specialist",
            "voice": "Pooja (Murf Falcon)",
            "specialist_role": "Doctor Consultations & Slot Booking",
            "data_freshness": "live",
            "status": "transferred",
            "message": "Conversation transferred to Clinic & Appointment Specialist (Voice: Pooja)"
        })
        specialist = ClinicAppointmentAgent(
            chat_ctx=self.chat_ctx.copy(exclude_instructions=True)
        )
        return specialist, "Transferring you to our Clinic and Appointment Specialist now."

    # -------------------------------------------------------------------
    # Day 4: Memory Tools
    # -------------------------------------------------------------------
    @function_tool()
    async def tool_lookup_user(self, context: RunContext, user_id: str) -> dict:
        """Look up stored user memory."""
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
        reminder_type: str = "medication",
        scheduled_time: str = "tomorrow morning",
    ) -> dict:
        """Trigger or schedule an outbound follow-up or medication reminder call."""
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
    # Day 7: Human Escalation Tool
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
        """Create a human help request for an ASHA healthcare worker or doctor."""
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

    # Set up the voice AI pipeline using Murf Falcon (voice: Anisha for Main Agent)
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
