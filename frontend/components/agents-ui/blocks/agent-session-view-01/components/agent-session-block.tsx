'use client';

import React, { useEffect, useRef, useState } from 'react';
import { AnimatePresence, type MotionProps, motion } from 'motion/react';
import { useAgent, useSessionContext, useSessionMessages } from '@livekit/components-react';
import { AgentChatTranscript } from '@/components/agents-ui/agent-chat-transcript';
import {
  AgentControlBar,
  type AgentControlBarControls,
} from '@/components/agents-ui/agent-control-bar';
import { Shimmer } from '@/components/ai-elements/shimmer';
import { cn } from '@/lib/shadcn/utils';
import { TileLayout } from './tile-view';

const MotionMessage = motion.create(Shimmer);

const BOTTOM_VIEW_MOTION_PROPS: MotionProps = {
  variants: {
    visible: {
      opacity: 1,
      translateY: '0%',
    },
    hidden: {
      opacity: 0,
      translateY: '100%',
    },
  },
  initial: 'hidden',
  animate: 'visible',
  exit: 'hidden',
  transition: {
    duration: 0.3,
    delay: 0.5,
    ease: 'easeOut',
  },
};

const CHAT_MOTION_PROPS: MotionProps = {
  variants: {
    hidden: {
      opacity: 0,
      transition: {
        ease: 'easeOut',
        duration: 0.3,
      },
    },
    visible: {
      opacity: 1,
      transition: {
        delay: 0.2,
        ease: 'easeOut',
        duration: 0.3,
      },
    },
  },
  initial: 'hidden',
  animate: 'visible',
  exit: 'hidden',
};

const SHIMMER_MOTION_PROPS: MotionProps = {
  variants: {
    visible: {
      opacity: 1,
      transition: {
        ease: 'easeIn',
        duration: 0.5,
        delay: 0.8,
      },
    },
    hidden: {
      opacity: 0,
      transition: {
        ease: 'easeIn',
        duration: 0.5,
        delay: 0,
      },
    },
  },
  initial: 'hidden',
  animate: 'visible',
  exit: 'hidden',
};

interface FadeProps {
  top?: boolean;
  bottom?: boolean;
  className?: string;
}

export function Fade({ top = false, bottom = false, className }: FadeProps) {
  return (
    <div
      className={cn(
        'from-background pointer-events-none h-4 bg-linear-to-b to-transparent',
        top && 'bg-linear-to-b',
        bottom && 'bg-linear-to-t',
        className
      )}
    />
  );
}

/* ── Agent State Badge ──────────────────────────────────────────── */
type AgentStateType = 'connecting' | 'pre-connect-buffering' | 'listening' | 'thinking' | 'speaking' | string;

interface AgentStateBadgeProps {
  agentState: AgentStateType;
}

function AgentStateBadge({ agentState }: AgentStateBadgeProps) {
  const config = {
    connecting: {
      label: 'Connecting...',
      color: 'bg-yellow-500/15 text-yellow-600 dark:text-yellow-400 border-yellow-500/20',
      dot: 'bg-yellow-500 animate-pulse',
    },
    'pre-connect-buffering': {
      label: 'Warming up...',
      color: 'bg-blue-500/15 text-blue-600 dark:text-blue-400 border-blue-500/20',
      dot: 'bg-blue-500 animate-pulse',
    },
    listening: {
      label: 'Listening to you...',
      color: 'bg-primary/15 text-primary border-primary/20',
      dot: 'bg-primary animate-listening-ripple',
    },
    thinking: {
      label: 'Agent is thinking...',
      color: 'bg-purple-500/15 text-purple-600 dark:text-purple-400 border-purple-500/20',
      dot: 'bg-purple-500 animate-pulse',
    },
    speaking: {
      label: 'Agent is speaking...',
      color: 'bg-orange-400/15 text-orange-600 dark:text-orange-400 border-orange-400/20',
      dot: 'bg-orange-400 animate-speaking-ring',
    },
  };

  const cfg = config[agentState as keyof typeof config] ?? config.connecting;

  return (
    <motion.div
      key={agentState}
      initial={{ opacity: 0, y: 6, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -6, scale: 0.95 }}
      transition={{ duration: 0.2 }}
      className={cn(
        'inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold backdrop-blur-sm',
        cfg.color
      )}
    >
      <span className={cn('h-2 w-2 rounded-full shrink-0', cfg.dot)} />
      {cfg.label}
    </motion.div>
  );
}

