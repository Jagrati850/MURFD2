'use client';

import React, { useEffect, useRef, useState } from 'react';

interface DarkOrbVisualizerProps {
  state: 'ready' | 'connecting' | 'listening' | 'speaking' | 'ended';
  volume?: number; // 0.0 to 1.0
  personalisation?: number;
  automation?: number;
}

interface Point3D {
  x: number;
  y: number;
  z: number;
  baseX: number;
  baseY: number;
  baseZ: number;
  size: number;
  alpha: number;
}

export function DarkOrbVisualizer({
  state,
  volume = 0,
  personalisation = 0.9,
  automation = 0.8,
}: DarkOrbVisualizerProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const pointsRef = useRef<Point3D[]>([]);

  // Sliders state
  const [persVal, setPersVal] = useState(personalisation);
  const [autoVal, setAutoVal] = useState(automation);

  // Generate 2800 Fibonacci sphere points for hyper-dense particle mesh
  useEffect(() => {
    const numPoints = 2800;
    const radius = 190;
    const goldenRatio = (1 + Math.sqrt(5)) / 2;
    const points: Point3D[] = [];

    for (let i = 0; i < numPoints; i++) {
      const theta = (2 * Math.PI * i) / goldenRatio;
      const phi = Math.acos(1 - (2 * (i + 0.5)) / numPoints);

      const x = radius * Math.sin(phi) * Math.cos(theta);
      const y = radius * Math.sin(phi) * Math.sin(theta);
      const z = radius * Math.cos(phi);

      points.push({
        x,
        y,
        z,
        baseX: x,
        baseY: y,
        baseZ: z,
        size: Math.random() * 1.4 + 0.6,
        alpha: Math.random() * 0.75 + 0.25,
      });
    }

    pointsRef.current = points;
  }, []);

  // Main 60fps render loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let time = 0;
    let rotX = 0.2;
    let rotY = 0;

    const render = () => {
      time += 0.02;

      // Handle HDPI / Retina display scaling
      const rect = canvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      if (canvas.width !== rect.width * dpr || canvas.height !== rect.height * dpr) {
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
      }

      ctx.save();
      ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, rect.width, rect.height);

      const centerX = rect.width / 2;
      const centerY = rect.height / 2;

      // Rotation & wave speeds based on state
      let speedY = 0.003;
      let waveFreq = 4.0;
      let waveAmp = 18 * autoVal;
      let volAmp = volume * 50;

      if (state === 'connecting') {
        speedY = 0.012;
        waveAmp = 25;
      } else if (state === 'listening') {
        speedY = 0.006;
        waveAmp = 22 + volume * 40;
      } else if (state === 'speaking') {
        speedY = 0.01;
        waveFreq = 6.0;
        waveAmp = 30 + Math.sin(time * 10) * 15;
        volAmp = 60;
      } else if (state === 'ended') {
        speedY = 0.001;
        waveAmp = 5;
      }

      rotY += speedY;
      rotX += 0.001;

      const cosY = Math.cos(rotY);
      const sinY = Math.sin(rotY);
      const cosX = Math.cos(rotX);
      const sinX = Math.sin(rotX);

      // Draw background ambient dark radial glow
      const bgGlow = ctx.createRadialGradient(
        centerX,
        centerY,
        30,
        centerX,
        centerY,
        260
      );
      if (state === 'speaking') {
        bgGlow.addColorStop(0, 'rgba(255, 255, 255, 0.12)');
        bgGlow.addColorStop(0.5, 'rgba(99, 102, 241, 0.06)');
        bgGlow.addColorStop(1, 'rgba(0, 0, 0, 0)');
      } else if (state === 'listening') {
        bgGlow.addColorStop(0, 'rgba(56, 189, 248, 0.12)');
        bgGlow.addColorStop(0.5, 'rgba(14, 165, 233, 0.04)');
        bgGlow.addColorStop(1, 'rgba(0, 0, 0, 0)');
      } else {
        bgGlow.addColorStop(0, 'rgba(255, 255, 255, 0.06)');
        bgGlow.addColorStop(0.6, 'rgba(255, 255, 255, 0.01)');
        bgGlow.addColorStop(1, 'rgba(0, 0, 0, 0)');
      }

      ctx.fillStyle = bgGlow;
      ctx.beginPath();
      ctx.arc(centerX, centerY, 260, 0, Math.PI * 2);
      ctx.fill();

      // Render 2 Thin Outer Copper/Gold Wireframe Loops (Exact match from dark-orb.aura.build)
      ctx.lineWidth = 0.8;

      // Outer Loop 1 (Tilted Thin Copper Ring)
      ctx.strokeStyle = 'rgba(180, 100, 50, 0.25)';
      ctx.beginPath();
      ctx.ellipse(centerX, centerY, 230 + Math.sin(time * 1.5) * 6, 210 + Math.cos(time * 1.5) * 6, Math.PI / 6, 0, Math.PI * 2);
      ctx.stroke();

      // Outer Loop 2 (Thin Neutral Ring)
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
      ctx.beginPath();
      ctx.ellipse(centerX, centerY, 215, 235, -Math.PI / 4, 0, Math.PI * 2);
      ctx.stroke();

      // Project & Render 3D Point Cloud Mesh with "Giggly" Organic Noise Waves
      const points = pointsRef.current;
      const projected: { x: number; y: number; z: number; size: number; alpha: number }[] = [];

      for (let i = 0; i < points.length; i++) {
        const pt = points[i];

        // Multi-frequency 3D Organic Wave Wobble Displacement
        const noise =
          Math.sin(time * waveFreq + pt.baseX * 0.025 + pt.baseY * 0.02) *
          Math.cos(time * 2.5 + pt.baseZ * 0.025) *
          waveAmp *
          persVal;

        const radMult = 1 + (noise + volAmp) / 200;

        const bx = pt.baseX * radMult;
        const by = pt.baseY * radMult;
        const bz = pt.baseZ * radMult;

        // 3D Y-Axis Rotation
        const x1 = bx * cosY - bz * sinY;
        const z1 = bz * cosY + bx * sinY;

        // 3D X-Axis Rotation
        const y2 = by * cosX - z1 * sinX;
        const z2 = z1 * cosX + by * sinX;

        // Perspective Projection Formula
        const fov = 450;
        const scale = fov / (fov + z2);
        const px = centerX + x1 * scale;
        const py = centerY + y2 * scale;

        projected.push({
          x: px,
          y: py,
          z: z2,
          size: pt.size * scale,
          alpha: pt.alpha * Math.max(0.12, (z2 + 220) / 440),
        });
      }

      // Sort points back-to-front for proper depth blending
      projected.sort((a, b) => a.z - b.z);

      // Draw particle points
      for (let i = 0; i < projected.length; i++) {
        const p = projected[i];

        ctx.beginPath();
        ctx.arc(p.x, p.y, Math.max(0.4, p.size), 0, Math.PI * 2);

        if (state === 'speaking') {
          ctx.fillStyle = `rgba(255, 255, 255, ${p.alpha})`;
        } else if (state === 'listening') {
          ctx.fillStyle = `rgba(224, 242, 254, ${p.alpha * 0.95})`;
        } else if (state === 'connecting') {
          ctx.fillStyle = `rgba(199, 210, 254, ${p.alpha * 0.85})`;
        } else {
          ctx.fillStyle = `rgba(240, 240, 245, ${p.alpha * 0.75})`;
        }

        ctx.fill();
      }

      ctx.restore();
      animationFrameRef.current = requestAnimationFrame(render);
    };

    render();

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [state, volume, persVal, autoVal]);

  return (
    <div className="relative w-full aspect-square max-w-[560px] mx-auto flex items-center justify-center">
      {/* 3D Particle Cloud Canvas */}
      <canvas ref={canvasRef} className="w-full h-full object-contain" />

      {/* Floating Glassmorphic Control Engine Card (Exact match of dark-orb.aura.build) */}
      <div className="absolute bottom-2 right-0 md:-right-4 w-[290px] backdrop-blur-2xl bg-[#0c0c0e]/90 border border-white/10 rounded-xl p-5 shadow-[0_20px_50px_rgba(0,0,0,0.8)] text-left select-none z-20 transition-all hover:border-white/20">
        <h4 className="font-serif italic text-base text-white/95 mb-4 border-b border-white/10 pb-2.5 flex items-center justify-between">
          <span>Health Experience Engine</span>
        </h4>

        {/* PERSONALISATION Slider */}
        <div className="space-y-1.5 mb-4">
          <div className="flex justify-between items-center text-[10px] font-mono text-neutral-400 uppercase tracking-widest">
            <span>Personalisation</span>
            <span className="text-white font-mono">{persVal.toFixed(1)}</span>
          </div>
          <input
            type="range"
            min="0.2"
            max="1.8"
            step="0.1"
            value={persVal}
            onChange={(e) => setPersVal(parseFloat(e.target.value))}
            className="w-full h-1 bg-neutral-800 rounded-lg appearance-none cursor-pointer accent-white"
          />
        </div>

        {/* AUTOMATION Slider */}
        <div className="space-y-1.5 mb-5">
          <div className="flex justify-between items-center text-[10px] font-mono text-neutral-400 uppercase tracking-widest">
            <span>Automation</span>
            <span className="text-white font-mono">{autoVal.toFixed(1)}</span>
          </div>
          <input
            type="range"
            min="0.2"
            max="1.5"
            step="0.1"
            value={autoVal}
            onChange={(e) => setAutoVal(parseFloat(e.target.value))}
            className="w-full h-1 bg-neutral-800 rounded-lg appearance-none cursor-pointer accent-white"
          />
        </div>

        {/* Progress bars (CHECK-IN & IN-ROOM / TRIAGE & MEMORY) */}
        <div className="grid grid-cols-2 gap-3 mb-5 border-t border-white/10 pt-3 text-[9px] font-mono uppercase tracking-widest text-neutral-400">
          <div>
            <span className="block mb-1">Triage Core</span>
            <div className="w-full h-1 bg-neutral-800 rounded-full overflow-hidden">
              <div className="h-full bg-white rounded-full w-[85%]" />
            </div>
          </div>
          <div>
            <span className="block mb-1">SQLite Memory</span>
            <div className="w-full h-1 bg-neutral-800 rounded-full overflow-hidden">
              <div className="h-full bg-white rounded-full w-[95%]" />
            </div>
          </div>
        </div>

        {/* AI LAYER Status Badge */}
        <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-widest pt-2 border-t border-white/10">
          <span className="text-neutral-400">AI Layer</span>
          <span className="font-semibold text-emerald-400 flex items-center gap-1.5">
            LIVE <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse inline-block" />
          </span>
        </div>
      </div>
    </div>
  );
}
