import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mic, Volume2, Sparkles, Activity } from 'lucide-react';

/**
 * 3D Iridescent Liquid Crystal Voice Orb
 * Inspired by theosm™ PRO+ iconic spherical AI assistant visual:
 * - Ultra-glossy 3D glass crystal sphere
 * - Flowing iridescent chromatic nebula core (violet, magenta, cyan, amber)
 * - Realistic studio-light curved glass specular reflections & subsurface caustics
 * - Audio-reactive concentric acoustic ripples & floating levitation dynamics
 */
export default function VoiceOrb({
  isListening = false,
  isSpeaking = true,
  state = null, // 'speaking' | 'listening' | 'idle'
  size = 'lg',
  className = '',
  onClick,
  showLabel = true,
}) {
  const [hovered, setHovered] = useState(false);
  const [isClicked, setIsClicked] = useState(false);

  // Normalize state if 'state' prop is provided
  const speakingActive = state !== null ? state === 'speaking' : isSpeaking;
  const listeningActive = state !== null ? state === 'listening' : isListening;

  // Sizing matrix
  const sizeConfig = {
    sm: {
      container: 'w-28 h-28',
      orb: 'w-20 h-20',
      highlightSize: 'h-6',
      iconSize: 'w-3.5 h-3.5',
      fontSize: 'text-[9px]',
    },
    md: {
      container: 'w-48 h-48',
      orb: 'w-36 h-36',
      highlightSize: 'h-10',
      iconSize: 'w-4 h-4',
      fontSize: 'text-[10px]',
    },
    lg: {
      container: 'w-64 h-64',
      orb: 'w-48 h-48',
      highlightSize: 'h-14',
      iconSize: 'w-5 h-5',
      fontSize: 'text-[11px]',
    },
    xl: {
      container: 'w-80 h-80',
      orb: 'w-60 h-60',
      highlightSize: 'h-16',
      iconSize: 'w-6 h-6',
      fontSize: 'text-xs',
    },
  }[size] || {
    container: 'w-64 h-64',
    orb: 'w-48 h-48',
    highlightSize: 'h-14',
    iconSize: 'w-5 h-5',
    fontSize: 'text-[11px]',
  };

  const handleClick = (e) => {
    setIsClicked(true);
    setTimeout(() => setIsClicked(false), 600);
    if (onClick) onClick(e);
  };

  return (
    <div
      className={`relative ${sizeConfig.container} flex flex-col items-center justify-center cursor-pointer select-none group ${className}`}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={handleClick}
    >
      {/* 1. ATMOSPHERIC CHROMATIC BLOOM (Back Ambient Glow) */}
      <motion.div
        animate={{
          scale: speakingActive ? [1, 1.28, 1.05, 1.22, 1] : listeningActive ? [1, 1.15, 1] : [1, 1.06, 1],
          opacity: speakingActive ? [0.45, 0.75, 0.5, 0.8, 0.45] : listeningActive ? [0.4, 0.65, 0.4] : [0.25, 0.4, 0.25],
        }}
        transition={{
          duration: speakingActive ? 3.2 : 4.5,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
        className="absolute inset-0 rounded-full bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-fuchsia-600/40 via-purple-700/35 to-cyan-500/20 blur-3xl pointer-events-none"
      />

      {/* Secondary Warm Underglow */}
      <motion.div
        animate={{
          scale: speakingActive ? [0.9, 1.2, 0.95, 1.15, 0.9] : [1, 1.08, 1],
          opacity: speakingActive ? [0.35, 0.65, 0.35] : [0.2, 0.35, 0.2],
        }}
        transition={{
          duration: speakingActive ? 2.8 : 5,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
        className="absolute -bottom-4 w-3/4 h-1/2 rounded-full bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-amber-500/30 via-rose-500/20 to-transparent blur-2xl pointer-events-none"
      />

      {/* 2. ACOUSTIC RIPPLE WAVE EXPANSIONS (Active on Speaking or Click) */}
      {(speakingActive || isClicked) && (
        <>
          <motion.div
            initial={{ scale: 0.85, opacity: 0.8 }}
            animate={{ scale: [0.85, 1.5, 1.85], opacity: [0.75, 0.3, 0] }}
            transition={{ duration: 2.4, repeat: Infinity, ease: 'easeOut' }}
            className="absolute inset-0 rounded-full border border-fuchsia-400/40 pointer-events-none"
            style={{
              boxShadow: '0 0 25px rgba(236, 72, 153, 0.3), inset 0 0 15px rgba(168, 85, 247, 0.2)',
            }}
          />
          <motion.div
            initial={{ scale: 0.85, opacity: 0.7 }}
            animate={{ scale: [0.85, 1.55, 1.95], opacity: [0.65, 0.25, 0] }}
            transition={{ duration: 2.4, delay: 0.8, repeat: Infinity, ease: 'easeOut' }}
            className="absolute inset-0 rounded-full border border-cyan-400/35 pointer-events-none"
            style={{
              boxShadow: '0 0 20px rgba(6, 182, 212, 0.3)',
            }}
          />
          <motion.div
            initial={{ scale: 0.85, opacity: 0.6 }}
            animate={{ scale: [0.85, 1.6, 2.05], opacity: [0.55, 0.2, 0] }}
            transition={{ duration: 2.4, delay: 1.6, repeat: Infinity, ease: 'easeOut' }}
            className="absolute inset-0 rounded-full border border-purple-400/30 pointer-events-none"
          />
        </>
      )}

      {/* 3. LISTENING FOCUS RESONANCE PULSE */}
      {listeningActive && (
        <motion.div
          animate={{ scale: [1, 1.15, 1], opacity: [0.6, 0.2, 0.6] }}
          transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
          className="absolute inset-1 rounded-full border-2 border-cyan-400/50 pointer-events-none"
          style={{ boxShadow: '0 0 30px rgba(6, 182, 212, 0.4)' }}
        />
      )}

      {/* 4. THE 3D IRIDESCENT CRYSTAL SPHERE CONTAINER */}
      <motion.div
        animate={{
          y: speakingActive ? [-3, 3, -3] : [-2, 2, -2],
          scale: isClicked ? 0.95 : hovered ? 1.04 : 1,
        }}
        transition={{
          y: { duration: 4, repeat: Infinity, ease: 'easeInOut' },
          scale: { type: 'spring', stiffness: 350, damping: 20 },
        }}
        className={`relative ${sizeConfig.orb} rounded-full overflow-hidden flex items-center justify-center`}
        style={{
          boxShadow: `
            0 25px 60px -12px rgba(112, 26, 117, 0.65),
            0 15px 35px -8px rgba(6, 182, 212, 0.4),
            0 0 50px rgba(168, 85, 247, 0.35),
            inset 0 0 35px rgba(255, 255, 255, 0.22),
            inset 0 -18px 30px rgba(59, 7, 100, 0.9),
            inset 0 12px 25px rgba(255, 255, 255, 0.45)
          `,
        }}
      >
        {/* A. BASE CHROMATIC DEEP VIOLET / INDIGO CORE */}
        <div
          className="absolute inset-0 rounded-full"
          style={{
            background: 'radial-gradient(circle at 35% 35%, #9333ea 0%, #6366f1 35%, #312e81 65%, #0f051d 100%)',
          }}
        />

        {/* B. FLUID MORPHING LAYER 1: HOT MAGENTA & FUCHSIA CYCLONE */}
        <motion.div
          animate={{
            rotate: [0, 180, 360],
            scale: speakingActive ? [1, 1.25, 0.95, 1.18, 1] : [1, 1.12, 1],
          }}
          transition={{
            rotate: { duration: speakingActive ? 9 : 18, repeat: Infinity, ease: 'linear' },
            scale: { duration: 4.5, repeat: Infinity, ease: 'easeInOut' },
          }}
          className="absolute -inset-1/4 rounded-full opacity-85 mix-blend-screen"
          style={{
            background: 'radial-gradient(circle at 70% 65%, #f43f5e 0%, #ec4899 35%, #a855f7 65%, transparent 80%)',
          }}
        />

        {/* C. FLUID MORPHING LAYER 2: ELECTRIC CYAN & AQUA CAUSTIC SWIRL */}
        <motion.div
          animate={{
            rotate: [360, 180, 0],
            scale: speakingActive ? [0.9, 1.2, 0.92, 1.15, 0.9] : [0.95, 1.1, 0.95],
          }}
          transition={{
            rotate: { duration: speakingActive ? 12 : 22, repeat: Infinity, ease: 'linear' },
            scale: { duration: 5, repeat: Infinity, ease: 'easeInOut' },
          }}
          className="absolute -inset-1/3 rounded-full opacity-75 mix-blend-color-dodge"
          style={{
            background: 'radial-gradient(ellipse at 30% 75%, #38bdf8 0%, #06b6d4 30%, #818cf8 60%, transparent 80%)',
          }}
        />

        {/* D. FLUID MORPHING LAYER 3: WARM AMBER / PEACH LUMINESCENT HEART */}
        <motion.div
          animate={{
            scale: speakingActive ? [0.8, 1.35, 0.9, 1.28, 0.8] : [0.9, 1.1, 0.9],
            opacity: speakingActive ? [0.65, 0.95, 0.7, 0.9, 0.65] : [0.45, 0.65, 0.45],
          }}
          transition={{
            duration: speakingActive ? 2.5 : 4,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
          className="absolute inset-2 rounded-full mix-blend-screen"
          style={{
            background: 'radial-gradient(circle at 50% 50%, #fb923c 0%, #f59e0b 28%, #ec4899 55%, transparent 75%)',
          }}
        />

        {/* E. ULTRA-REALISTIC CURVED GLASS SPECULAR HIGHLIGHT (The "theosm™ PRO+" Glass Arc) */}
        <div
          className={`absolute top-1 inset-x-3 ${sizeConfig.highlightSize} rounded-[50%_50%_45%_45%_/_60%_60%_35%_35%] pointer-events-none z-20`}
          style={{
            background: 'linear-gradient(180deg, rgba(255, 255, 255, 0.95) 0%, rgba(255, 255, 255, 0.5) 40%, rgba(255, 255, 255, 0) 100%)',
            boxShadow: '0 1px 8px rgba(255, 255, 255, 0.6)',
            filter: 'drop-shadow(0 0 3px rgba(255, 255, 255, 0.8))',
          }}
        />

        {/* F. SECONDARY LOWER SUBSURFACE REFLECTION CRESCENT */}
        <div
          className="absolute bottom-1.5 inset-x-8 h-4 rounded-[40%_40%_60%_60%] pointer-events-none z-20 opacity-60"
          style={{
            background: 'linear-gradient(0deg, rgba(255, 255, 255, 0.7) 0%, rgba(6, 182, 212, 0.3) 60%, transparent 100%)',
            filter: 'blur(1px)',
          }}
        />

        {/* G. CRYSTAL GLASS RIM BEVEL (Fresnel Boundary) */}
        <div
          className="absolute inset-0 rounded-full border border-white/40 pointer-events-none z-20"
          style={{
            boxShadow: `
              inset 0 0 12px rgba(255, 255, 255, 0.5),
              inset 0 -6px 14px rgba(147, 51, 234, 0.4),
              0 0 12px rgba(255, 255, 255, 0.25)
            `,
          }}
        />

        {/* H. MINIMALIST CENTER AUDIO PULSE BARS (Interactive overlay) */}
        <div className="relative z-30 flex items-center justify-center gap-1">
          {[0, 1, 2, 3, 4].map((barIndex) => (
            <motion.div
              key={barIndex}
              animate={{
                height: speakingActive
                  ? [6, 18 + ((barIndex * 7) % 14), 8, 22 - ((barIndex * 5) % 12), 6]
                  : listeningActive
                  ? [4, 10, 4]
                  : [3, 6, 3],
                opacity: speakingActive ? [0.75, 1, 0.8] : [0.45, 0.7, 0.45],
              }}
              transition={{
                duration: speakingActive ? 0.7 + barIndex * 0.12 : 1.6,
                repeat: Infinity,
                ease: 'easeInOut',
                delay: barIndex * 0.08,
              }}
              className="w-1 rounded-full bg-white shadow-[0_0_8px_rgba(255,255,255,0.9)]"
            />
          ))}
        </div>
      </motion.div>

      {/* 5. ELEGANT BOTTOM STATUS PILL */}
      {showLabel && (
        <motion.div
          animate={{
            y: speakingActive ? [-1, 1, -1] : 0,
          }}
          transition={{
            duration: 3,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
          className="mt-3 relative z-10 flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-charcoal/80 backdrop-blur-md border border-ivory/15 shadow-lg shadow-black/40"
        >
          {listeningActive ? (
            <span className="flex items-center gap-1.5 text-cyan-400">
              <Mic className={`${sizeConfig.iconSize} animate-pulse`} />
              <span className={`${sizeConfig.fontSize} font-mono uppercase tracking-widest font-bold`}>
                Listening
              </span>
            </span>
          ) : speakingActive ? (
            <span className="flex items-center gap-1.5 text-amber">
              <Volume2 className={`${sizeConfig.iconSize} animate-bounce`} />
              <span className={`${sizeConfig.fontSize} font-mono uppercase tracking-widest font-bold`}>
                AI Speaking
              </span>
            </span>
          ) : (
            <span className="flex items-center gap-1.5 text-lavender">
              <Sparkles className={`${sizeConfig.iconSize}`} />
              <span className={`${sizeConfig.fontSize} font-mono uppercase tracking-widest font-bold text-mutedgrey`}>
                Online
              </span>
            </span>
          )}

          {/* Micro status ping node */}
          <span className="relative flex h-2 w-2">
            <span
              className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                speakingActive ? 'bg-amber' : listeningActive ? 'bg-cyan-400' : 'bg-emerald-400'
              }`}
            />
            <span
              className={`relative inline-flex rounded-full h-2 w-2 ${
                speakingActive ? 'bg-amber' : listeningActive ? 'bg-cyan-400' : 'bg-emerald-400'
              }`}
            />
          </span>
        </motion.div>
      )}
    </div>
  );
}
