'use client';

import React, { useEffect, useState } from 'react';
import { useRoomContext, useTranscription } from '@livekit/components-react';
import { RoomEvent } from 'livekit-client';
import { UserCheck, CalendarCheck, Send, Sparkles, Stethoscope, Clock, MapPin } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

interface SpecialistChatViewProps {
  onEndCall: () => void;
}

interface HandoffInfo {
  agent_name: string;
  voice: string;
  specialist_role: string;
  message: string;
  timestamp: string;
}

interface AppointmentInfo {
  appointment_id: string;
  facility_name: string;
  date: string;
  time_slot: string;
}

export function SpecialistChatView({ onEndCall }: SpecialistChatViewProps) {
  const room = useRoomContext();
  const { segments } = useTranscription();
  const [handoff, setHandoff] = useState<HandoffInfo | null>({
    agent_name: 'Clinic & Appointment Specialist',
    voice: 'Pooja (Murf Falcon)',
    specialist_role: 'Doctor Consultations & PHC Slot Booking',
    message: 'Specialist Agent Active & Listening (Voice: Pooja)',
    timestamp: new Date().toLocaleTimeString(),
  });
  const [appointment, setAppointment] = useState<AppointmentInfo | null>(null);
  const [textInput, setTextInput] = useState('');

  useEffect(() => {
    if (!room) return;

    const onData = (payload: Uint8Array, _p: unknown, _k: unknown, topic?: string) => {
      if (topic !== 'health_data') return;
      try {
        const msg = JSON.parse(new TextDecoder().decode(payload));
        if (msg?.kind === 'handoff') {
          setHandoff({
            agent_name: msg.payload.agent_name || 'Clinic & Appointment Specialist',
            voice: msg.payload.voice || 'Pooja (Murf Falcon)',
            specialist_role: msg.payload.specialist_role || 'Doctor Consultations & Slot Booking',
            message: msg.payload.message || 'Conversation transferred to Specialist Agent',
            timestamp: new Date().toLocaleTimeString(),
          });
        }
        if (msg?.kind === 'appointment') {
          setAppointment({
            appointment_id: msg.payload.appointment_id,
            facility_name: msg.payload.facility_name,
            date: msg.payload.date,
            time_slot: msg.payload.time_slot,
          });
        }
      } catch (err) {
        console.warn('SpecialistChatView data error:', err);
      }
    };

    room.on(RoomEvent.DataReceived, onData);
    return () => {
      room.off(RoomEvent.DataReceived, onData);
    };
  }, [room]);

  const handleSendText = async (textToSend?: string) => {
    const msgText = textToSend || textInput;
    if (!msgText.trim() || !room) return;

    try {
      const encoder = new TextEncoder();
      await room.local_participant.publishData(
        encoder.encode(JSON.stringify({ text: msgText })),
        { reliable: true, topic: 'lk-chat-topic' }
      );
      setTextInput('');
    } catch (err) {
      console.error('Failed to send text message:', err);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 text-left space-y-6">
      {/* Dedicated Specialist Header Banner */}
      <div className="border border-purple-500/30 rounded-2xl p-6 bg-gradient-to-r from-purple-950/80 via-black to-neutral-950/90 backdrop-blur-xl shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-purple-600/10 rounded-full blur-3xl pointer-events-none" />
        
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 relative z-10">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-2xl bg-purple-500/20 border border-purple-400/40 flex items-center justify-center text-purple-300 shadow-lg">
              <Stethoscope className="w-6 h-6 animate-pulse" />
            </div>
            <div>
              <div className="inline-flex items-center gap-2 font-mono text-[10px] text-purple-400 uppercase tracking-widest mb-0.5">
                <span className="w-2 h-2 rounded-full bg-purple-400 animate-ping" />
                DAY 9 — SEPARATE SPECIALIST CHAT AREA
              </div>
              <h2 className="font-serif text-2xl md:text-3xl text-white font-medium">
                Clinic & Appointment Specialist
              </h2>
              <div className="flex items-center gap-3 text-xs text-neutral-400 mt-1 font-mono">
                <span>Voice: <strong className="text-purple-300 font-bold">Pooja (Murf Falcon)</strong></span>
                <span>•</span>
                <span className="text-emerald-400 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  Active Handoff Session
                </span>
              </div>
            </div>
          </div>

          <button
            onClick={onEndCall}
            className="px-4 py-2 rounded-xl border border-red-500/40 bg-red-950/40 hover:bg-red-900/60 text-red-200 font-mono text-xs transition-all shadow-md flex items-center gap-2"
          >
            <span className="w-2 h-2 rounded-full bg-red-400" />
            End Call
          </button>
        </div>
      </div>

      {/* Confirmed Appointment Notification Banner */}
      <AnimatePresence>
        {appointment && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="border border-emerald-500/40 rounded-xl p-4 bg-emerald-950/40 backdrop-blur-md flex items-center justify-between text-emerald-200 text-xs font-mono shadow-xl"
          >
            <div className="flex items-center gap-3">
              <CalendarCheck className="w-5 h-5 text-emerald-400" />
              <div>
                <p className="font-bold text-white text-sm">{appointment.facility_name}</p>
                <p className="text-emerald-300/80">Date: {appointment.date} at {appointment.time_slot} • Token ID: <span className="text-emerald-400 font-bold">{appointment.appointment_id}</span></p>
              </div>
            </div>
            <span className="px-2.5 py-1 rounded bg-emerald-900/60 border border-emerald-400/40 text-emerald-300 font-bold uppercase text-[10px]">
              CONFIRMED
            </span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Quick Action Chips for Specialist */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-[10px] text-neutral-500 uppercase tracking-widest mr-1">Quick Prompts:</span>
        <button
          onClick={() => handleSendText("Book an appointment for tomorrow at 10 AM")}
          className="px-3 py-1.5 rounded-lg border border-purple-500/30 bg-purple-950/30 hover:bg-purple-900/50 text-purple-200 text-xs font-mono transition-all flex items-center gap-1.5"
        >
          <Sparkles className="w-3 h-3 text-purple-400" />
          <span>"Book appointment tomorrow 10 AM"</span>
        </button>
        <button
          onClick={() => handleSendText("Check available doctor slots")}
          className="px-3 py-1.5 rounded-lg border border-white/10 bg-white/5 hover:bg-white/10 text-neutral-300 text-xs font-mono transition-all flex items-center gap-1.5"
        >
          <Clock className="w-3 h-3 text-amber-400" />
          <span>"Check doctor slots"</span>
        </button>
        <button
          onClick={() => handleSendText("Find nearest Primary Health Centre")}
          className="px-3 py-1.5 rounded-lg border border-white/10 bg-white/5 hover:bg-white/10 text-neutral-300 text-xs font-mono transition-all flex items-center gap-1.5"
        >
          <MapPin className="w-3 h-3 text-sky-400" />
          <span>"Find nearby PHC"</span>
        </button>
      </div>

      {/* Dedicated Specialist Live Chat Feed */}
      <div className="border border-white/10 rounded-2xl p-6 bg-neutral-950/80 backdrop-blur-md space-y-4 min-h-[350px] max-h-[500px] overflow-y-auto flex flex-col justify-between">
        <div className="space-y-4">
          {/* Handoff Status Announcement */}
          <div className="flex justify-center">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-purple-500/30 bg-purple-950/50 text-purple-300 text-xs font-mono shadow-md">
              <UserCheck className="w-3.5 h-3.5" />
              <span>Transferred to Specialist Agent Pooja (Murf Falcon)</span>
            </div>
          </div>

          {/* Transcript Feed */}
          {segments.length > 0 ? (
            segments.map((segment) => (
              <div
                key={segment.id}
                className={`flex gap-3 text-xs ${
                  segment.isFinal ? 'opacity-100' : 'opacity-75 animate-pulse'
                }`}
              >
                <div
                  className={`w-7 h-7 rounded-lg flex items-center justify-center font-mono text-[10px] font-bold shrink-0 ${
                    segment.participant?.isAgent
                      ? 'bg-purple-900/60 border border-purple-500/40 text-purple-300'
                      : 'bg-white/10 border border-white/20 text-white'
                  }`}
                >
                  {segment.participant?.isAgent ? 'Pooja' : 'You'}
                </div>
                <div className="space-y-0.5 max-w-xl">
                  <div className="flex items-center gap-2 font-mono text-[10px] text-neutral-400">
                    <span className="font-semibold text-white">
                      {segment.participant?.isAgent ? 'Clinic Specialist (Pooja)' : 'You'}
                    </span>
                    <span>•</span>
                    <span>{new Date(segment.firstReceivedTime).toLocaleTimeString()}</span>
                  </div>
                  <p className="text-neutral-200 leading-relaxed font-sans text-sm">
                    {segment.text}
                  </p>
                </div>
              </div>
            ))
          ) : (
            <div className="py-12 text-center text-neutral-500 font-mono text-xs space-y-2">
              <Stethoscope className="w-8 h-8 text-neutral-600 mx-auto animate-bounce" />
              <p>Specialist Agent Pooja is listening in native script...</p>
              <p className="text-[10px] text-neutral-600">Speak or use the quick prompt buttons below to book your clinic slot.</p>
            </div>
          )}
        </div>

        {/* Text Input Bar for Specialist Chat */}
        <div className="pt-4 border-t border-white/10 flex items-center gap-3">
          <input
            type="text"
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSendText()}
            placeholder="Type a message to Specialist Agent Pooja..."
            className="flex-1 px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-xs placeholder:text-neutral-500 focus:outline-none focus:border-purple-500 font-sans"
          />
          <button
            onClick={() => handleSendText()}
            className="px-4 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-mono text-xs font-bold transition-all shadow-lg flex items-center gap-2 shrink-0"
          >
            <span>Send</span>
            <Send className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
