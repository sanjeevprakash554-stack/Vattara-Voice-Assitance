import React from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Palette,
  X,
  Check,
  Sun,
  Moon,
  RotateCcw,
  Sparkles,
  Sliders,
  Pipette,
  CheckCircle2,
} from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';
import confetti from 'canvas-confetti';

const QUICK_ACCENTS = [
  { name: 'Vattara Burnt', hex: '#E47745' },
  { name: 'Solar Amber', hex: '#F0AD57' },
  { name: 'Royal Violet', hex: '#8B5CF6' },
  { name: 'Electric Cyan', hex: '#06B6D4' },
  { name: 'Emerald Jade', hex: '#10B981' },
  { name: 'Hot Rose', hex: '#F43F5E' },
  { name: 'Gold Dust', hex: '#EAB308' },
  { name: 'Ocean Coral', hex: '#FF6B6B' },
];

export default function ThemeCustomizerModal({ isOpen, onClose }) {
  const {
    themes,
    themeId,
    setThemeId,
    mode,
    setMode,
    customAccent,
    setCustomAccent,
    resetToDefault,
  } = useTheme();

  if (!isOpen) return null;

  const handleSelectTheme = (id) => {
    setThemeId(id);
    confetti({
      particleCount: 25,
      spread: 40,
      origin: { x: 0.85, y: 0.3 },
      colors: ['#E47745', '#F0AD57', '#A78BFA'],
    });
  };

  const handleReset = () => {
    resetToDefault();
    confetti({
      particleCount: 35,
      spread: 50,
      colors: ['#E47745', '#F0AD57'],
    });
  };

  return createPortal(
    <div className="fixed inset-0 z-[100] overflow-hidden flex justify-end">
      {/* Backdrop */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        className="fixed inset-0 bg-warmblack/70 backdrop-blur-sm"
      />

      {/* Slide-over Panel */}
      <motion.div
        initial={{ x: '100%' }}
        animate={{ x: 0 }}
        exit={{ x: '100%' }}
        transition={{ type: 'spring', damping: 26, stiffness: 220 }}
        className="relative w-full max-w-xl bg-charcoal border-l border-graphite shadow-2xl h-screen max-h-screen flex flex-col z-10 overflow-hidden"
      >
        {/* Panel Top Header */}
        <div className="p-6 border-b border-graphite flex items-center justify-between bg-warmblack/70 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <span className="p-2.5 rounded-2xl bg-burnt/15 border border-burnt/30 text-burnt">
              <Palette className="w-5 h-5 animate-pulse" />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-ivory">Theme & Visual Experience</h2>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold uppercase tracking-wider bg-burnt/15 text-burnt border border-burnt/30">
                  Live Sync
                </span>
              </div>
              <p className="text-xs text-mutedgrey mt-0.5">
                Switch themes, appearance mode, and custom accent colors across all pages.
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 rounded-xl bg-warmblack border border-graphite text-mutedgrey hover:text-ivory transition-colors"
            title="Close theme panel"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Panel Scrollable Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* 1. Appearance Mode: Dark vs Light */}
          <div className="space-y-3">
            <span className="text-[11px] font-mono uppercase font-bold tracking-wider text-mutedgrey flex items-center gap-1.5">
              <Sun className="w-3.5 h-3.5 text-amber" /> Appearance Mode
            </span>

            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setMode('dark')}
                className={`p-3.5 rounded-2xl border flex items-center justify-between transition-all ${
                  mode === 'dark'
                    ? 'bg-burnt/15 border-burnt text-ivory font-bold shadow-lg shadow-burnt/10'
                    : 'bg-warmblack/60 border-graphite text-mutedgrey hover:text-ivory hover:border-burnt/40'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Moon className="w-4 h-4 text-burnt" />
                  <div className="text-left">
                    <p className="text-xs font-bold text-ivory">Dark Surface</p>
                    <p className="text-[10px] text-mutedgrey">Signature Deep Charcoal</p>
                  </div>
                </div>
                {mode === 'dark' && <Check className="w-4 h-4 text-burnt stroke-[3]" />}
              </button>

              <button
                type="button"
                onClick={() => setMode('light')}
                className={`p-3.5 rounded-2xl border flex items-center justify-between transition-all ${
                  mode === 'light'
                    ? 'bg-burnt/15 border-burnt text-ivory font-bold shadow-lg shadow-burnt/10'
                    : 'bg-warmblack/60 border-graphite text-mutedgrey hover:text-ivory hover:border-burnt/40'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Sun className="w-4 h-4 text-amber" />
                  <div className="text-left">
                    <p className="text-xs font-bold text-ivory">Light Surface</p>
                    <p className="text-[10px] text-mutedgrey">Clean Editorial White</p>
                  </div>
                </div>
                {mode === 'light' && <Check className="w-4 h-4 text-burnt stroke-[3]" />}
              </button>
            </div>
          </div>

          {/* 2. 12 Predefined Themes Grid */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-mono uppercase font-bold tracking-wider text-mutedgrey flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-burnt" /> Predefined Themes ({themes.length})
              </span>
              <span className="text-[10px] font-mono text-burnt font-semibold">Immediate Live Preview</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
              {themes.map((t) => {
                const isSelected = themeId === t.id;

                return (
                  <motion.div
                    key={t.id}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => handleSelectTheme(t.id)}
                    className={`relative p-3.5 rounded-2xl border cursor-pointer transition-all flex flex-col justify-between ${
                      isSelected
                        ? 'bg-warmblack border-burnt shadow-lg shadow-burnt/15 ring-1 ring-burnt'
                        : 'bg-warmblack/60 border-graphite hover:border-burnt/40'
                    }`}
                  >
                    <div>
                      {/* Top Header & Check */}
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <div>
                          <h4 className="text-xs font-bold text-ivory flex items-center gap-1.5">
                            {t.name}
                          </h4>
                          <p className="text-[10px] text-mutedgrey line-clamp-1 mt-0.5">
                            {t.description}
                          </p>
                        </div>

                        {isSelected && (
                          <span className="w-5 h-5 rounded-full bg-burnt text-warmblack flex items-center justify-center shrink-0">
                            <Check className="w-3.5 h-3.5 stroke-[3]" />
                          </span>
                        )}
                      </div>

                      {/* Color Palette Swatches */}
                      <div className="flex items-center gap-1.5 py-1">
                        {t.preview.map((color, idx) => (
                          <div
                            key={idx}
                            className="w-5 h-5 rounded-lg border border-white/10 shadow-sm"
                            style={{ backgroundColor: color }}
                            title={`Color: ${color}`}
                          />
                        ))}
                      </div>
                    </div>

                    {/* Mini UI Preview Strip */}
                    <div
                      className="mt-3 p-1.5 rounded-xl border border-white/5 flex items-center justify-between text-[9px] font-mono"
                      style={{
                        backgroundColor: mode === 'light' ? t.light.charcoal : t.dark.charcoal,
                        borderColor: mode === 'light' ? t.light.graphite : t.dark.graphite,
                      }}
                    >
                      <span
                        className="px-2 py-0.5 rounded font-bold"
                        style={{
                          backgroundColor: `${t.dark.burnt}25`,
                          color: t.dark.burnt,
                        }}
                      >
                        Accent
                      </span>
                      <span
                        className="truncate max-w-[80px]"
                        style={{ color: mode === 'light' ? t.light.ivory : t.dark.ivory }}
                      >
                        AI Interface
                      </span>
                      <span
                        className="w-2 h-2 rounded-full"
                        style={{ backgroundColor: t.dark.amber }}
                      />
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </div>

          {/* 3. Custom Accent Color Option */}
          <div className="space-y-3 pt-2 border-t border-graphite">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-mono uppercase font-bold tracking-wider text-mutedgrey flex items-center gap-1.5">
                <Pipette className="w-3.5 h-3.5 text-amber" /> Custom Accent Color
              </span>
              {customAccent && (
                <button
                  type="button"
                  onClick={() => setCustomAccent(null)}
                  className="text-[10px] text-burnt hover:underline font-mono"
                >
                  Reset Custom Accent
                </button>
              )}
            </div>

            {/* Quick Presets */}
            <div className="grid grid-cols-4 sm:grid-cols-8 gap-2">
              {QUICK_ACCENTS.map((item) => {
                const isActive = customAccent?.toLowerCase() === item.hex.toLowerCase();

                return (
                  <button
                    key={item.hex}
                    type="button"
                    onClick={() => setCustomAccent(item.hex)}
                    className={`h-9 rounded-xl border flex items-center justify-center transition-all ${
                      isActive
                        ? 'border-ivory ring-2 ring-burnt scale-110 shadow-md'
                        : 'border-transparent hover:scale-105'
                    }`}
                    style={{ backgroundColor: item.hex }}
                    title={item.name}
                  >
                    {isActive && <Check className="w-4 h-4 text-warmblack stroke-[3]" />}
                  </button>
                );
              })}
            </div>

            {/* Custom Color Input */}
            <div className="flex items-center gap-3 p-3 rounded-2xl bg-warmblack/70 border border-graphite">
              <input
                type="color"
                value={customAccent || '#E47745'}
                onChange={(e) => setCustomAccent(e.target.value)}
                className="w-8 h-8 rounded-xl border-0 cursor-pointer bg-transparent"
              />
              <div className="flex-1">
                <p className="text-xs font-bold text-ivory">Hex Color Code</p>
                <p className="text-[10px] font-mono text-mutedgrey">
                  {customAccent ? `Active: ${customAccent}` : 'Using theme default accent'}
                </p>
              </div>
              <input
                type="text"
                placeholder="#E47745"
                value={customAccent || ''}
                onChange={(e) => {
                  const val = e.target.value;
                  if (val.startsWith('#') && (val.length === 4 || val.length === 7)) {
                    setCustomAccent(val);
                  }
                }}
                className="w-24 px-2.5 py-1.5 rounded-xl bg-charcoal border border-graphite text-xs font-mono text-ivory text-center uppercase"
              />
            </div>
          </div>
        </div>

        {/* Panel Footer */}
        <div className="p-4 border-t border-graphite bg-warmblack/90 flex items-center justify-between">
          <button
            type="button"
            onClick={handleReset}
            className="px-4 py-2 rounded-xl bg-warmblack hover:bg-graphite border border-graphite text-xs font-semibold text-mutedgrey hover:text-ivory flex items-center gap-1.5 transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5 text-burnt" />
            Reset to Default
          </button>

          <button
            type="button"
            onClick={onClose}
            className="px-6 py-2 rounded-xl bg-gradient-to-r from-burnt to-amber text-warmblack font-bold text-xs shadow-md shadow-burnt/20 hover:scale-[1.02] active:scale-[0.98] transition-all"
          >
            Done
          </button>
        </div>
      </motion.div>
    </div>,
    document.body
  );
}

