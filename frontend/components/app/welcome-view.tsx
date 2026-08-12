'use client';

import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Button } from '@/components/ui/button';

/* ── Mic permission error banner ────────────────────────────────── */
function MicPermissionError() {
  return (
    <motion.div
      initial={{ opacity: 0, y: -12 }}
      animate={{ opacity: 1, y: 0 }}
      className="mb-6 w-full max-w-sm rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-left"
    >
      <div className="flex items-start gap-3">
        {/* Mic blocked icon */}
        <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-destructive/20">
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="text-destructive"
          >
            <line x1="2" y1="2" x2="22" y2="22" />
            <path d="M18.89 13.23A7.12 7.12 0 0 0 19 12v-2M5 10v2a7 7 0 0 0 12 4.93" />
            <path d="M15 9.34V5a3 3 0 0 0-5.68-1.33" />
            <path d="M9 9v3a3 3 0 0 0 5.12 2.12" />
            <line x1="12" y1="19" x2="12" y2="22" />
            <line x1="8" y1="22" x2="16" y2="22" />
          </svg>
        </div>
        <div>
          <p className="text-sm font-semibold text-destructive">Microphone Access Blocked</p>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">
            Please allow microphone access in your browser settings and reload the page to use the
            voice assistant.
          </p>
          <button
            onClick={() => window.location.reload()}
            className="mt-2 text-xs font-medium text-primary underline underline-offset-2 hover:no-underline"
          >
            Reload page →
          </button>
        </div>
      </div>
    </motion.div>
  );
}

/* ── Hero Icon — animated headset ──────────────────────────────── */
function HeroIcon() {
  return (
    <div className="relative mb-8 flex items-center justify-center">
      {/* Outer slow-spin ring */}
      <div className="absolute h-36 w-36 rounded-full border border-primary/15 animate-spin-slow" />
      {/* Middle pulse ring */}
      <div className="absolute h-28 w-28 rounded-full border border-primary/25" />
      {/* Inner glowing circle */}
      <div className="relative flex h-20 w-20 items-center justify-center rounded-full bg-gradient-to-br from-primary/90 to-primary shadow-[0_0_40px_rgba(99,102,241,0.4)] animate-float">
        <svg
          width="36"
          height="36"
          viewBox="0 0 24 24"
          fill="none"
          stroke="white"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M3 18v-6a9 9 0 0 1 18 0v6" />
          <path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z" />
        </svg>
      </div>
    </div>
  );
}

/* ── Feature chips ──────────────────────────────────────────────── */
function FeatureChips() {
  const chips = [
    { icon: '🇮🇳', label: 'Hindi & English' },
    { icon: '⚡', label: 'Murf Falcon TTS' },
    { icon: '🕐', label: '24/7 Available' },
  ];
  return (
    <div className="mt-6 flex flex-wrap justify-center gap-2">
      {chips.map((chip) => (
        <span
          key={chip.label}
          className="inline-flex items-center gap-1.5 rounded-full border border-border bg-secondary/60 px-3 py-1 text-xs font-medium text-secondary-foreground backdrop-blur-sm"
        >
          <span>{chip.icon}</span>
          {chip.label}
        </span>
      ))}
    </div>
  );
}

interface WelcomeViewProps {
  startButtonText: string;
  onStartCall: () => void;
}

export const WelcomeView = ({
  startButtonText,
  onStartCall,
  ref,
}: React.ComponentProps<'div'> & WelcomeViewProps) => {
  const [micBlocked, setMicBlocked] = useState(false);

  // Detect mic permission state
  useEffect(() => {
    if (!navigator?.permissions) return;
    navigator.permissions
      .query({ name: 'microphone' as PermissionName })
      .then((result) => {
        if (result.state === 'denied') setMicBlocked(true);
        result.onchange = () => {
          setMicBlocked(result.state === 'denied');
        };
      })
      .catch(() => {});
  }, []);

  const handleStart = async () => {
    // Request mic to surface the browser permission prompt early
    try {
      await navigator.mediaDevices.getUserMedia({ audio: true });
      setMicBlocked(false);
    } catch {
      setMicBlocked(true);
      return;
    }
    onStartCall();
  };

  return (
    <div ref={ref} className="relative">
      <section className="flex flex-col items-center justify-center text-center px-6">
        {/* Mic blocked error */}
        <AnimatePresence>
          {micBlocked && <MicPermissionError key="mic-error" />}
        </AnimatePresence>

        {/* Hero icon */}
        <HeroIcon />

        {/* Headline */}
        <h1 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
          Kisan Mitra — Farm & Field AI
        </h1>

        <p className="mt-3 max-w-xs text-sm leading-6 text-muted-foreground sm:max-w-sm sm:text-base">
          नमस्ते!{' '}
          <span className="text-foreground font-medium">
            Your AI agricultural voice assistant is ready
          </span>
          . Ask about Mandi prices, weather forecasts, or crop health advice.
        </p>

        {/* CTA button */}
        <div className="mt-8 relative">
          {/* Pulse rings behind button */}
          <span className="absolute inset-0 rounded-full animate-ping bg-primary/20 pointer-events-none" />
          <Button
            id="start-call-btn"
            size="lg"
            onClick={handleStart}
            disabled={micBlocked}
            className="relative z-10 min-w-52 rounded-full bg-gradient-to-r from-primary to-indigo-500 px-8 font-semibold tracking-wide text-primary-foreground shadow-[0_4px_30px_rgba(99,102,241,0.4)] transition-all duration-300 hover:shadow-[0_6px_40px_rgba(99,102,241,0.6)] hover:scale-[1.03] active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="mr-2 shrink-0"
            >
              <path d="M12 2a3 3 0 0 1 3 3v7a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              <line x1="12" y1="19" x2="12" y2="22" />
              <line x1="8" y1="22" x2="16" y2="22" />
            </svg>
            {startButtonText}
          </Button>
        </div>

        {/* Feature chips */}
        <FeatureChips />

        {/* Disclaimer */}
        <p className="mt-8 text-xs text-muted-foreground/60">
          Your microphone will be requested when you start the call.
        </p>
      </section>
    </div>
  );
};
