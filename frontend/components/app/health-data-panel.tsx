'use client';

import React, { useEffect, useState } from 'react';
import { RoomEvent } from 'livekit-client';
import { Activity, AlertTriangle, Hospital, Wind, UserCheck, CalendarCheck } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useRoomContext } from '@livekit/components-react';

type Facility = {
  name: string;
  category?: string;
  distance_km?: number;
  area?: string;
  address?: string;
  phone?: string;
};

type ToolResult = {
  status?: string;
  data_freshness?: 'live' | 'local' | 'none';
  source?: string;
  reason?: string;
  spoken_fallback?: string;
  data_as_of_spoken?: string;
  // triage
  triage_level?: 'red' | 'amber' | 'green' | 'unclear';
  urgency?: string;
  recommended_action?: string;
  matched_indicators?: string[];
  // facilities
  district?: string;
  state?: string;
  location_resolved?: string;
  location_came_from_memory?: boolean;
  facilities?: Facility[];
  // advisory
  temperature_c?: number;
  feels_like_c?: number;
  humidity_percent?: number;
  us_aqi?: number;
  heat_risk?: string;
  air_quality?: string;
  // handoff (Day 9)
  agent_name?: string;
  voice?: string;
  specialist_role?: string;
  message?: string;
  // appointment (Day 9)
  appointment_id?: string;
  facility_name?: string;
  date?: string;
  time_slot?: string;
};

type Payload = { kind: 'triage' | 'facilities' | 'advisory' | 'handoff' | 'appointment'; payload: ToolResult };

const TRIAGE_STYLES: Record<string, { dot: string; label: string }> = {
  red: { dot: 'bg-red-500', label: 'EMERGENCY' },
  amber: { dot: 'bg-amber-400', label: 'SEE A DOCTOR SOON' },
  green: { dot: 'bg-emerald-400', label: 'SELF CARE' },
  unclear: { dot: 'bg-neutral-400', label: 'NEED MORE DETAIL' },
};

function FreshnessBadge({ result }: { result: ToolResult }) {
  const freshness = result.data_freshness ?? 'none';
  const styles =
    freshness === 'live'
      ? 'border-emerald-400/40 text-emerald-300'
      : freshness === 'local'
        ? 'border-amber-400/40 text-amber-300'
        : 'border-red-400/40 text-red-300';
  const label =
    freshness === 'live' ? 'LIVE' : freshness === 'local' ? 'OFFLINE LIST' : 'UNAVAILABLE';

  return (
    <span className={`rounded border px-1.5 py-0.5 text-[10px] tracking-wider ${styles}`}>
      {label}
    </span>
  );
}

function Card({
  icon,
  title,
  result,
  children,
  badgeOverride,
}: {
  icon: React.ReactNode;
  title: string;
  result: ToolResult;
  children: React.ReactNode;
  badgeOverride?: React.ReactNode;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      className="rounded-xl border border-white/10 bg-black/80 p-3 shadow-2xl backdrop-blur-md"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-white">
          {icon}
          <span className="text-xs font-semibold tracking-wide">{title}</span>
        </div>
        {badgeOverride || <FreshnessBadge result={result} />}
      </div>
      <div className="space-y-1.5 text-[11px] leading-relaxed text-neutral-300">{children}</div>
      {result.data_as_of_spoken && (
        <p className="mt-2 border-t border-white/10 pt-1.5 text-[10px] text-neutral-500">
          Fetched {result.data_as_of_spoken}
        </p>
      )}
    </motion.div>
  );
}

function FailureNote({ result }: { result: ToolResult }) {
  if (!result.spoken_fallback) return null;
  return (
    <div className="rounded-lg border border-red-400/30 bg-red-500/10 p-2">
      <div className="mb-1 flex items-center gap-1.5 text-red-300">
        <AlertTriangle className="h-3 w-3" />
        <span className="text-[10px] font-semibold tracking-wider">SOURCE UNAVAILABLE</span>
      </div>
      {result.reason && <p className="text-[10px] text-red-200/80">Reason: {result.reason}</p>}
      <p className="mt-1 text-[11px] text-neutral-200">{result.spoken_fallback}</p>
    </div>
  );
}

function HandoffCard({ result }: { result: ToolResult }) {
  return (
    <Card
      icon={<UserCheck className="h-3.5 w-3.5 text-purple-400" />}
      title="Agent Handoff Active"
      result={result}
      badgeOverride={
        <span className="rounded border border-purple-400/50 bg-purple-950/60 px-1.5 py-0.5 text-[10px] tracking-wider text-purple-300 font-bold">
          DAY 9 HANDOFF
        </span>
      }
    >
      <div className="space-y-1 rounded-lg border border-purple-500/20 bg-purple-950/30 p-2.5">
        <div className="text-xs font-bold text-purple-200">{result.agent_name || 'Specialist Agent'}</div>
        <div className="text-[10px] text-purple-300/80">Voice: <span className="font-semibold text-white">{result.voice || 'Pooja (Murf Falcon)'}</span></div>
        <div className="text-[10px] text-neutral-300">{result.specialist_role}</div>
      </div>
      <p className="text-[10px] text-emerald-300 flex items-center gap-1 mt-1">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
        {result.message}
      </p>
    </Card>
  );
}

