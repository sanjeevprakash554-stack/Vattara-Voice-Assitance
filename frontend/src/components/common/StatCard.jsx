import React from 'react';
import { motion } from 'framer-motion';

export default function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  color = 'burnt',
  trend,
  className = '',
  sparkline = false,
}) {
  const colorMap = {
    burnt: {
      border: 'border-burnt/25',
      glow: 'shadow-burnt/10',
      iconBg: 'bg-burnt/15 text-burnt-light border-burnt/30',
      badge: 'bg-burnt/15 text-burnt-light border-burnt/30',
    },
    amber: {
      border: 'border-amber/25',
      glow: 'shadow-amber/10',
      iconBg: 'bg-amber/15 text-amber-light border-amber/30',
      badge: 'bg-amber/15 text-amber-light border-amber/30',
    },
    lavender: {
      border: 'border-lavender/25',
      glow: 'shadow-lavender/10',
      iconBg: 'bg-lavender/15 text-lavender-light border-lavender/30',
      badge: 'bg-lavender/15 text-lavender-light border-lavender/30',
    },
    emerald: {
      border: 'border-emerald-500/25',
      glow: 'shadow-emerald-500/10',
      iconBg: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
      badge: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    },
    rose: {
      border: 'border-rose-500/25',
      glow: 'shadow-rose-500/10',
      iconBg: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
      badge: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
    },
  };

  const scheme = colorMap[color] || colorMap.burnt;

  return (
    <motion.div
      whileHover={{ y: -3, transition: { duration: 0.2 } }}
      className={`glass-card rounded-2xl p-5 border ${scheme.border} shadow-lg ${scheme.glow} relative overflow-hidden group ${className}`}
    >
      {/* Top subtle ambient highlight */}
      <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-ivory/15 to-transparent" />

      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-mutedgrey">
            {title}
          </p>
          <div className="mt-2 flex items-baseline gap-3">
            <span className="text-3xl font-extrabold text-ivory tracking-tight">
              {value}
            </span>
            {trend !== undefined && (
              <span
                className={`text-[11px] font-mono font-bold px-2 py-0.5 rounded-full border ${
                  trend >= 0
                    ? 'bg-emerald-950/60 text-emerald-400 border-emerald-500/30'
                    : 'bg-rose-950/60 text-rose-400 border-rose-500/30'
                }`}
              >
                {trend >= 0 ? `+${trend}%` : `${trend}%`}
              </span>
            )}
          </div>
        </div>

        {Icon && (
          <div className={`p-3 rounded-xl border ${scheme.iconBg} shadow-sm group-hover:scale-105 transition-transform duration-200`}>
            <Icon className="w-5 h-5" />
          </div>
        )}
      </div>

      {subtitle && (
        <p className="mt-2 text-xs text-mutedgrey/80 line-clamp-1">{subtitle}</p>
      )}

      {/* Decorative background flare */}
      <div className="absolute -bottom-6 -right-6 w-20 h-20 rounded-full bg-ivory/[0.02] blur-xl pointer-events-none group-hover:bg-burnt/10 transition-colors" />
    </motion.div>
  );
}
