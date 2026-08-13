# Health Access Voice Agent — Day 5: Tools

A multilingual voice agent for health access in India. It listens, judges how urgent a
symptom sounds, finds a real place to go, and checks today's heat and air quality —
speaking in whichever language the user speaks, in that language's own script.

Built with the fastest TTS API, **Murf Falcon** (voice: Anisha), on LiveKit Agents,
with Deepgram Nova-3 for multilingual speech-to-text and Google Gemini as the LLM.

- **Day 4** gave the agent persistent memory (SQLite).
- **Day 5** gives it tools: it now fetches real data instead of improvising.

## Is the data live or local?

This is the honest answer the challenge asks for — some of it is live, some is not.

| Tool | Data | Source | Live? |
|---|---|---|---|
| `find_nearby_health_centre` | Hospitals, clinics, PHCs near a place, nearest first | OpenStreetMap — Nominatim geocoding + Overpass API | **Live**, fetched per call |
| `find_nearby_health_centre` (PIN codes) | PIN code → district and state | India Post PIN code API | **Live** |
| `find_nearby_health_centre` (fallback) | Government hospitals for 15 districts | `backend/data/health_facilities.json` | **Local** — hand-built, used only when the live lookup fails |
| `check_local_health_advisory` | Temperature, feels-like, humidity, PM2.5, US AQI | Open-Meteo forecast + air-quality APIs | **Live**, fetched per call |
| `assess_symptom_urgency` | Red / amber / green urgency band | `backend/src/health_tools.py` ruleset | **Local** — a fixed offline checklist, by design |
| Helpline numbers (112, 108, 104, 14416, 1098) | Official Indian public helplines | Hardcoded | **Static** |

None of the live sources needs an API key.

### About the local pieces

The offline facility list is **hand-built and not live**. It names widely known government
and medical-college hospitals per district with area names only. It deliberately carries
**no phone numbers and no opening hours** — inventing those would be worse than omitting
them, so the agent offers the official helplines instead and tells the user to confirm
before travelling. `backend/data/health_facilities.json` states this in its own `meta`
block, and the agent says it out loud whenever it falls back.

The triage ruleset is local on purpose: urgency sorting must be deterministic and must
work with no network. It **never names a disease and never suggests a medicine** — it only
answers "how soon should this person be seen, and by whom".

## The three tools, and when they fire

The agent is told to call these on its own initiative — the user never has to ask.

