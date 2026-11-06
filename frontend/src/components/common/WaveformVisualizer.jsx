import React from 'react';
import { motion } from 'framer-motion';

export default function WaveformVisualizer({ isPlaying = true, barCount = 28, height = 40, color = 'burnt' }) {
  const bars = Array.from({ length: barCount }, (_, i) => i);

  // Gradient selection
  const gradientClass =
    color === 'amber'
      ? 'from-amber to-amber-light'
      : color === 'lavender'
      ? 'from-lavender to-lavender-light'
      : 'from-burnt via-amber to-burnt-light';

  return (
    <div className="flex items-center gap-1 h-12 px-2" style={{ height: `${height}px` }}>
      {bars.map((bar) => {
        // Generate pseudo-random organic frequency heights
        const minHeight = 4;
        const maxHeight = height * 0.85;
        const randomHeight1 = Math.sin(bar * 0.4) * (maxHeight * 0.5) + maxHeight * 0.5;
        const randomHeight2 = Math.cos(bar * 0.5) * (maxHeight * 0.4) + maxHeight * 0.6;
        const randomHeight3 = Math.sin(bar * 0.8) * (maxHeight * 0.6) + maxHeight * 0.4;

        return (
          <motion.div
            key={bar}
            className={`w-1 rounded-full bg-gradient-to-t ${gradientClass}`}
            animate={
              isPlaying
                ? {
                    height: [
                      `${Math.max(minHeight, randomHeight1)}px`,
                      `${Math.max(minHeight, randomHeight2)}px`,
                      `${Math.max(minHeight, randomHeight3)}px`,
                      `${Math.max(minHeight, randomHeight1)}px`,
                    ],
                    opacity: [0.65, 1, 0.8, 0.65],
                  }
                : { height: `${minHeight}px`, opacity: 0.3 }
            }
            transition={{
              duration: 1.1 + (bar % 5) * 0.15,
              repeat: Infinity,
              ease: 'easeInOut',
              delay: (bar % 6) * 0.08,
            }}
          />
        );
      })}
    </div>
  );
}

