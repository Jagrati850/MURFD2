'use client';

import React from 'react';

interface HeaderProps {
  isConnected: boolean;
  onStartCall: () => void;
  onEndCall: () => void;
  activeView?: 'agent' | 'analytics';
  onViewChange?: (view: 'agent' | 'analytics') => void;
}

export function Header({
  isConnected,
  onStartCall,
  onEndCall,
  activeView = 'agent',
  onViewChange,
}: HeaderProps) {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 backdrop-blur-md bg-black/70 border-b border-white/10 px-6 py-4 transition-all">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Brand Logo & Name */}
        <div className="flex items-center gap-3 cursor-pointer" onClick={() => onViewChange?.('agent')}>
          <div className="w-8 h-8 rounded border border-white/20 flex items-center justify-center bg-white/5 relative overflow-hidden">
            <div className="absolute inset-0 border border-white/10 rotate-45 scale-75" />
            <span className="font-mono text-xs font-bold text-white">H</span>
          </div>
          <span className="font-serif text-lg font-medium tracking-tight text-white">
            Health Access <span className="text-neutral-400 font-normal">.ai</span>
          </span>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex items-center gap-2 font-mono text-xs text-neutral-400 uppercase tracking-widest bg-white/5 border border-white/10 p-1 rounded-xl">
          <button
            onClick={() => onViewChange?.('agent')}
            className={`px-4 py-1.5 rounded-lg transition-all ${
              activeView === 'agent' ? 'bg-white text-black font-semibold' : 'hover:text-white'
            }`}
          >
            Voice Agent
          </button>
          <button
            onClick={() => onViewChange?.('analytics')}
            className={`px-4 py-1.5 rounded-lg transition-all flex items-center gap-1.5 ${
              activeView === 'analytics' ? 'bg-white text-black font-semibold' : 'hover:text-white'
            }`}
          >
            <span>Analytics Dashboard</span>
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
          </button>
        </nav>

        {/* CTA Button */}
        <div>
          {isConnected ? (
            <button
              onClick={onEndCall}
              className="px-5 py-2 rounded-full border border-red-500/40 bg-red-950/40 hover:bg-red-900/60 text-red-200 font-serif italic text-sm transition-all shadow-lg hover:scale-105 active:scale-95 flex items-center gap-2"
            >
              <span className="w-2 h-2 rounded-full bg-red-400 animate-pulse" />
              Disconnect Call
            </button>
          ) : (
            <button
              onClick={onStartCall}
              className="px-5 py-2 rounded-full border border-white/20 bg-white/5 hover:bg-white/10 hover:border-white/40 text-white font-serif italic text-sm transition-all shadow-lg hover:scale-105 active:scale-95 flex items-center gap-2"
            >
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              Start Voice Call
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
