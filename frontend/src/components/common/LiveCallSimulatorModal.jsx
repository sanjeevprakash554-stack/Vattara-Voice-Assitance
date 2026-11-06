import React, { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Phone,
  PhoneCall,
  PhoneOff,
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Sparkles,
  CheckCircle2,
  Clock,
  User,
  Radio,
  Send,
  MessageSquare,
} from 'lucide-react';
import VoiceOrb from './VoiceOrb';
import WaveformVisualizer from './WaveformVisualizer';
import confetti from 'canvas-confetti';
import { callsService } from '../../services/api';

const SAMPLE_DIALOG_FLOW = [
  {
    role: 'assistant',
    text: 'Hello and welcome to Vattara Health & Diagnostics. I am Maya, your AI voice assistant. How may I assist your appointment or inquiry today?',
  },
  {
    role: 'caller',
    text: 'Hi Maya, I need to book a general health consultation for tomorrow morning if possible.',
  },
  {
    role: 'assistant',
    text: 'I can certainly help you with that! We have an opening tomorrow with Dr. Ramanathan at 10:30 AM, or with Dr. Sarah Mitchell at 11:15 AM. Which one would you prefer?',
  },
  {
    role: 'caller',
    text: '10:30 AM with Dr. Ramanathan sounds perfect.',
  },
  {
    role: 'assistant',
    text: 'Wonderful. I have reserved 10:30 AM tomorrow for Dr. Ramanathan. I have confirmed your slot and sent an SMS reminder to your number. Is there anything else I can assist you with?',
  },
  {
    role: 'caller',
    text: 'No, that is all. Thank you very much!',
  },
  {
    role: 'assistant',
    text: 'You are most welcome! Have a wonderful day ahead. Goodbye!',
  },
];