function AppointmentCard({ result }: { result: ToolResult }) {
  return (
    <Card
      icon={<CalendarCheck className="h-3.5 w-3.5 text-emerald-400" />}
      title="Appointment Confirmed"
      result={result}
      badgeOverride={
        <span className="rounded border border-emerald-400/50 bg-emerald-950/60 px-1.5 py-0.5 text-[10px] tracking-wider text-emerald-300 font-bold">
          BOOKED
        </span>
      }
    >
      <div className="space-y-1 rounded-lg border border-emerald-500/20 bg-emerald-950/30 p-2.5">
        <div className="text-xs font-bold text-emerald-200">{result.facility_name || 'Primary Health Centre'}</div>
        <div className="text-[10px] text-neutral-300">Date: <span className="font-semibold text-white">{result.date}</span> ({result.time_slot})</div>
        <div className="text-[10px] font-mono text-emerald-400">Token ID: {result.appointment_id}</div>
      </div>
    </Card>
  );
}

function TriageCard({ result }: { result: ToolResult }) {
  const style = TRIAGE_STYLES[result.triage_level ?? 'unclear'] ?? TRIAGE_STYLES.unclear;
  return (
    <Card icon={<Activity className="h-3.5 w-3.5" />} title="Symptom urgency" result={result}>
      <div className="flex items-center gap-2">
        <span className={`h-2.5 w-2.5 rounded-full ${style.dot}`} />
        <span className="text-xs font-semibold text-white">{style.label}</span>
      </div>
      {result.urgency && <p className="text-neutral-400">{result.urgency}</p>}
      {result.recommended_action && <p>{result.recommended_action}</p>}
      {!!result.matched_indicators?.length && (
        <p className="text-neutral-500">Matched: {result.matched_indicators.join(', ')}</p>
      )}
      <FailureNote result={result} />
    </Card>
  );
}

function FacilitiesCard({ result }: { result: ToolResult }) {
  return (
    <Card icon={<Hospital className="h-3.5 w-3.5" />} title="Nearby health centres" result={result}>
      {(result.district || result.location_resolved) && (
        <p className="text-neutral-400">
          {result.district || result.location_resolved}
          {result.state ? `, ${result.state}` : ''}
          {result.location_came_from_memory && (
            <span className="ml-1 text-[10px] text-sky-300">(from saved memory)</span>
          )}
        </p>
      )}
      {result.facilities?.map((f) => (
        <div key={f.name} className="border-l border-white/10 pl-2">
          <p className="text-neutral-100">{f.name}</p>
          <p className="text-[10px] text-neutral-500">
            {[f.category, f.area || f.address, f.distance_km ? `${f.distance_km} km` : null]
              .filter(Boolean)
              .join(' · ')}
          </p>
        </div>
      ))}
      <FailureNote result={result} />
    </Card>
  );
}

function AdvisoryCard({ result }: { result: ToolResult }) {
  const rows: [string, string][] = [];
  if (result.temperature_c != null) rows.push(['Temperature', `${result.temperature_c} °C`]);
  if (result.feels_like_c != null) rows.push(['Feels like', `${result.feels_like_c} °C`]);
  if (result.humidity_percent != null) rows.push(['Humidity', `${result.humidity_percent}%`]);
  if (result.us_aqi != null) rows.push(['Air quality (US AQI)', `${result.us_aqi}`]);

  return (
    <Card icon={<Wind className="h-3.5 w-3.5" />} title="Today's conditions" result={result}>
      {result.location_resolved && (
        <p className="truncate text-neutral-400">{result.location_resolved}</p>
      )}
      {rows.map(([label, value]) => (
        <div key={label} className="flex items-baseline justify-between gap-2">
          <span className="text-neutral-500">{label}</span>
          <span className="text-neutral-100">{value}</span>
        </div>
      ))}
      {result.heat_risk && result.heat_risk !== 'unknown' && (
        <p className="text-amber-200/90">Heat risk: {result.heat_risk}</p>
      )}
      {result.air_quality && result.air_quality !== 'unknown' && (
        <p className="text-sky-200/90">Air: {result.air_quality}</p>
      )}
      <FailureNote result={result} />
    </Card>
  );
}

export function HealthDataPanel() {
  const room = useRoomContext();
  const [cards, setCards] = useState<Record<string, ToolResult>>({});

  useEffect(() => {
    if (!room) return;

    const onData = (payload: Uint8Array, _p: unknown, _k: unknown, topic?: string) => {
      if (topic !== 'health_data') return;
      try {
        const message = JSON.parse(new TextDecoder().decode(payload)) as Payload;
        if (!message?.kind) return;
        setCards((prev) => ({ ...prev, [message.kind]: message.payload }));
      } catch (err) {
        console.warn('Could not parse health_data payload', err);
      }
    };

    room.on(RoomEvent.DataReceived, onData);
    return () => {
      room.off(RoomEvent.DataReceived, onData);
    };
  }, [room]);

  const hasAnything = Object.keys(cards).length > 0;
  if (!hasAnything) return null;

  return (
    <div className="pointer-events-none fixed top-20 left-6 z-40 w-[19rem] max-w-[calc(100vw-3rem)] space-y-2 font-mono">
      <p className="text-[10px] tracking-[0.2em] text-neutral-500">LIVE AGENT & TOOL DATA</p>
      <div className="max-h-[calc(100vh-8rem)] space-y-2 overflow-y-auto pr-1 pointer-events-auto">
        <AnimatePresence mode="popLayout">
          {cards.handoff && <HandoffCard key="handoff" result={cards.handoff} />}
          {cards.appointment && <AppointmentCard key="appointment" result={cards.appointment} />}
          {cards.triage && <TriageCard key="triage" result={cards.triage} />}
          {cards.facilities && <FacilitiesCard key="facilities" result={cards.facilities} />}
          {cards.advisory && <AdvisoryCard key="advisory" result={cards.advisory} />}
        </AnimatePresence>
      </div>
    </div>
  );
}
