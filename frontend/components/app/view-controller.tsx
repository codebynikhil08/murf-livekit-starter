'use client';

import { useState, useEffect } from 'react';
import { useTheme } from 'next-themes';
import { AnimatePresence, motion } from 'motion/react';
import { useAgent, useSessionContext } from '@livekit/components-react';
import type { AppConfig } from '@/app-config';
import { AgentSessionView_01 } from '@/components/agents-ui/blocks/agent-session-view-01';
import { WelcomeView } from '@/components/app/welcome-view';
import { EscalationDashboard } from '@/components/app/escalation-dashboard';

const MotionWelcomeView = motion.create(WelcomeView);
const MotionSessionView = motion.create(AgentSessionView_01);

const VIEW_MOTION_PROPS = {
  variants: {
    visible: {
      opacity: 1,
      scale: 1,
    },
    hidden: {
      opacity: 0,
      scale: 0.97,
    },
  },
  initial: 'hidden',
  animate: 'visible',
  exit: 'hidden',
  transition: {
    duration: 0.45,
    ease: 'easeOut',
  },
};

/* ── Connecting Overlay ─────────────────────────────────────────── */
function ConnectingOverlay() {
  return (
    <motion.div
      key="connecting"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.3 }}
      className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-background/80 backdrop-blur-md"
    >
      <div className="flex flex-col items-center gap-5">
        {/* Spinner */}
        <div className="relative h-16 w-16">
          <div className="absolute inset-0 rounded-full border-4 border-primary/20" />
          <div className="absolute inset-0 rounded-full border-4 border-transparent border-t-primary animate-spin" />
          <div className="absolute inset-2 flex items-center justify-center rounded-full bg-primary/10">
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="text-primary"
            >
              <path d="M3 18v-6a9 9 0 0 1 18 0v6" />
              <path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z" />
            </svg>
          </div>
        </div>
        <div className="text-center">
          <p className="text-base font-semibold text-foreground">Connecting to Kisan Mitra...</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Setting up your AI agricultural assistant session, please wait
          </p>
        </div>
        {/* Animated dots */}
        <div className="flex gap-1.5">
          {[0, 1, 2].map((i) => (
            <motion.div
              key={i}
              className="h-1.5 w-1.5 rounded-full bg-primary"
              animate={{ opacity: [0.3, 1, 0.3] }}
              transition={{
                duration: 1.2,
                repeat: Infinity,
                delay: i * 0.25,
              }}
            />
          ))}
        </div>
      </div>
    </motion.div>
  );
}

/* ── Inner component that can use useAgent() inside SessionProvider ─ */
function ViewControllerInner({ appConfig }: { appConfig: AppConfig }) {
  const { isConnected, start } = useSessionContext();
  const { state: agentState } = useAgent();
  const { resolvedTheme } = useTheme();
  const [dashboardOpen, setDashboardOpen] = useState(false);
  const [openTicketsCount, setOpenTicketsCount] = useState(0);

  // Poll open tickets count for top button badge
  useEffect(() => {
    const fetchCount = async () => {
      try {
        const res = await fetch('/api/escalations');
        const data = await res.json();
        if (data.success && Array.isArray(data.escalations)) {
          const openCount = data.escalations.filter(
            (item: { status: string }) => item.status === 'Open'
          ).length;
          setOpenTicketsCount(openCount);
        }
      } catch {
        // silent catch
      }
    };
    fetchCount();
    const interval = setInterval(fetchCount, 4000);
    return () => clearInterval(interval);
  }, []);

  const isConnecting = isConnected && agentState === 'connecting';
  const showWelcome = !isConnected;
  const showSession = isConnected;

  return (
    <>
      {/* Top Bar for Escalations Dashboard */}
      <div className="fixed top-4 right-4 z-40 flex items-center gap-3">
        <button
          onClick={() => setDashboardOpen(true)}
          className="relative inline-flex items-center gap-2 rounded-full border border-amber-500/30 bg-slate-900/90 px-4 py-2 text-xs font-semibold text-amber-300 backdrop-blur-md shadow-lg transition-all hover:bg-slate-800 hover:border-amber-500/60 active:scale-95"
        >
          <span className="text-base">🌾</span>
          <span>Human Help Portal</span>
          {openTicketsCount > 0 && (
            <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1.5 text-[11px] font-bold text-white shadow-sm animate-pulse">
              {openTicketsCount}
            </span>
          )}
        </button>
      </div>

      {/* Escalation Dashboard Modal */}
      <EscalationDashboard
        isOpen={dashboardOpen}
        onClose={() => setDashboardOpen(false)}
      />

      <AnimatePresence mode="wait">
        {/* Welcome view */}
        {showWelcome && (
          <MotionWelcomeView
            key="welcome"
            {...VIEW_MOTION_PROPS}
            startButtonText={appConfig.startButtonText}
            onStartCall={start}
          />
        )}
        {/* Session view */}
        {showSession && (
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
            className="fixed inset-0"
          />
        )}
      </AnimatePresence>

      {/* Connecting overlay */}
      <AnimatePresence>
        {isConnecting && <ConnectingOverlay key="connecting-overlay" />}
      </AnimatePresence>
    </>
  );
}

interface ViewControllerProps {
  appConfig: AppConfig;
}

export function ViewController({ appConfig }: ViewControllerProps) {
  return <ViewControllerInner appConfig={appConfig} />;
}