export default function LiveCallSimulatorModal({ isOpen, onClose, onCallCompleted }) {
  const [callState, setCallState] = useState('ringing'); // 'ringing' | 'connected' | 'ended'
  const [callSeconds, setCallSeconds] = useState(0);
  const [dialogStep, setDialogStep] = useState(0);
  const [dialogHistory, setDialogHistory] = useState([]);
  const [isMuted, setIsMuted] = useState(false);
  const [voiceOrbState, setVoiceOrbState] = useState('idle'); // 'idle' | 'listening' | 'speaking'
  const [customInput, setCustomInput] = useState('');
  const timerRef = useRef(null);
  const chatBottomRef = useRef(null);

  // Sound synthesis utility
  const speakText = (text) => {
    if (isMuted || !('speechSynthesis' in window)) return;
    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.05;
      utterance.pitch = 1.0;
      utterance.onstart = () => setVoiceOrbState('speaking');
      utterance.onend = () => setVoiceOrbState('listening');
      window.speechSynthesis.speak(utterance);
    } catch (e) {
      console.warn('SpeechSynthesis error:', e);
    }
  };

  // Start call session
  const handleAnswerCall = () => {
    setCallState('connected');
    setCallSeconds(0);
    const initialMsg = SAMPLE_DIALOG_FLOW[0];
    setDialogHistory([initialMsg]);
    setDialogStep(1);
    speakText(initialMsg.text);

    timerRef.current = setInterval(() => {
      setCallSeconds((prev) => prev + 1);
    }, 1000);
  };

  // Advance dialog
  const handleNextTurn = (overrideText = null) => {
    if (dialogStep >= SAMPLE_DIALOG_FLOW.length && !overrideText) return;

    let callerMsg;
    if (overrideText) {
      callerMsg = { role: 'caller', text: overrideText };
    } else {
      callerMsg = SAMPLE_DIALOG_FLOW[dialogStep];
    }

    setDialogHistory((prev) => [...prev, callerMsg]);
    setVoiceOrbState('listening');

    setTimeout(() => {
      let aiResponse;
      if (overrideText) {
        aiResponse = {
          role: 'assistant',
          text: `Understood! I have processed your request for "${overrideText}". Your appointment schedule has been updated accordingly.`,
        };
      } else if (dialogStep + 1 < SAMPLE_DIALOG_FLOW.length) {
        aiResponse = SAMPLE_DIALOG_FLOW[dialogStep + 1];
      }

      if (aiResponse) {
        setDialogHistory((prev) => [...prev, aiResponse]);
        speakText(aiResponse.text);
      }

      setDialogStep((prev) => prev + 2);
    }, 1200);
  };

  const handleEndCall = async () => {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    clearInterval(timerRef.current);
    setCallState('ended');

    confetti({
      particleCount: 50,
      spread: 60,
      origin: { y: 0.6 },
      colors: ['#E47745', '#F0AD57', '#A78BFA'],
    });

    try {
      const saved = await callsService.simulateCall({
        caller_name: 'Dr. T. Ramanathan',
        caller_phone: '+91 98409 77881',
        call_type: 'incoming',
        duration_seconds: Math.max(12, callSeconds),
        status: 'completed',
        summary: 'Successful appointment booking for tomorrow 10:30 AM via AI Voice Receptionist.',
      });
      if (onCallCompleted) onCallCompleted(saved);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [dialogHistory]);

  useEffect(() => {
    if (!isOpen) {
      if ('speechSynthesis' in window) window.speechSynthesis.cancel();
      clearInterval(timerRef.current);
      setCallState('ringing');
      setCallSeconds(0);
      setDialogHistory([]);
      setDialogStep(0);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const minutes = Math.floor(callSeconds / 60);
  const seconds = callSeconds % 60;
  const timeFormatted = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;

  return createPortal(
    <div className="fixed inset-0 z-[100] overflow-y-auto bg-warmblack/80 backdrop-blur-md flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="relative w-full max-w-2xl bg-charcoal border border-graphite rounded-3xl shadow-2xl overflow-hidden"
      >
        {/* Glow ambient backgrounds */}
        <div className="absolute top-0 right-0 w-80 h-80 bg-burnt/10 rounded-full blur-3xl pointer-events-none -mr-16 -mt-16" />
        <div className="absolute bottom-0 left-0 w-80 h-80 bg-amber/10 rounded-full blur-3xl pointer-events-none -ml-16 -mb-16" />

        {/* Modal Top Ribbon */}
        <div className="relative z-10 px-6 py-4 border-b border-graphite bg-warmblack/60 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="p-2 rounded-xl bg-burnt/15 border border-burnt/30 text-burnt">
              <Radio className="w-4 h-4 animate-pulse" />
            </span>
            <div>
              <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-burnt">
                Neural Telephony Simulation
              </span>
              <h3 className="text-sm font-bold text-ivory">Interactive Inbound Call Sandbox</h3>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsMuted(!isMuted)}
              className="p-2 rounded-xl bg-warmblack border border-graphite text-mutedgrey hover:text-ivory transition-colors"
              title={isMuted ? 'Unmute Audio' : 'Mute Audio'}
            >
              {isMuted ? <VolumeX className="w-4 h-4 text-rose-400" /> : <Volume2 className="w-4 h-4 text-burnt" />}
            </button>
            <button
              onClick={onClose}
              className="p-2 rounded-xl bg-warmblack border border-graphite text-mutedgrey hover:text-ivory transition-colors"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Modal Content */}
        <div className="relative z-10 p-6 space-y-6">
          {callState === 'ringing' ? (
            /* Ringing Screen */
            <div className="py-12 flex flex-col items-center justify-center text-center space-y-6">
              <div className="relative">
                <div className="w-24 h-24 rounded-full bg-burnt/20 border-2 border-burnt flex items-center justify-center animate-ping absolute inset-0" />
                <div className="relative w-24 h-24 rounded-full bg-gradient-to-tr from-burnt to-amber flex items-center justify-center text-warmblack shadow-xl shadow-burnt/30">
                  <PhoneCall className="w-10 h-10 animate-bounce" />
                </div>
              </div>

              <div>
                <span className="text-xs font-mono font-bold uppercase tracking-widest text-burnt">
                  Incoming Neural Call
                </span>
                <h2 className="text-2xl font-extrabold text-ivory mt-1">Dr. T. Ramanathan</h2>
                <p className="text-xs font-mono text-mutedgrey mt-0.5">+91 98409 77881 • Clinic Patient</p>
              </div>

              <div className="flex items-center gap-4 pt-4">
                <button
                  onClick={onClose}
                  className="px-6 py-3 rounded-2xl bg-warmblack hover:bg-rose-500/20 border border-rose-500/30 text-rose-400 font-bold text-xs flex items-center gap-2 transition-all"
                >
                  <PhoneOff className="w-4 h-4" /> Decline
                </button>

                <button
                  onClick={handleAnswerCall}
                  className="px-8 py-3 rounded-2xl bg-gradient-to-r from-burnt to-amber hover:from-burnt/90 hover:to-amber/90 text-warmblack font-extrabold text-xs flex items-center gap-2 shadow-xl shadow-burnt/25 hover:scale-105 active:scale-95 transition-all"
                >
                  <Phone className="w-4 h-4" /> Accept Call
                </button>
              </div>
            </div>
          ) : callState === 'connected' ? (
            /* Active Call Screen */
            <div className="space-y-6">
              {/* Call Header with Orb and Timer */}
              <div className="p-4 rounded-2xl bg-warmblack/70 border border-graphite flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <VoiceOrb state={voiceOrbState} size="sm" />
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="text-sm font-bold text-ivory">Maya • Vattara AI Voice</h4>
                      <span className="px-2 py-0.5 rounded-full text-[9px] font-mono font-bold uppercase bg-emerald-500/15 border border-emerald-500/30 text-emerald-400">
                        HD Codec Live
                      </span>
                    </div>
                    <p className="text-xs font-mono text-mutedgrey capitalize">
                      State: <span className="text-burnt">{voiceOrbState}</span>
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <span className="px-3 py-1 rounded-xl bg-warmblack border border-white/5 font-mono font-bold text-sm text-ivory">
                    {timeFormatted}
                  </span>

                  <button
                    onClick={handleEndCall}
                    className="p-2.5 rounded-xl bg-rose-500/15 hover:bg-rose-500/30 border border-rose-500/30 text-rose-400 transition-colors"
                    title="End Call"
                  >
                    <PhoneOff className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Dynamic Waveform Visualizer */}
              <div className="py-2 px-4 rounded-2xl bg-warmblack/50 border border-white/5 flex items-center justify-center">
                <WaveformVisualizer isPlaying={voiceOrbState === 'speaking'} bars={36} height={32} />
              </div>

              {/* Real-time Dialog Stream */}
              <div className="max-h-64 overflow-y-auto space-y-3 p-4 rounded-2xl bg-warmblack/60 border border-graphite text-xs">
                {dialogHistory.map((msg, i) => {
                  const isAi = msg.role === 'assistant';
                  return (
                    <motion.div
                      key={i}
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      className={`flex gap-3 ${isAi ? 'justify-start' : 'justify-end'}`}
                    >
                      {isAi && (
                        <div className="w-7 h-7 rounded-xl bg-burnt/15 border border-burnt/30 text-burnt flex items-center justify-center shrink-0 text-[10px] font-mono font-bold">
                          AI
                        </div>
                      )}
                      <div
                        className={`max-w-[80%] p-3 rounded-2xl ${
                          isAi
                            ? 'bg-charcoal border border-white/10 text-ivory'
                            : 'bg-burnt text-warmblack font-semibold'
                        }`}
                      >
                        <p className="leading-relaxed">{msg.text}</p>
                      </div>
                    </motion.div>
                  );
                })}
                <div ref={chatBottomRef} />
              </div>

              {/* Quick Reply Chips or Custom Turn Input */}
              <div className="space-y-3">
                <span className="text-[10px] font-mono uppercase text-mutedgrey font-bold">
                  Simulate Caller Turn:
                </span>
                <div className="flex flex-wrap items-center gap-2">
                  {[
                    '10:30 AM with Dr. Ramanathan is great',
                    'Could we do 4:00 PM in the afternoon instead?',
                    'Can you confirm my appointment location?',
                    'Thank you, Maya, that solves everything!',
                  ].map((preset, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleNextTurn(preset)}
                      className="px-3 py-1.5 rounded-xl bg-warmblack hover:bg-graphite border border-graphite text-ivory text-xs transition-colors"
                    >
                      "{preset}"
                    </button>
                  ))}
                </div>

                <div className="flex items-center gap-2 pt-2">
                  <input
                    type="text"
                    placeholder="Or type a custom caller response..."
                    value={customInput}
                    onChange={(e) => setCustomInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && customInput.trim()) {
                        handleNextTurn(customInput);
                        setCustomInput('');
                      }
                    }}
                    className="glass-input flex-1 py-2 text-xs"
                  />
                  <button
                    onClick={() => {
                      if (customInput.trim()) {
                        handleNextTurn(customInput);
                        setCustomInput('');
                      }
                    }}
                    className="px-4 py-2 rounded-xl bg-burnt text-warmblack font-bold text-xs flex items-center gap-1.5"
                  >
                    <Send className="w-3.5 h-3.5" /> Speak
                  </button>
                </div>
              </div>
            </div>
          ) : (
            /* Ended Screen */
            <div className="py-12 flex flex-col items-center justify-center text-center space-y-4">
              <div className="w-16 h-16 rounded-2xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 flex items-center justify-center">
                <CheckCircle2 className="w-8 h-8" />
              </div>
              <div>
                <h3 className="text-xl font-bold text-ivory">Call Session Completed</h3>
                <p className="text-xs text-mutedgrey mt-1">
                  Duration: {timeFormatted} • Telemetry transcript saved to call history.
                </p>
              </div>

              <button
                onClick={onClose}
                className="px-6 py-2.5 rounded-xl bg-burnt text-warmblack font-bold text-xs shadow-lg shadow-burnt/20 hover:scale-[1.02] transition-all"
              >
                Close Sandbox
              </button>
            </div>
          )}
        </div>
      </motion.div>
    </div>,
    document.body
  );
}

