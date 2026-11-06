import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  AudioWaveform,
  Lock,
  Mail,
  ArrowRight,
  Eye,
  EyeOff,
  Sparkles,
  Radio,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import VoiceOrb from '../../components/common/VoiceOrb';
import WaveformVisualizer from '../../components/common/WaveformVisualizer';

export default function Login() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState('admin@vattara.com');
  const [password, setPassword] = useState('Admin@123');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login({ email, password });
      navigate('/');
    } catch (err) {
      setError(
        err.response?.data?.detail || 'Authentication failed. Please verify your credentials.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleFillDemo = () => {
    setEmail('admin@vattara.com');
    setPassword('Admin@123');
  };

  return (
    <div className="min-h-screen bg-warmblack text-ivory flex flex-col lg:flex-row relative overflow-hidden bg-mesh-pattern">
      {/* Background ambient lighting */}
      <div className="absolute top-[-10%] left-[-10%] w-[500px] h-[500px] bg-burnt/[0.08] rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[500px] h-[500px] bg-amber/[0.06] rounded-full blur-[140px] pointer-events-none" />

      {/* LEFT SIDE: Immersive AI Voice Experience & 3D Glowing Orb */}
      <div className="lg:w-7/12 relative flex flex-col justify-between p-8 sm:p-12 lg:p-16 border-b lg:border-b-0 lg:border-r border-ivory/10">
        {/* Brand identity */}
        <div className="relative z-10 flex items-center gap-3">
          <div className="w-11 h-11 rounded-2xl bg-gradient-to-tr from-burnt to-amber flex items-center justify-center text-warmblack shadow-xl shadow-burnt/30">
            <AudioWaveform className="w-6 h-6 animate-pulse" />
          </div>
          <div>
            <h1 className="text-xl font-extrabold tracking-tight text-ivory">VATTARA</h1>
            <p className="text-[10px] font-mono uppercase tracking-widest text-amber font-bold">
              Autonomous Voice Receptionist
            </p>
          </div>
        </div>

        {/* Centerpiece: Glowing 3D Voice Orb with floating soundwaves */}
        <div className="my-auto py-12 flex flex-col items-center justify-center relative z-10">
          <VoiceOrb size="xl" isSpeaking={true} />

          <div className="mt-8 text-center max-w-md">
            <motion.div
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
            >
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-mono uppercase font-bold tracking-widest text-burnt-light bg-burnt/15 border border-burnt/30 mb-4">
                <Radio className="w-3 h-3 text-burnt animate-pulse" /> Neural Voice Gateway Active
              </span>
              <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-ivory">
                Calls answered with human warmth, powered by AI.
              </h2>
              <p className="mt-3 text-sm text-mutedgrey leading-relaxed">
                Hospital, clinic, hotel, salon and automotive reception automated with sub-500ms conversational intelligence.
              </p>
            </motion.div>

            {/* Audio Waveform visualizer */}
            <div className="mt-6 flex justify-center">
              <WaveformVisualizer barCount={36} height={36} color="burnt" isPlaying={true} />
            </div>
          </div>
        </div>

        {/* Bottom feature badges */}
        <div className="relative z-10 flex flex-wrap items-center justify-center lg:justify-start gap-4 text-xs text-mutedgrey font-mono">
          <span className="flex items-center gap-1.5 bg-graphite/60 px-3 py-1.5 rounded-xl border border-ivory/5">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> Multi-Tenant Architecture
          </span>
          <span className="flex items-center gap-1.5 bg-graphite/60 px-3 py-1.5 rounded-xl border border-ivory/5">
            <Sparkles className="w-3.5 h-3.5 text-amber" /> 6 Natural Speech Personas
          </span>
          <span className="flex items-center gap-1.5 bg-graphite/60 px-3 py-1.5 rounded-xl border border-ivory/5">
            <Radio className="w-3.5 h-3.5 text-lavender" /> Realtime Audio Transcripts
          </span>
        </div>
      </div>

      {/* RIGHT SIDE: Minimalist Premium Sign In Console */}
      <div className="lg:w-5/12 flex items-center justify-center p-8 sm:p-12 lg:p-16 relative z-10">
        <motion.div
          initial={{ opacity: 0, x: 25 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5 }}
          className="w-full max-w-md space-y-6"
        >
          {/* Header */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-amber">
                Console Access
              </span>
              {/* Quick Fill Demo Button */}
              <button
                type="button"
                onClick={handleFillDemo}
                className="text-[11px] font-mono px-2.5 py-1 rounded-lg bg-amber/10 border border-amber/30 text-amber hover:bg-amber/20 transition-colors"
                title="Autofill standard demo credentials"
              >
                Auto-fill Demo
              </button>
            </div>
            <h3 className="text-2xl font-extrabold text-ivory tracking-tight">Sign in to your portal</h3>
            <p className="text-xs text-mutedgrey mt-1">
              Enter your organizational credentials to manage voice reception and appointments.
            </p>
          </div>

          {error && (
            <div className="p-3.5 rounded-2xl bg-rose-950/40 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2.5">
              <AlertCircle className="w-4 h-4 flex-shrink-0 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1.5">
                Work Email
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-mutedgrey absolute left-3.5 top-3.5" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full pl-10 pr-4 py-3 glass-input rounded-xl text-xs font-medium focus:ring-1 focus:ring-burnt"
                  placeholder="admin@vattara.com"
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey">
                  Password
                </label>
                <Link
                  to="/forgot-password"
                  className="text-xs text-burnt-light hover:text-burnt transition-colors font-medium"
                >
                  Forgot password?
                </Link>
              </div>
              <div className="relative">
                <Lock className="w-4 h-4 text-mutedgrey absolute left-3.5 top-3.5" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full pl-10 pr-10 py-3 glass-input rounded-xl text-xs font-medium focus:ring-1 focus:ring-burnt"
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3.5 top-3.5 text-mutedgrey hover:text-ivory"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full relative group overflow-hidden flex items-center justify-center gap-2 py-3.5 px-4 rounded-xl bg-gradient-to-r from-burnt via-burnt to-amber text-warmblack font-extrabold text-xs shadow-xl shadow-burnt/25 hover:shadow-burnt/40 transition-all duration-200 disabled:opacity-50 tracking-wider uppercase"
            >
              <span>{loading ? 'Authenticating...' : 'Enter Platform Console'}</span>
              <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
            </button>
          </form>

          {/* Footer switcher */}
          <div className="pt-4 border-t border-ivory/10 text-center text-xs text-mutedgrey">
            Deploying for a new hospital, salon, or service centre?{' '}
            <Link
              to="/register"
              className="font-bold text-amber hover:text-amber-light underline underline-offset-4"
            >
              Register business
            </Link>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
