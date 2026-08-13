'use client';

import React, { useState } from 'react';
import { useTheme } from 'next-themes';
import { AnimatePresence, motion } from 'motion/react';
import {
  useSessionContext,
  useVoiceAssistant,
  useConnectionState,
} from '@livekit/components-react';
import { ConnectionState } from 'livekit-client';
import type { AppConfig } from '@/app-config';
import { AgentSessionView_01 } from '@/components/agents-ui/blocks/agent-session-view-01';
import { WelcomeView } from '@/components/app/welcome-view';
import { Header } from '@/components/app/header';
import { AnalyticsDashboard } from '@/components/app/analytics-dashboard';

const MotionWelcomeView = motion.create(WelcomeView);
const MotionSessionView = motion.create(AgentSessionView_01);
const MotionAnalyticsView = motion.create(AnalyticsDashboard);

const VIEW_MOTION_PROPS = {
  variants: {
    visible: { opacity: 1 },
    hidden: { opacity: 0 },
  },
  initial: 'hidden',
  animate: 'visible',
  exit: 'hidden',
  transition: { duration: 0.4, ease: 'linear' },
};

interface ViewControllerProps {
  appConfig: AppConfig;
}

export function ViewController({ appConfig }: ViewControllerProps) {
  const { isConnected, start, end } = useSessionContext();
  const connectionState = useConnectionState();
  const voiceAssistant = useVoiceAssistant();
  const { resolvedTheme } = useTheme();

  const [micError, setMicError] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<'agent' | 'analytics'>('agent');
  const [activeCallSubTab, setActiveCallSubTab] = useState<'orb' | 'transcript'>('orb');

  // Determine the 5 Agent States (Day 3)
  const getAgentState = (): 'ready' | 'connecting' | 'listening' | 'speaking' | 'ended' => {
    if (connectionState === ConnectionState.Connecting) {
      return 'connecting';
    }
    if (connectionState === ConnectionState.Disconnected && !isConnected) {
      return 'ready';
    }
    if (isConnected) {
      if (voiceAssistant.state === 'speaking') {
        return 'speaking';
      }
      return 'listening';
    }
    return 'ended';
  };

  const agentState = getAgentState();

  const handleStartCall = async () => {
    setMicError(null);
    setActiveView('agent');
    try {
      if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        await navigator.mediaDevices.getUserMedia({ audio: true });
      }
      await start();
    } catch (err: any) {
      console.error('Microphone error:', err);
      if (err?.name === 'NotAllowedError' || err?.name === 'PermissionDeniedError') {
        setMicError('Microphone access was denied. Please allow microphone access in browser settings.');
      } else if (err?.name === 'NotFoundError' || err?.name === 'DevicesNotFoundError') {
        setMicError('No microphone found. Please connect a microphone and retry.');
      } else {
        setMicError(err?.message || 'Failed to access microphone.');
      }
    }
  };

  return (
    <div className="min-h-screen bg-[#070709] relative">
      {/* Top Header */}
      <Header
        isConnected={isConnected}
        onStartCall={handleStartCall}
        onEndCall={end}
        activeView={activeView}
        onViewChange={setActiveView}
      />

      {/* Main View Area */}
      <div className="pt-20">
        <AnimatePresence mode="wait">
          {/* View 1: Day 8 Call Analytics Dashboard */}
          {activeView === 'analytics' && (
            <MotionAnalyticsView key="analytics-view" {...VIEW_MOTION_PROPS} />
          )}

          {/* View 2: Voice Agent Interface */}
          {activeView === 'agent' && (
            <>
              {!isConnected && (
                <MotionWelcomeView
                  key="welcome"
                  {...VIEW_MOTION_PROPS}
                  startButtonText={appConfig.startButtonText}
                  onStartCall={handleStartCall}
                  state={agentState}
                  micError={micError}
                />
              )}

              {isConnected && (
                <div>
                  {/* View Switcher during active call */}
                  <div className="fixed top-20 right-6 z-40 flex items-center gap-2 bg-black/80 border border-white/10 p-1.5 rounded-xl backdrop-blur-md font-mono text-xs shadow-2xl">
                    <button
                      onClick={() => setActiveCallSubTab('orb')}
                      className={`px-3 py-1.5 rounded-lg transition-all ${
                        activeCallSubTab === 'orb'
                          ? 'bg-white text-black font-semibold'
                          : 'text-neutral-400 hover:text-white'
                      }`}
                    >
                      Dark Orb 3D
                    </button>
                    <button
                      onClick={() => setActiveCallSubTab('transcript')}
                      className={`px-3 py-1.5 rounded-lg transition-all ${
                        activeCallSubTab === 'transcript'
                          ? 'bg-white text-black font-semibold'
                          : 'text-neutral-400 hover:text-white'
                      }`}
                    >
                      Live Transcript
                    </button>
                  </div>

                  {activeCallSubTab === 'orb' && (
                    <MotionWelcomeView
                      key="session-orb"
                      {...VIEW_MOTION_PROPS}
                      startButtonText="Disconnect Call"
                      onStartCall={end}
                      state={agentState}
                      micError={micError}
                    />
                  )}

                  {activeCallSubTab === 'transcript' && (
                    <MotionSessionView
                      key="session-view"
                      {...VIEW_MOTION_PROPS}
                      supportsChatInput={appConfig.supportsChatInput}
                      supportsVideoInput={appConfig.supportsVideoInput}
                      supportsScreenShare={appConfig.supportsScreenShare}
                      isPreConnectBufferEnabled={appConfig.isPreConnectBufferEnabled}
                      audioVisualizerType={appConfig.audioVisualizerType}
                      audioVisualizerColor={
                        resolvedTheme === 'dark'
                          ? appConfig.audioVisualizerColorDark
                          : appConfig.audioVisualizerColor
                      }
                      audioVisualizerColorShift={appConfig.audioVisualizerColorShift}
                      audioVisualizerBarCount={appConfig.audioVisualizerBarCount}
                      audioVisualizerGridRowCount={appConfig.audioVisualizerGridRowCount}
                      audioVisualizerGridColumnCount={appConfig.audioVisualizerGridColumnCount}
                      audioVisualizerRadialBarCount={appConfig.audioVisualizerRadialBarCount}
                      audioVisualizerRadialRadius={appConfig.audioVisualizerRadialRadius}
                      audioVisualizerWaveLineWidth={appConfig.audioVisualizerWaveLineWidth}
                      className="fixed inset-0 pt-20"
                    />
                  )}
                </div>
              )}
            </>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
