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

interface AnalyticsData {
  total_calls: number;
  successful_calls: number;
  failed_calls: number;
  escalated_calls: number;
  success_rate_percent: string;
  recent_calls: CallRecord[];
  escalations: EscalationRecord[];
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
    success_rate_percent: '75.0',
    recent_calls: [],
    escalations: [],
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-12 text-left space-y-10">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/10 pb-6">
        <div>
          <div className="inline-flex items-center gap-2 font-mono text-xs text-amber-500 uppercase tracking-widest mb-1">
            <span className="w-2 h-2 rounded-full bg-amber-500 animate-ping" />
            DAY 8 — CALL ANALYTICS DASHBOARD
          </div>
          <h2 className="font-serif text-3xl md:text-5xl text-white font-normal">
            Agent Performance & Triage Metrics
          </h2>
        </div>
        <button
          onClick={fetchAnalytics}
          className="self-start md:self-auto px-4 py-2 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 text-xs font-mono text-neutral-300 transition-all flex items-center gap-2"
        >
          <span>↻ Refresh Live SQLite Data</span>
        </button>
      </div>

      {/* 4 Core Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Total Calls */}
        <div className="border border-white/10 rounded-2xl p-6 bg-neutral-950/60 backdrop-blur-md relative overflow-hidden">
          <div className="font-mono text-xs text-neutral-400 uppercase tracking-wider mb-2">Total Calls</div>
          <div className="font-serif text-4xl text-white font-semibold">{stats.total_calls}</div>
          <div className="text-[10px] font-mono text-neutral-500 mt-2">Recorded in SQLite DB</div>
        </div>

        {/* Successful Calls */}
        <div className="border border-emerald-500/20 rounded-2xl p-6 bg-emerald-950/20 backdrop-blur-md relative overflow-hidden">
          <div className="font-mono text-xs text-emerald-400 uppercase tracking-wider mb-2">Successful Calls</div>
          <div className="font-serif text-4xl text-emerald-300 font-semibold">{stats.successful_calls}</div>
          <div className="text-[10px] font-mono text-emerald-400/80 mt-2">
            Success Rate: <span className="font-bold">{stats.success_rate_percent}%</span>
          </div>
        </div>

        {/* Failed Calls */}
        <div className="border border-red-500/20 rounded-2xl p-6 bg-red-950/20 backdrop-blur-md relative overflow-hidden">
          <div className="font-mono text-xs text-red-400 uppercase tracking-wider mb-2">Failed / Early Disconnects</div>
          <div className="font-serif text-4xl text-red-300 font-semibold">{stats.failed_calls}</div>
          <div className="text-[10px] font-mono text-red-400/80 mt-2">Calls incomplete or unfulfilled</div>
        </div>

        {/* Escalated Calls (Day 7 Integration) */}
        <div className="border border-amber-500/20 rounded-2xl p-6 bg-amber-950/20 backdrop-blur-md relative overflow-hidden">
          <div className="font-mono text-xs text-amber-400 uppercase tracking-wider mb-2">Human Escalations (Day 7)</div>
          <div className="font-serif text-4xl text-amber-300 font-semibold">{stats.escalated_calls}</div>
          <div className="text-[10px] font-mono text-amber-400/80 mt-2">ASHA Worker / Doctor Alerts</div>
        </div>
      </div>

      {/* Analytics Visual Bar */}
      <div className="border border-white/10 rounded-2xl p-6 bg-neutral-950/40 space-y-3">
        <div className="flex justify-between items-center text-xs font-mono text-neutral-400 uppercase tracking-wider">
          <span>Overall Call Completion Ratio</span>
          <span className="text-white font-bold">{stats.success_rate_percent}% Success</span>
        </div>
        <div className="w-full h-3 bg-neutral-800 rounded-full overflow-hidden flex">
          <div
            style={{ width: `${(stats.successful_calls / (stats.total_calls || 1)) * 100}%` }}
            className="h-full bg-emerald-500 transition-all"
            title="Successful Calls"
          />
          <div
            style={{ width: `${(stats.escalated_calls / (stats.total_calls || 1)) * 100}%` }}
            className="h-full bg-amber-500 transition-all"
            title="Human Escalations"
          />
          <div
            style={{ width: `${(stats.failed_calls / (stats.total_calls || 1)) * 100}%` }}
            className="h-full bg-red-500 transition-all"
            title="Failed Calls"
          />
        </div>
        <div className="flex items-center gap-6 font-mono text-[10px] text-neutral-400 pt-1">
          <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-emerald-500" /> Successful</span>
          <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-amber-500" /> Escalated (Day 7)</span>
          <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-red-500" /> Incomplete</span>
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
