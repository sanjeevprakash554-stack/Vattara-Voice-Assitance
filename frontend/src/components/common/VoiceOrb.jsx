import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Sparkles, Mic, Volume2 } from 'lucide-react';

export default function VoiceOrb({ isListening = false, isSpeaking = true, size = 'lg' }) {
  const [hovered, setHovered] = useState(false);

  const dimensions = {
    sm: 'w-24 h-24',
    md: 'w-44 h-44',
    lg: 'w-64 h-64',
    xl: 'w-80 h-80',
  }[size] || 'w-64 h-64';

  return (
    <div
      className={`relative ${dimensions} flex items-center justify-center cursor-pointer select-none`}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Outer ambient glow */}
      <motion.div
        animate={{
          scale: isSpeaking ? [1, 1.25, 1.05, 1.2, 1] : [1, 1.08, 1],
          opacity: isSpeaking ? [0.35, 0.65, 0.4, 0.7, 0.35] : [0.2, 0.35, 0.2],
        }}
        transition={{
          duration: isSpeaking ? 3 : 5,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
        className="absolute inset-0 rounded-full bg-gradient-to-tr from-burnt/40 via-amber/30 to-lavender/30 blur-3xl pointer-events-none"
      />

      {/* Rotating outer orbital ring */}
      <motion.div
        animate={{ rotate: 360 }}
        transition={{ duration: 25, repeat: Infinity, ease: 'linear' }}
        className="absolute inset-2 rounded-full border border-dashed border-amber/30 pointer-events-none"
      />

      {/* Counter-rotating secondary ring with accent nodes */}
      <motion.div
        animate={{ rotate: -360 }}
        transition={{ duration: 18, repeat: Infinity, ease: 'linear' }}
        className="absolute inset-5 rounded-full border border-burnt/20 pointer-events-none"
      >
        <span className="absolute -top-1 left-1/2 w-2 h-2 rounded-full bg-burnt shadow-lg shadow-burnt" />
        <span className="absolute -bottom-1 left-1/3 w-1.5 h-1.5 rounded-full bg-amber shadow-lg shadow-amber" />
        <span className="absolute top-1/2 -right-1 w-2 h-2 rounded-full bg-lavender shadow-lg shadow-lavender" />
      </motion.div>

      {/* Dynamic Sound Ripple Ring 1 */}
      {isSpeaking && (
        <motion.div
          animate={{
            scale: [1, 1.45, 1.7],
            opacity: [0.7, 0.25, 0],
          }}
          transition={{
            duration: 2.2,
            repeat: Infinity,
            ease: 'easeOut',
          }}
          className="absolute inset-8 rounded-full border border-burnt/50 pointer-events-none"
        />
      )}

      {/* Dynamic Sound Ripple Ring 2 */}
      {isSpeaking && (
        <motion.div
          animate={{
            scale: [1, 1.5, 1.8],
            opacity: [0.6, 0.2, 0],
          }}
          transition={{
            duration: 2.2,
            delay: 0.7,
            repeat: Infinity,
            ease: 'easeOut',
          }}
          className="absolute inset-8 rounded-full border border-amber/40 pointer-events-none"
        />
      )}

      {/* Core Glowing Orb */}
      <motion.div
        animate={{
          scale: isSpeaking ? [1, 1.06, 0.97, 1.04, 1] : [1, 1.02, 1],
          boxShadow: hovered
            ? '0 0 50px rgba(228, 119, 69, 0.8), inset 0 0 35px rgba(240, 173, 87, 0.6)'
            : '0 0 35px rgba(228, 119, 69, 0.5), inset 0 0 25px rgba(240, 173, 87, 0.4)',
        }}
        transition={{
          duration: isSpeaking ? 2 : 4,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
        className="relative w-3/4 h-3/4 rounded-full bg-gradient-to-br from-charcoal-50 via-warmblack to-charcoal border border-amber/40 flex items-center justify-center overflow-hidden"
      >
        {/* Internal fluid gradient swirls */}
        <motion.div
          animate={{
            rotate: [0, 180, 360],
            scale: [1, 1.15, 1],
          }}
          transition={{
            duration: 12,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
          className="absolute inset-0 opacity-40 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-amber via-burnt to-transparent blur-md"
        />

        {/* Center icon / soundwave indicator */}
        <div className="relative z-10 flex flex-col items-center gap-1 text-ivory">
          <motion.div
            animate={{
              scale: isSpeaking ? [1, 1.2, 1] : 1,
            }}
            transition={{
              duration: 1.2,
              repeat: Infinity,
            }}
          >
            {isListening ? (
              <Mic className="w-8 h-8 text-amber animate-pulse" />
            ) : isSpeaking ? (
              <Volume2 className="w-8 h-8 text-burnt-light" />
            ) : (
              <Sparkles className="w-8 h-8 text-lavender" />
            )}
          </motion.div>
          <span className="text-[10px] font-mono tracking-widest uppercase text-mutedgrey font-semibold">
            {isSpeaking ? 'AI Speaking' : 'Listening'}
          </span>
        </div>
      </motion.div>
    </div>
  );
}