/* ── Call Ended Overlay ─────────────────────────────────────────── */
interface CallEndedOverlayProps {
  onRestart: () => void;
}

function CallEndedOverlay({ onRestart }: CallEndedOverlayProps) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-background/90 backdrop-blur-md px-6"
    >
      <motion.div
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ delay: 0.15, type: 'spring', stiffness: 300, damping: 25 }}
        className="flex flex-col items-center gap-6 text-center max-w-sm"
      >
        {/* Checkmark circle */}
        <div className="flex h-20 w-20 items-center justify-center rounded-full bg-green-500/15 border border-green-500/30">
          <svg
            width="36"
            height="36"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="text-green-500"
          >
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
            <polyline points="22 4 12 14.01 9 11.01" />
          </svg>
        </div>

        <div>
          <h2 className="text-2xl font-bold text-foreground">Call Ended</h2>
          <p className="mt-2 text-sm text-muted-foreground leading-6">
            Thank you for using TechSeva Support. We hope we could help!
          </p>
        </div>

        <div className="flex flex-col sm:flex-row gap-3 w-full">
          <button
            id="restart-call-btn"
            onClick={onRestart}
            className="flex-1 inline-flex items-center justify-center gap-2 rounded-full bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground shadow-[0_4px_20px_rgba(99,102,241,0.35)] transition-all hover:shadow-[0_6px_30px_rgba(99,102,241,0.5)] hover:scale-[1.02] active:scale-[0.98]"
          >
            <svg
              width="15"
              height="15"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
              <path d="M3 3v5h5" />
            </svg>
            Start Again
          </button>
        </div>

        <p className="text-xs text-muted-foreground/60">
          Powered by Murf Falcon · TechSeva AI Support
        </p>
      </motion.div>
    </motion.div>
  );
}

export interface AgentSessionView_01Props {
  /**
   * Message shown above the controls before the first chat message is sent.
   *
   * @default 'Agent is listening, ask it a question'
   */
  preConnectMessage?: string;
  /**
   * Enables or disables the chat toggle and transcript input controls.
   *
   * @default true
   */
  supportsChatInput?: boolean;
  /**
   * Enables or disables camera controls in the bottom control bar.
   *
   * @default true
   */
  supportsVideoInput?: boolean;
  /**
   * Enables or disables screen sharing controls in the bottom control bar.
   *
   * @default true
   */
  supportsScreenShare?: boolean;
  /**
   * Shows a pre-connect buffer state with a shimmer message before messages appear.
   *
   * @default true
   */
  isPreConnectBufferEnabled?: boolean;

  /** Selects the visualizer style rendered in the main tile area. */
  audioVisualizerType?: 'bar' | 'wave' | 'grid' | 'radial' | 'aura';
  /** Primary hex color used by supported audio visualizer variants. */
  audioVisualizerColor?: `#${string}`;
  /** Hue shift intensity used by certain visualizers. */
  audioVisualizerColorShift?: number;
  /** Number of bars to render when `audioVisualizerType` is `bar`. */
  audioVisualizerBarCount?: number;
  /** Number of rows in the visualizer when `audioVisualizerType` is `grid`. */
  audioVisualizerGridRowCount?: number;
  /** Number of columns in the visualizer when `audioVisualizerType` is `grid`. */
  audioVisualizerGridColumnCount?: number;
  /** Number of radial bars when `audioVisualizerType` is `radial`. */
  audioVisualizerRadialBarCount?: number;
  /** Base radius of the radial visualizer when `audioVisualizerType` is `radial`. */
  audioVisualizerRadialRadius?: number;
  /** Stroke width of the wave path when `audioVisualizerType` is `wave`. */
  audioVisualizerWaveLineWidth?: number;
  /** Optional class name merged onto the outer `<section>` container. */
  className?: string;
}

