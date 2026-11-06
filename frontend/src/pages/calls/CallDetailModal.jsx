import React, { useState } from 'react';
import { motion } from 'framer-motion';
import {
  Play,
  Pause,
  PhoneCall,
  Calendar,
  Clock,
  User,
  Phone,
  FileText,
  CheckCircle2,
  Sparkles,
  Share2,
  CalendarPlus,
} from 'lucide-react';
import Modal from '../../components/common/Modal';
import Badge from '../../components/common/Badge';
import WaveformVisualizer from '../../components/common/WaveformVisualizer';

export default function CallDetailModal({ isOpen, onClose, call, onScheduleFollowup }) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(35);

  if (!call) return null;

  const toggleAudio = () => {
    setIsPlaying(!isPlaying);
  };

  const minutes = Math.floor(call.duration_seconds / 60);
  const seconds = call.duration_seconds % 60;
  const formattedDuration = `${minutes}m ${seconds}s`;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Neural Telemetry & Call Transcript" maxWidth="max-w-3xl">
      <div className="space-y-6 text-ivory">
        {/* Top Meta Console */}
        <div className="p-5 rounded-3xl glass-card border border-ivory/10 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2 mb-1.5">
                <Badge status={call.call_type} text={`${call.call_type} Call`} />
                <Badge status={call.status} />
                <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded-full border border-emerald-500/30 font-bold">
                  98% Sentiment Positive
                </span>
              </div>
              <h3 className="text-lg font-extrabold text-ivory">
                {call.caller_name || 'Verified Caller'}
              </h3>
              <p className="text-xs font-mono text-amber">{call.caller_phone}</p>
            </div>

            <div className="text-right text-xs text-mutedgrey font-mono">
              <span className="block font-bold text-ivory">
                {new Date(call.initiated_at).toLocaleDateString([], {
                  weekday: 'short',
                  month: 'short',
                  day: 'numeric',
                })}
              </span>
              <span className="block text-[11px]">
                {new Date(call.initiated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
          </div>

          {/* Interactive Audio Player Bar */}
          <div className="p-4 rounded-2xl bg-charcoal border border-ivory/10 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <button
                  onClick={toggleAudio}
                  className="w-10 h-10 rounded-xl bg-gradient-to-tr from-burnt to-amber text-warmblack flex items-center justify-center shadow-lg shadow-burnt/25 hover:scale-105 transition-all"
                >
                  {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5 ml-0.5" />}
                </button>
                <div>
                  <span className="text-xs font-bold text-ivory block">
                    {isPlaying ? 'Streaming Audio Recording' : 'Synthesized Call Recording'}
                  </span>
                  <span className="text-[10px] font-mono text-mutedgrey">
                    PSTN High-Fidelity Audio • {formattedDuration}
                  </span>
                </div>
              </div>

              <WaveformVisualizer barCount={20} height={24} color="amber" isPlaying={isPlaying} />
            </div>

            {/* Scrubber simulation */}
            <div className="space-y-1">
              <div className="w-full h-1.5 rounded-full bg-graphite overflow-hidden cursor-pointer">
                <div
                  className="h-full bg-gradient-to-r from-burnt to-amber"
                  style={{ width: `${isPlaying ? '68%' : '35%'}` }}
                />
              </div>
              <div className="flex justify-between text-[10px] font-mono text-mutedgrey">
                <span>00:48</span>
                <span>{formattedDuration}</span>
              </div>
            </div>
          </div>
        </div>

        {/* AI Key Insights & Summary */}
        {call.summary && (
          <div className="space-y-2">
            <h4 className="text-xs font-mono font-bold uppercase tracking-wider text-amber flex items-center gap-1.5">
              <Sparkles className="w-4 h-4 text-amber" /> AI Diagnostic Summary
            </h4>
            <div className="p-4 rounded-2xl glass-card border border-ivory/10 text-xs text-ivory/90 leading-relaxed font-sans">
              {call.summary}
            </div>
          </div>
        )}

        {/* Timestamped Transcript */}
        <div className="space-y-2">
          <h4 className="text-xs font-mono font-bold uppercase tracking-wider text-mutedgrey flex items-center gap-1.5">
            <FileText className="w-4 h-4 text-burnt" /> Conversational Transcript
          </h4>
          <div className="p-5 rounded-2xl bg-charcoal border border-ivory/10 space-y-3 max-h-64 overflow-y-auto font-mono text-xs">
            {call.transcript ? (
              call.transcript.split('\n').map((line, idx) => {
                const isAi = line.startsWith('AI:');
                return (
                  <div
                    key={idx}
                    className={`p-2.5 rounded-xl ${
                      isAi ? 'bg-burnt/10 border border-burnt/20 text-burnt-light' : 'bg-graphite text-ivory'
                    }`}
                  >
                    <span className="font-bold uppercase tracking-wider text-[10px] block opacity-70 mb-0.5">
                      {isAi ? '🤖 Vattara AI Voice Agent' : '👤 Caller'}
                    </span>
                    {line.replace(/^AI:|^Caller:/, '').trim()}
                  </div>
                );
              })
            ) : (
              <p className="text-mutedgrey italic">No audio transcript generated for this missed call.</p>
            )}
          </div>
        </div>

        {/* Modal actions */}
        <div className="pt-2 flex items-center justify-between border-t border-ivory/10">
          <span className="text-[11px] font-mono text-mutedgrey">
            Record ID: <span className="text-ivory">{call.id}</span>
          </span>

          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="px-5 py-2.5 rounded-xl glass-card text-mutedgrey hover:text-ivory text-xs font-semibold"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
