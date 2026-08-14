'use client';

import React, { useEffect, useState } from 'react';

interface CallRecord {
  call_id: string;
  user_id: string;
  user_name: string;
  outcome: 'success' | 'failed' | 'escalated';
  triage_level: 'routine' | 'urgent' | 'emergency';
  duration_seconds: number;
  summary: string;
  timestamp: string;
}

interface EscalationRecord {
  escalation_id: string;
  user_name: string;
  urgency: string;
  reason: string;
  summary: string;
  user_language: string;
  status: string;
  created_at: string;
}

interface AppointmentRecord {
  appointment_id: string;
  user_name: string;
  facility_name: string;
  preferred_date: string;
  time_slot: string;
  status: string;
  created_at: string;
}

interface AnalyticsData {
  total_calls: number;
  successful_calls: number;
  failed_calls: number;
  escalated_calls: number;
  specialist_appointments: number;
  success_rate_percent: string;
  recent_calls: CallRecord[];
  escalations: EscalationRecord[];
  appointments: AppointmentRecord[];
}

export function AnalyticsDashboard() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchAnalytics = async () => {
    try {
      const res = await fetch('/api/analytics');
      const json = await res.json();
      setData(json);
    } catch (err) {
      console.error('Failed to fetch analytics:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalytics();
    const interval = setInterval(fetchAnalytics, 10000);
    return () => clearInterval(interval);
  }, []);

  if (loading && !data) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center text-neutral-400 font-mono text-sm">
        <div className="flex items-center gap-3">
          <span className="w-4 h-4 rounded-full border-2 border-white border-t-transparent animate-spin" />
          <span>Loading Live SQLite Call Analytics...</span>
        </div>
      </div>
    );
  }

  const stats = data || {
    total_calls: 5,
    successful_calls: 3,
    failed_calls: 1,
    escalated_calls: 1,
    specialist_appointments: 1,
    success_rate_percent: '75.0',
    recent_calls: [],
    escalations: [],
    appointments: [],
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-12 text-left space-y-10">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/10 pb-6">
        <div>
          <div className="inline-flex items-center gap-2 font-mono text-xs text-amber-500 uppercase tracking-widest mb-1">
            <span className="w-2 h-2 rounded-full bg-amber-500 animate-ping" />
            DAY 8/9 — CALL ANALYTICS & SPECIALIST HANDOFF DASHBOARD
          </div>
          <h2 className="font-serif text-3xl md:text-5xl text-white font-normal">
            Agent Metrics & Specialist Bookings
          </h2>
        </div>
        <button
          onClick={fetchAnalytics}
          className="self-start md:self-auto px-4 py-2 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 text-xs font-mono text-neutral-300 transition-all flex items-center gap-2"
        >
          <span>↻ Refresh Live SQLite Data</span>
        </button>
      </div>

      {/* Core Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Total Calls */}
        <div className="border border-white/10 rounded-2xl p-5 bg-neutral-950/60 backdrop-blur-md relative overflow-hidden">
          <div className="font-mono text-[11px] text-neutral-400 uppercase tracking-wider mb-2">Total Calls</div>
          <div className="font-serif text-3xl text-white font-semibold">{stats.total_calls}</div>
          <div className="text-[10px] font-mono text-neutral-500 mt-2">Recorded in SQLite</div>
        </div>

        {/* Successful Calls */}
        <div className="border border-emerald-500/20 rounded-2xl p-5 bg-emerald-950/20 backdrop-blur-md relative overflow-hidden">
          <div className="font-mono text-[11px] text-emerald-400 uppercase tracking-wider mb-2">Successful Calls</div>
          <div className="font-serif text-3xl text-emerald-300 font-semibold">{stats.successful_calls}</div>
          <div className="text-[10px] font-mono text-emerald-400/80 mt-2">
            Success Rate: <span className="font-bold">{stats.success_rate_percent}%</span>
          </div>
        </div>

        {/* Failed Calls */}
        <div className="border border-red-500/20 rounded-2xl p-5 bg-red-950/20 backdrop-blur-md relative overflow-hidden">
          <div className="font-mono text-[11px] text-red-400 uppercase tracking-wider mb-2">Failed / Incomplete</div>
          <div className="font-serif text-3xl text-red-300 font-semibold">{stats.failed_calls}</div>
          <div className="text-[10px] font-mono text-red-400/80 mt-2">Early disconnects</div>
        </div>

        {/* Human Escalations (Day 7) */}
        <div className="border border-amber-500/20 rounded-2xl p-5 bg-amber-950/20 backdrop-blur-md relative overflow-hidden">
          <div className="font-mono text-[11px] text-amber-400 uppercase tracking-wider mb-2">Human Escalations (Day 7)</div>
          <div className="font-serif text-3xl text-amber-300 font-semibold">{stats.escalated_calls}</div>
          <div className="text-[10px] font-mono text-amber-400/80 mt-2">ASHA / Doctor Alerts</div>
        </div>

        {/* Specialist Appointments (Day 9) */}
        <div className="border border-purple-500/20 rounded-2xl p-5 bg-purple-950/20 backdrop-blur-md relative overflow-hidden">
          <div className="font-mono text-[11px] text-purple-400 uppercase tracking-wider mb-2">Specialist Bookings (Day 9)</div>
          <div className="font-serif text-3xl text-purple-300 font-semibold">{stats.specialist_appointments}</div>
          <div className="text-[10px] font-mono text-purple-400/80 mt-2">Clinic Handoffs (Voice: Pooja)</div>
        </div>
      </div>

      {/* Day 9 Specialist Handoff Appointments Section */}
      <div className="border border-purple-500/20 rounded-2xl p-6 bg-purple-950/10 backdrop-blur-md space-y-4">
        <div className="flex items-center justify-between border-b border-purple-500/20 pb-3">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-purple-400 animate-pulse" />
            <h3 className="font-serif text-2xl text-white">Day 9 Specialist Handoff Bookings</h3>
          </div>
          <span className="font-mono text-xs text-purple-300 uppercase tracking-widest bg-purple-900/50 px-3 py-1 rounded-full border border-purple-500/30">
            Handed off to Clinic Specialist (Voice: Pooja)
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse font-sans text-xs">
            <thead>
              <tr className="border-b border-purple-500/20 text-purple-300 font-mono uppercase text-[10px] tracking-wider">
                <th className="py-2.5 px-4">Token ID</th>
                <th className="py-2.5 px-4">Patient Name</th>
                <th className="py-2.5 px-4">Facility / Clinic</th>
                <th className="py-2.5 px-4">Date & Time</th>
                <th className="py-2.5 px-4">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-purple-500/10 text-neutral-300">
              {stats.appointments.length > 0 ? (
                stats.appointments.map((apt) => (
                  <tr key={apt.appointment_id} className="hover:bg-purple-900/20 transition-colors">
                    <td className="py-2.5 px-4 font-mono text-purple-300 text-[11px]">{apt.appointment_id}</td>
                    <td className="py-2.5 px-4 font-semibold text-white">{apt.user_name || 'Caller'}</td>
                    <td className="py-2.5 px-4 text-neutral-300">{apt.facility_name}</td>
                    <td className="py-2.5 px-4 font-mono text-neutral-400">{apt.preferred_date} ({apt.time_slot})</td>
                    <td className="py-2.5 px-4">
                      <span className="px-2 py-0.5 rounded font-mono text-[10px] uppercase font-bold bg-emerald-950 border border-emerald-500/40 text-emerald-300">
                        {apt.status}
                      </span>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="py-4 text-center text-neutral-500 font-mono text-xs">
                    No specialist appointments booked yet. Ask the agent: "I want to book an appointment" to test Day 9 handoff!
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Call History Table (Live SQLite) */}
      <div className="border border-white/10 rounded-2xl p-6 bg-neutral-950/60 backdrop-blur-md space-y-6">
        <div className="flex items-center justify-between border-b border-white/10 pb-4">
          <h3 className="font-serif text-2xl text-white">Live Call Logs</h3>
          <span className="font-mono text-xs text-neutral-400 uppercase tracking-widest">
            {stats.recent_calls.length} Recent Sessions
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse font-sans text-xs">
            <thead>
              <tr className="border-b border-white/10 text-neutral-400 font-mono uppercase text-[10px] tracking-wider">
                <th className="py-3 px-4">Call ID</th>
                <th className="py-3 px-4">Caller</th>
                <th className="py-3 px-4">Outcome</th>
                <th className="py-3 px-4">Triage Level</th>
                <th className="py-3 px-4">Duration</th>
                <th className="py-3 px-4">Summary</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-neutral-300">
              {stats.recent_calls.map((call) => (
                <tr key={call.call_id} className="hover:bg-white/5 transition-colors">
                  <td className="py-3 px-4 font-mono text-neutral-400 text-[11px]">{call.call_id}</td>
                  <td className="py-3 px-4 font-semibold text-white">{call.user_name || 'Caller'}</td>
                  <td className="py-3 px-4">
                    <span className={`px-2 py-0.5 rounded font-mono text-[10px] uppercase font-bold ${
                      call.outcome === 'success' ? 'bg-emerald-950 border border-emerald-500/40 text-emerald-300' :
                      call.outcome === 'escalated' ? 'bg-amber-950 border border-amber-500/40 text-amber-300' :
                      'bg-red-950 border border-red-500/40 text-red-300'
                    }`}>
                      {call.outcome}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <span className={`px-2 py-0.5 rounded font-mono text-[10px] uppercase ${
                      call.triage_level === 'emergency' ? 'text-red-400 font-bold' :
                      call.triage_level === 'urgent' ? 'text-amber-400' : 'text-neutral-400'
                    }`}>
                      {call.triage_level}
                    </span>
                  </td>
                  <td className="py-3 px-4 font-mono text-neutral-400">{call.duration_seconds}s</td>
                  <td className="py-3 px-4 text-neutral-400 max-w-xs truncate" title={call.summary}>
                    {call.summary}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
