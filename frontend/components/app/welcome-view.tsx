'use client';

import React, { useState } from 'react';
import { DarkOrbVisualizer } from './dark-orb-visualizer';

interface WelcomeViewProps {
  startButtonText: string;
  onStartCall: () => void;
  state?: 'ready' | 'connecting' | 'listening' | 'speaking' | 'ended';
  micError?: string | null;
}

export function WelcomeView({
  startButtonText,
  onStartCall,
  state = 'ready',
  micError = null,
}: WelcomeViewProps) {
  const [personalisation, setPersonalisation] = useState(0.9);
  const [automation, setAutomation] = useState(0.8);

  return (
    <div className="min-h-screen bg-[#070709] text-white selection:bg-white selection:text-black font-sans relative overflow-x-hidden pt-24 pb-16">
      {/* Background subtle grid pattern */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#ffffff05_1px,transparent_1px),linear-gradient(to_bottom,#ffffff05_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)] pointer-events-none" />

      {/* Microphone Permission Error Banner */}
      {micError && (
        <div className="max-w-4xl mx-auto px-6 mb-6">
          <div className="bg-red-950/80 border border-red-500/50 rounded-xl p-4 flex items-center justify-between text-red-200 text-sm shadow-2xl backdrop-blur-md">
            <div className="flex items-center gap-3">
              <span className="text-xl">🎙️</span>
              <div>
                <p className="font-semibold text-red-100">Microphone Permission Blocked</p>
                <p className="text-xs text-red-300/90">{micError}</p>
              </div>
            </div>
            <button
              onClick={() => window.location.reload()}
              className="px-3 py-1.5 rounded-lg bg-red-800/60 hover:bg-red-700/80 text-white font-mono text-xs transition-colors"
            >
              Retry
            </button>
          </div>
        </div>
      )}

      {/* Hero Section */}
      <section className="max-w-7xl mx-auto px-6 grid grid-cols-1 lg:grid-cols-12 gap-12 items-center min-h-[75vh]">
        {/* Left Column: Hero Content */}
        <div className="lg:col-span-6 space-y-8 text-left relative z-10">
          {/* Category Tag */}
          <div className="inline-flex items-center gap-3 font-mono text-xs text-amber-500/90 uppercase tracking-widest">
            <span className="w-6 h-[1px] bg-amber-500/80" />
            <span>AGENTIC VOICE AI — HEALTH ACCESS</span>
          </div>

          {/* Main Headline */}
          <h1 className="font-serif text-5xl sm:text-6xl md:text-7xl font-normal tracking-tight leading-[1.05] text-white">
            Agentic AI for <br />
            <span className="italic font-serif text-neutral-300">Autonomous Health</span>
          </h1>

          {/* Subtitle */}
          <p className="text-neutral-400 text-base md:text-lg max-w-xl font-normal leading-relaxed">
            Health Access Assistant orchestrates and personalises every patient interaction — 
            from symptom triage to health guidance — in Indian languages, remembering your health history across calls.
          </p>

          {/* Call Action & Status Badge */}
          <div className="flex flex-wrap items-center gap-5 pt-2">
            <button
              onClick={onStartCall}
              disabled={state === 'connecting'}
              className="px-8 py-4 rounded-xl bg-white text-black font-mono text-xs font-bold tracking-wider uppercase transition-all shadow-xl hover:bg-neutral-200 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-3 group"
            >
              <span>{state === 'connecting' ? 'CONNECTING...' : startButtonText.toUpperCase()}</span>
              <span className="group-hover:translate-x-1 transition-transform">→</span>
            </button>

            <div className="inline-flex items-center gap-2 font-mono text-xs text-neutral-400 border border-white/10 rounded-xl px-4 py-3 bg-white/5 backdrop-blur-sm">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="italic font-serif text-white">PILOT LIVE — VOICE FOR BHARAT</span>
            </div>
          </div>

          {/* 5 Agent States Banner (Day 3 Requirement) */}
          <div className="pt-4 border-t border-white/10 flex flex-wrap items-center gap-3 font-mono text-[11px] text-neutral-400 uppercase tracking-wider">
            <span className="text-neutral-500">Agent State:</span>
            <span className={`px-2.5 py-1 rounded-md border font-semibold ${
              state === 'speaking' ? 'bg-emerald-950/60 border-emerald-500/40 text-emerald-300' :
              state === 'listening' ? 'bg-sky-950/60 border-sky-500/40 text-sky-300' :
              state === 'connecting' ? 'bg-amber-950/60 border-amber-500/40 text-amber-300' :
              state === 'ended' ? 'bg-red-950/60 border-red-500/40 text-red-300' :
              'bg-neutral-900 border-white/10 text-neutral-300'
            }`}>
              {state === 'ready' && 'READY (CLICK TO START)'}
              {state === 'connecting' && 'CONNECTING TO LIVEKIT...'}
              {state === 'listening' && 'LISTENING TO YOU...'}
              {state === 'speaking' && 'AGENT IS SPEAKING...'}
              {state === 'ended' && 'CALL ENDED (CLICK TO RE-CONNECT)'}
            </span>
          </div>

          {/* Sector metadata */}
          <div className="space-y-1 font-mono text-[10px] text-neutral-500 uppercase tracking-widest pt-4">
            <p>SECTOR: HEALTHCARE TECH</p>
            <p>TRACK: HEALTH ACCESS #VOICEFORBHARAT</p>
          </div>
        </div>

        {/* Right Column: Interactive 3D Dark Orb Visualizer */}
        <div className="lg:col-span-6 relative flex justify-center">
          <DarkOrbVisualizer
            state={state}
            personalisation={personalisation}
            automation={automation}
          />
        </div>
      </section>

      {/* Social Proof / Technology Stack Bar */}
      <section className="max-w-7xl mx-auto px-6 my-20 border-y border-white/10 py-8">
        <p className="font-mono text-[10px] text-neutral-500 uppercase tracking-widest mb-6 text-center">
          POWERED BY WORLD-CLASS VOICE & AI INFRASTRUCTURE
        </p>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-8 items-center justify-items-center opacity-75 grayscale hover:grayscale-0 transition-all font-mono text-xs text-neutral-300 tracking-wider">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-indigo-500" />
            <span>MURF FALCON TTS</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span>DEEPGRAM NOVA-3</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-cyan-500" />
            <span>GOOGLE GEMINI</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-amber-500" />
            <span>LIVEKIT CLOUD</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-purple-500" />
            <span>SQLITE MEMORY</span>
          </div>
        </div>
      </section>

      {/* "The Shift" Comparison Section (Replica of dark-orb.aura.build) */}
      <section id="triage" className="max-w-7xl mx-auto px-6 my-24 text-left">
        <div className="mb-12">
          <span className="font-mono text-xs text-amber-500 uppercase tracking-widest">THE SHIFT</span>
          <h2 className="font-serif text-3xl md:text-5xl text-white font-normal mt-2">
            From Fragmented Triage to Autonomous Health Guidance
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Today's Reality */}
          <div className="border border-white/10 rounded-2xl p-8 bg-neutral-950/40 backdrop-blur-sm space-y-6">
            <div className="flex items-center justify-between border-b border-white/10 pb-4">
              <h3 className="font-mono text-sm text-neutral-400 uppercase tracking-wider">Today&apos;s Reality</h3>
              <span className="text-red-400 font-mono text-xs">FRAGMENTED</span>
            </div>
            <ul className="space-y-4 text-neutral-400 text-sm font-normal">
              <li className="flex items-start gap-3">
                <span className="text-red-400 font-bold">✕</span>
                <span>Long wait times at rural clinics and primary care centres.</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="text-red-400 font-bold">✕</span>
                <span>Language barriers prevent effective symptom explanation.</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="text-red-400 font-bold">✕</span>
                <span>No memory of previous consultations or care history.</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="text-red-400 font-bold">✕</span>
                <span>Delayed emergency response when critical symptoms occur.</span>
              </li>
            </ul>
          </div>

          {/* The Health Access Layer */}
          <div className="border border-white/20 rounded-2xl p-8 bg-gradient-to-br from-neutral-900/80 to-black/90 backdrop-blur-sm space-y-6 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/10 rounded-full blur-3xl" />
            <div className="flex items-center justify-between border-b border-white/10 pb-4">
              <h3 className="font-mono text-sm text-white uppercase tracking-wider">The Health Access Layer</h3>
              <span className="text-emerald-400 font-mono text-xs">AUTONOMOUS</span>
            </div>
            <ul className="space-y-4 text-neutral-200 text-sm font-normal">
              <li className="flex items-start gap-3">
                <span className="text-emerald-400 font-bold">✓</span>
                <span>Instant ~100ms voice response via Murf Falcon & Deepgram.</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="text-emerald-400 font-bold">✓</span>
                <span>Native Devanagari Hindi & regional language auto-mirroring.</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="text-emerald-400 font-bold">✓</span>
                <span>Persistent SQLite memory remembers name, symptoms & goals.</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="text-emerald-400 font-bold">✓</span>
                <span>Immediate emergency escalation for chest pain & breathing issues.</span>
              </li>
            </ul>
          </div>
        </div>
      </section>

      {/* Platform Pillars Section */}
      <section id="pillars" className="max-w-7xl mx-auto px-6 my-24 text-left">
        <div className="mb-12">
          <span className="font-mono text-xs text-amber-500 uppercase tracking-widest">CORE CAPABILITIES</span>
          <h2 className="font-serif text-3xl md:text-5xl text-white font-normal mt-2">
            Five Pillars of Agentic Health Access
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="border border-white/10 rounded-xl p-6 bg-neutral-950/40 hover:border-white/20 transition-all">
            <span className="font-mono text-xs text-neutral-500">01</span>
            <h4 className="font-serif text-xl text-white mt-3 mb-2">Symptom Triage</h4>
            <p className="text-neutral-400 text-xs leading-relaxed">
              Gently gathers symptom descriptions and offers safe general guidance without diagnosing.
            </p>
          </div>

          <div className="border border-white/10 rounded-xl p-6 bg-neutral-950/40 hover:border-white/20 transition-all">
            <span className="font-mono text-xs text-neutral-500">02</span>
            <h4 className="font-serif text-xl text-white mt-3 mb-2">Native Script Mirror</h4>
            <p className="text-neutral-400 text-xs leading-relaxed">
              Automatically speaks and transcribes in native scripts (Devanagari Hindi, Tamil, etc.).
            </p>
          </div>

          <div className="border border-white/10 rounded-xl p-6 bg-neutral-950/40 hover:border-white/20 transition-all">
            <span className="font-mono text-xs text-neutral-500">03</span>
            <h4 className="font-serif text-xl text-white mt-3 mb-2">Persistent Memory</h4>
            <p className="text-neutral-400 text-xs leading-relaxed">
              Stores preferred name, symptoms, and health goals across sessions using consent-based SQLite.
            </p>
          </div>

          <div className="border border-white/10 rounded-xl p-6 bg-neutral-950/40 hover:border-white/20 transition-all">
            <span className="font-mono text-xs text-neutral-500">04</span>
            <h4 className="font-serif text-xl text-white mt-3 mb-2">Emergency Escalation</h4>
            <p className="text-neutral-400 text-xs leading-relaxed">
              Instantly detects critical symptoms like chest pain and directs users to emergency services (112).
            </p>
          </div>

          <div className="border border-white/10 rounded-xl p-6 bg-neutral-950/40 hover:border-white/20 transition-all">
            <span className="font-mono text-xs text-neutral-500">05</span>
            <h4 className="font-serif text-xl text-white mt-3 mb-2">ASHA Helper Support</h4>
            <p className="text-neutral-400 text-xs leading-relaxed">
              Empowers community healthcare workers with automated patient lookup and context tracking.
            </p>
          </div>

          <div className="border border-white/10 rounded-xl p-6 bg-neutral-950/40 hover:border-white/20 transition-all">
            <span className="font-mono text-xs text-neutral-500">06</span>
            <h4 className="font-serif text-xl text-white mt-3 mb-2">Consent Protection</h4>
            <p className="text-neutral-400 text-xs leading-relaxed">
              Strict consent protocol ensures memory is saved only when the user explicitly agrees.
            </p>
          </div>
        </div>
      </section>

      {/* Footer (Replica of dark-orb.aura.build footer) */}
      <footer className="max-w-7xl mx-auto px-6 pt-16 border-t border-white/10 flex flex-col md:flex-row items-center justify-between gap-6 font-mono text-xs text-neutral-500">
        <div>
          <p className="text-white font-serif text-sm font-medium">HEALTH ACCESS AI — AGENTIC CARE INTELLIGENCE</p>
          <p className="text-[10px] text-neutral-500 mt-1">Built for #VoiceForBharat Challenge 2026</p>
        </div>
        <div className="flex items-center gap-6">
          <a href="#triage" className="hover:text-white transition-colors">Triage</a>
          <a href="#pillars" className="hover:text-white transition-colors">Capabilities</a>
          <a href="https://murf.ai" target="_blank" rel="noreferrer" className="hover:text-white transition-colors">Murf Falcon</a>
        </div>
      </footer>
    </div>
  );
}