**`assess_symptom_urgency`** fires the moment anyone describes how they feel, in English,
Hinglish or Devanagari ("mujhe bukhar hai", "सीने में दर्द हो रहा है", "my child has loose
motions"). It matches against three keyword sets — emergency, urgent, routine — then
escalates for infants, elders and existing conditions like diabetes or asthma, and reports
which indicators matched so the agent can explain itself.

**`find_nearby_health_centre`** fires when someone needs a place to go, and — importantly —
fires *unprompted* right after triage returns red or amber. Somebody who has just been told
to see a doctor needs an address, not more advice.

**`check_local_health_advisory`** fires when the conversation touches heat, sun,
dehydration, pollution, breathing trouble or "is it safe to go out today".

### Two tools chained through memory

The district a user gave on Day 4 feeds Day 5's lookups. `home_district` was added to the
memory table (with a migration for databases created on Day 4), and both live tools accept
an empty location — falling back to the saved district instead of asking again. Results
carry `location_came_from_memory` so the UI can show that it was remembered.

```
Day 4:  "I'm in Varanasi"  →  consent asked  →  home_district saved
Day 5:  "koi clinic hai?"  →  no location asked  →  facilities near Varanasi, live
```

### Timestamps

Every result carries `data_as_of` (ISO 8601, UTC) and `data_as_of_spoken` (e.g.
"11 August 2026 at 9:20 PM IST"), and the agent is instructed to say when the reading was
taken. Yesterday's AQI and today's AQI lead to different decisions.

## When a source is down, the agent says so

Rural connections drop. A silent agent is a broken agent, and a confident wrong answer is
worse. Every lookup degrades in a fixed order:

1. **Live source works** → `status: ok`, `data_freshness: live`.
2. **Live source times out or errors** → `status: fallback`, `data_freshness: local`. The
   agent says the live directory could not be reached, reads the offline list, and warns
   that details may be out of date.
3. **No live data and no offline entry** → `status: unavailable`, `data_freshness: none`.
   The result contains **no facilities and no numbers at all** — only a `spoken_fallback`
   line admitting the failure, the real helplines, and an offer to retry.

Timeouts are 8 seconds for geocoding, PIN codes and weather; 20 for Overpass. Every result
carries a plain-language `reason` ("the map service timed out") so the agent can tell the
user *why*, not just *that*, it failed.

Tests cover all three paths, so the graceful failure is verifiable without unplugging
anything: `test_facility_lookup_falls_back_to_offline_list_on_timeout` and
`test_facility_lookup_admits_defeat_when_district_is_unknown`.

To demo the failure live, turn off Wi-Fi mid-conversation and ask "nearest hospital?".

## On-screen data

`frontend/components/app/health-data-panel.tsx` renders what the agent fetched while it is
speaking. The backend mirrors every tool result over the LiveKit data channel on topic
`health_data`; the panel shows triage colour, facility list and today's readings, each with
a **LIVE / OFFLINE LIST / UNAVAILABLE** badge and the fetch time. Failures render as a red
card showing the reason — the fallback is visible, not hidden.

The panel is decorative only. If it breaks, the voice conversation is unaffected.

## Language and script

STT runs Deepgram `nova-3` with `language="multi"`, turn detection uses the multilingual
model, and the Murf voice is set as `Anisha` with **no locale key hardcoded**, so the voice
follows the text. The prompt requires every language to be written in its own script —
Hindi in Devanagari (नमस्ते), never romanized.

## Running it

```bash
# backend
cd backend
cp .env.example .env.local      # fill in LiveKit, Murf, Deepgram and Google keys
uv sync
uv run python src/agent.py dev

# frontend, in a second terminal
cd frontend
pnpm install
pnpm dev
```

Or run everything at once from the project root: `./start_app.sh` (or `start_app.ps1` on
PowerShell). Then open http://localhost:3000.

Tests:

```bash
cd backend
uv run pytest          # 49 tests, no network needed — HTTP is faked
```

## Try these

| Say this | What should happen |
|---|---|
| "मुझे तीन दिन से बुखार है" | triage → amber, then a facility lookup, answered in Devanagari |
| "seene mein dard ho raha hai" | triage → red, emergency message and 112 first |
| "Is there a clinic near 221005?" | PIN code resolved live, nearest facilities read out with distances |
| "Aaj bahar kaam karna theek rahega?" | live temperature, feels-like and AQI with one precaution |
| "I'm in Varanasi" → consent → later "koi hospital hai?" | location reused from memory, never asked twice |
| Any of the above with Wi-Fi off | spoken fallback, offline list or helplines — never silence |

## Guardrails

Not a doctor and it says so. It does not diagnose, does not name or recommend any medicine
including over-the-counter ones, and refuses requests for prescriptions or medical
certificates. Chest pain, breathlessness, stroke signs, unconsciousness, heavy bleeding,
fever with confusion and any mention of self-harm all short-circuit the conversation into
the emergency message and 112. Memory is written **only after explicit consent**, and
"forget everything" deletes the row.

## Files changed on Day 5

```
backend/src/health_tools.py            new — the three lookups, timeouts, fallbacks, timestamps
backend/data/health_facilities.json    new — offline district list (disclosed above)
backend/src/agent.py                   three tools registered, prompt sections, UI mirroring
backend/src/memory.py                  home_district column + migration for Day 4 databases
frontend/components/app/health-data-panel.tsx   new — on-screen fetched data
frontend/components/app/view-controller.tsx     mounts the panel
backend/tests/                         new — 49 tests, including the failure paths
```

## Day 5 checklist

- [x] At least one tool that fetches real domain data — three, two of them live
- [x] Genuine sources (OpenStreetMap, Open-Meteo, India Post), local dataset disclosed
- [x] Tool descriptions written to drive when the model fires them
- [x] Failures are audible, never silent, never invented
- [x] Data is timestamped and the timestamp is spoken
- [x] Two tools chained through Day 4 memory (`home_district`)
- [x] Fetched data rendered on screen
- [x] README states what is live and what is local
- [ ] Record the demo video, including one graceful failure
- [ ] Post on LinkedIn — mention **Murf Falcon**, tag Murf AI, add `#VoiceForBharat`
- [ ] Submit the post URL in the form