export function AgentSessionView_01({
  preConnectMessage = 'नमस्ते! TechSeva Support यहाँ है — आप क्या जानना चाहते हैं?',
  supportsChatInput = true,
  supportsVideoInput = false,
  supportsScreenShare = false,
  isPreConnectBufferEnabled = true,

  audioVisualizerType,
  audioVisualizerColor,
  audioVisualizerColorShift,
  audioVisualizerBarCount,
  audioVisualizerGridRowCount,
  audioVisualizerGridColumnCount,
  audioVisualizerRadialBarCount,
  audioVisualizerRadialRadius,
  audioVisualizerWaveLineWidth,
  ref,
  className,
  ...props
}: React.ComponentProps<'section'> & AgentSessionView_01Props) {
  const session = useSessionContext();
  const { messages } = useSessionMessages(session);
  const [chatOpen, setChatOpen] = useState(false);
  const [callEnded, setCallEnded] = useState(false);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const { state: agentState } = useAgent();

  const controls: AgentControlBarControls = {
    leave: true,
    microphone: true,
    chat: supportsChatInput,
    camera: supportsVideoInput,
    screenShare: supportsScreenShare,
  };

  useEffect(() => {
    const lastMessage = messages.at(-1);
    const lastMessageIsLocal = lastMessage?.from?.isLocal === true;

    if (scrollAreaRef.current && lastMessageIsLocal) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
    }
  }, [messages]);

  const handleDisconnect = () => {
    session.end();
    setCallEnded(true);
  };

  const handleRestart = () => {
    setCallEnded(false);
    session.start();
  };

  return (
    <section
      ref={ref}
      className={cn('bg-background relative z-10 h-full w-full overflow-hidden', className)}
      {...props}
    >
      <Fade top className="absolute inset-x-4 top-0 z-10 h-40" />

      {/* Agent state badge — centered top */}
      <div className="absolute top-20 left-0 right-0 z-20 flex justify-center pointer-events-none">
        <AnimatePresence mode="wait">
          {agentState && agentState !== 'disconnected' && (
            <AgentStateBadge key={agentState} agentState={agentState} />
          )}
        </AnimatePresence>
      </div>

      {/* transcript */}
      <div className="absolute top-0 bottom-[135px] flex w-full flex-col md:bottom-[170px]">
        <AnimatePresence>
          {chatOpen && (
            <motion.div
              {...CHAT_MOTION_PROPS}
              className="flex h-full w-full flex-col gap-4 space-y-3 transition-opacity duration-300 ease-out"
            >
              <AgentChatTranscript
                agentState={agentState}
                messages={messages}
                className="mx-auto w-full max-w-2xl [&_.is-user>div]:rounded-[22px] [&>div>div]:px-4 [&>div>div]:pt-40 md:[&>div>div]:px-6"
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Tile layout — audio visualizer */}
      <TileLayout
        chatOpen={chatOpen}
        audioVisualizerType={audioVisualizerType}
        audioVisualizerColor={audioVisualizerColor}
        audioVisualizerColorShift={audioVisualizerColorShift}
        audioVisualizerBarCount={audioVisualizerBarCount}
        audioVisualizerRadialBarCount={audioVisualizerRadialBarCount}
        audioVisualizerRadialRadius={audioVisualizerRadialRadius}
        audioVisualizerGridRowCount={audioVisualizerGridRowCount}
        audioVisualizerGridColumnCount={audioVisualizerGridColumnCount}
        audioVisualizerWaveLineWidth={audioVisualizerWaveLineWidth}
      />

      {/* Bottom controls */}
      <motion.div
        {...BOTTOM_VIEW_MOTION_PROPS}
        className="absolute inset-x-3 bottom-0 z-50 md:inset-x-12"
      >
        {/* Pre-connect message */}
        {isPreConnectBufferEnabled && (
          <AnimatePresence>
            {messages.length === 0 && (
              <MotionMessage
                key="pre-connect-message"
                duration={2}
                aria-hidden={messages.length > 0}
                {...SHIMMER_MOTION_PROPS}
                className="pointer-events-none mx-auto block w-full max-w-2xl pb-4 text-center text-sm font-semibold"
              >
                {preConnectMessage}
              </MotionMessage>
            )}
          </AnimatePresence>
        )}
        <div className="bg-background relative mx-auto max-w-2xl pb-3 md:pb-12">
          <Fade bottom className="absolute inset-x-0 top-0 h-4 -translate-y-full" />
          <AgentControlBar
            variant="livekit"
            controls={controls}
            isChatOpen={chatOpen}
            isConnected={session.isConnected}
            onDisconnect={handleDisconnect}
            onIsChatOpenChange={setChatOpen}
          />
        </div>
      </motion.div>

      {/* Call Ended Overlay */}
      <AnimatePresence>
        {callEnded && (
          <CallEndedOverlay key="call-ended" onRestart={handleRestart} />
        )}
      </AnimatePresence>
    </section>
  );
}
