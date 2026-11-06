import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { AudioWaveform, Mail, ArrowLeft, CheckCircle2, ShieldCheck, KeyRound } from 'lucide-react';
import { authService } from '../../services/api';

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      await authService.forgotPassword(email);
      setSubmitted(true);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to dispatch reset email.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-warmblack text-ivory flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8 relative overflow-hidden bg-mesh-pattern">
      <div className="absolute top-1/4 left-1/3 w-96 h-96 bg-burnt/[0.05] rounded-full blur-[140px] pointer-events-none" />

      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center relative z-10">
        <motion.div
          animate={{ scale: [1, 1.05, 1], rotate: [0, 2, -2, 0] }}
          transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut' }}
          className="inline-flex w-16 h-16 rounded-3xl bg-gradient-to-tr from-burnt to-amber items-center justify-center text-warmblack shadow-xl shadow-burnt/30 mb-4"
        >
          <ShieldCheck className="w-8 h-8" />
        </motion.div>
        <h2 className="text-2xl font-extrabold text-ivory tracking-tight">Account Recovery</h2>
        <p className="mt-1 text-xs text-mutedgrey">
          Enter your authorized administrator email to receive cryptographic password reset credentials.
        </p>
      </div>

      <div className="mt-6 sm:mx-auto sm:w-full sm:max-w-md relative z-10">
        <div className="glass-panel-glow py-8 px-6 sm:px-10 rounded-3xl shadow-2xl border border-ivory/10">
          {submitted ? (
            <div className="text-center py-4 space-y-4">
              <div className="w-12 h-12 rounded-2xl bg-emerald-950/60 border border-emerald-500/30 text-emerald-400 flex items-center justify-center mx-auto">
                <CheckCircle2 className="w-6 h-6" />
              </div>

              <div>
                <h3 className="text-base font-bold text-ivory">Reset Instructions Dispatched</h3>
                <p className="text-xs text-mutedgrey mt-1 leading-relaxed">
                  We've transmitted reset verification instructions to{' '}
                  <span className="text-amber font-mono font-bold">{email}</span>.
                </p>
              </div>

              <div className="pt-2">
                <Link
                  to="/login"
                  className="inline-flex items-center gap-2 text-xs font-mono font-bold uppercase tracking-wider text-burnt-light hover:text-burnt transition-colors"
                >
                  <ArrowLeft className="w-4 h-4" /> Return to Sign In
                </Link>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="p-3.5 rounded-2xl bg-rose-950/40 border border-rose-500/30 text-rose-300 text-xs">
                  {error}
                </div>
              )}

              <div>
                <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1.5">
                  Account Email Address
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

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3.5 rounded-xl bg-gradient-to-r from-burnt to-amber text-warmblack font-extrabold text-xs uppercase tracking-wider shadow-lg shadow-burnt/25 hover:shadow-burnt/40 transition-all disabled:opacity-50"
              >
                {loading ? 'Transmitting Key...' : 'Send Recovery Credentials'}
              </button>

              <div className="text-center pt-2">
                <Link
                  to="/login"
                  className="inline-flex items-center gap-1.5 text-xs text-mutedgrey hover:text-ivory font-medium transition-colors"
                >
                  <ArrowLeft className="w-3.5 h-3.5" /> Back to Console Login
                </Link>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
