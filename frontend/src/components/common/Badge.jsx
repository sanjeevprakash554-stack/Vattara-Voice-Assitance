import React from 'react';

export default function Badge({ status, text, className = '' }) {
  const normalized = (status || text || '').toLowerCase();

  let styles = 'bg-graphite text-ivory/80 border-ivory/10';
  let dotColor = 'bg-mutedgrey';

  if (['completed', 'active', 'healthy', 'sent', 'incoming'].includes(normalized)) {
    styles = 'bg-emerald-950/50 text-emerald-300 border-emerald-500/30';
    dotColor = 'bg-emerald-400';
  } else if (['upcoming', 'pending', 'in_progress', 'rescheduled'].includes(normalized)) {
    styles = 'bg-amber/10 text-amber-light border-amber/30';
    dotColor = 'bg-amber';
  } else if (['missed', 'failed', 'cancelled', 'unhealthy', 'inactive'].includes(normalized)) {
    styles = 'bg-rose-950/50 text-rose-300 border-rose-500/30';
    dotColor = 'bg-rose-400';
  } else if (['outgoing', 'manual'].includes(normalized)) {
    styles = 'bg-burnt/10 text-burnt-light border-burnt/30';
    dotColor = 'bg-burnt';
  } else if (['ai_call'].includes(normalized)) {
    styles = 'bg-lavender/10 text-lavender-light border-lavender/30';
    dotColor = 'bg-lavender';
  }

  const displayText = text || status || '';

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium border capitalize backdrop-blur-sm ${styles} ${className}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${dotColor} animate-pulse`} />
      {displayText.replace('_', ' ')}
    </span>
  );
}
