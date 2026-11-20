import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Radio,
  PhoneCall,
  CheckCircle2,
  XCircle,
  Copy,
  Check,
  ShieldCheck,
  Zap,
  RefreshCw,
  Save,
  Server,
  Globe,
  Lock,
  ArrowUpRight,
  ExternalLink,
} from 'lucide-react';
import { integrationsService } from '../../services/api';
import confetti from 'canvas-confetti';

export default function Integrations() {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [copiedWebhook, setCopiedWebhook] = useState(false);
  const [toast, setToast] = useState('');

  const loadSettings = async () => {
    setLoading(true);
    try {
      const data = await integrationsService.getSettings();
      setSettings(data);
    } catch (err) {
      console.error('Failed to load integration settings:', err);
      setSettings({
        primary_provider: 'plivo',
        plivo_auth_id_masked: null,
        plivo_phone_number: null,
        is_plivo_verified: false,
        inbound_webhook_url: '/api/v1/plivo/incoming',
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSettings();
  }, []);

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(''), 4000);
  };

  const handleCopyWebhook = () => {
    if (!settings?.inbound_webhook_url) return;
    navigator.clipboard.writeText(settings.inbound_webhook_url);
    setCopiedWebhook(true);
    setTimeout(() => setCopiedWebhook(false), 2000);
  };

  const handleTestConnection = async () => {
    setTesting(true);
    try {
      const res = await integrationsService.testConnection({ provider: 'plivo' });
      setTestResult(res);
      if (res.status === 'connected') {
        confetti({
          particleCount: 30,
          spread: 50,
          origin: { y: 0.6 },
          colors: ['#E47745', '#10B981'],
        });
      }
      showToast(`Plivo trunk test: ${res.status}`);
    } catch (err) {
      console.error(err);
      setTestResult({ status: 'failed', message: 'Connection ping failed or timeout.' });
      showToast('Failed to test Plivo trunk connection.');
    } finally {
      setTesting(false);
    }
  };

  const handleSaveSettings = async (e) => {
    e?.preventDefault();
    setSaving(true);
    try {
      await integrationsService.updateSettings({
        primary_provider: 'plivo',
        plivo_auth_id: settings.plivo_auth_id,
        plivo_phone_number: settings.plivo_phone_number,
      });
      showToast('Plivo telephony credentials updated successfully!');
      await loadSettings();
    } catch (err) {
      console.error(err);
      showToast('Failed to save integration settings.');
    } finally {
      setSaving(false);
    }
  };

  if (loading || !settings) {
    return (
      <div className="flex flex-col items-center justify-center py-32 space-y-4">
        <div className="w-12 h-12 border-3 border-burnt border-t-transparent rounded-full animate-spin" />
        <p className="text-xs text-mutedgrey animate-pulse font-mono tracking-wider">
          QUERYING PLIVO TELEPHONY INTEGRATION STATUS...
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-12 max-w-6xl">
      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 bg-charcoal border border-burnt/40 text-ivory text-xs font-semibold px-5 py-3 rounded-2xl shadow-2xl flex items-center gap-2.5 backdrop-blur-md">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>{toast}</span>
        </div>
      )}

      {/* Hero Header */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-charcoal via-graphite to-warmblack border border-white/10 p-6 sm:p-8">
        <div className="absolute top-0 right-0 w-96 h-96 bg-burnt/10 rounded-full blur-3xl pointer-events-none -mr-20 -mt-20" />
        <div className="absolute bottom-0 left-1/4 w-72 h-72 bg-lavender/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <span className="p-2.5 rounded-xl bg-burnt/15 border border-burnt/30 text-burnt">
                <Radio className="w-5 h-5 animate-pulse" />
              </span>
              <span className="text-xs font-semibold tracking-wider uppercase text-burnt">
                Telephony Gateway Orchestration
              </span>
              <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-emerald-500/15 border border-emerald-500/30 text-emerald-400">
                <ShieldCheck className="w-3 h-3" /> Encrypted Secrets
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-ivory tracking-tight">
              Plivo Telephony & Audio Streaming
            </h1>
            <p className="text-xs sm:text-sm text-mutedgrey max-w-2xl">
              Plivo Programmable Voice is your exclusive carrier trunk for bidirectional 8kHz μ-law WebSocket streaming,
              instant appointment confirmations, and automated reminder calling.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleSaveSettings}
              disabled={saving}
              className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-burnt to-amber text-warmblack font-bold text-xs flex items-center gap-2 shadow-lg shadow-burnt/20 hover:scale-[1.02] active:scale-[0.98] transition-all disabled:opacity-50"
            >
              <Save className="w-4 h-4" />
              {saving ? 'Saving...' : 'Deploy Credentials'}
            </button>
          </div>
        </div>
      </div>

      {/* Primary Gateway Status Card */}
      <div className="glass-panel p-6 sm:p-7 rounded-3xl border border-graphite space-y-4">
        <div>
          <span className="text-[10px] font-mono uppercase font-bold tracking-wider text-burnt">
            Exclusive Telephony Carrier
          </span>
          <h3 className="text-base font-bold text-ivory">Plivo Programmable Voice Trunk</h3>
          <p className="text-xs text-mutedgrey mt-0.5">
            All inbound receptionist calls and automated reminder dispatches route exclusively through Plivo.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
          <div className="p-4 rounded-2xl border bg-burnt/15 border-burnt ring-1 ring-burnt shadow-md shadow-burnt/10 flex flex-col justify-between space-y-2">
            <div className="flex items-start justify-between">
              <div>
                <h4 className="text-xs font-bold text-ivory">Plivo Voice Trunk</h4>
                <p className="text-[11px] text-mutedgrey mt-0.5">Primary Indian PSTN • 8kHz μ-law Streaming</p>
              </div>
              <span className="w-2.5 h-2.5 rounded-full bg-burnt animate-pulse" />
            </div>
            <div className="flex items-center justify-between text-[10px] font-mono pt-2 border-t border-white/5">
              <span className="text-mutedgrey">Trunk Status:</span>
              <span className={settings.is_plivo_verified ? 'text-emerald-400 font-bold' : 'text-amber font-bold'}>
                {settings.is_plivo_verified ? 'Verified & Connected' : 'Configuration Pending'}
              </span>
            </div>
          </div>

          <div className="p-4 rounded-2xl border glass-card border-white/5 flex flex-col justify-between space-y-2">
            <div>
              <h4 className="text-xs font-bold text-ivory">Inbound Direct DID</h4>
              <p className="text-[11px] font-mono text-mutedgrey mt-0.5">
                {settings.plivo_phone_number || 'Not configured in tenant'}
              </p>
            </div>
            <div className="text-[10px] font-mono text-mutedgrey pt-2 border-t border-white/5">
              Receives customer incoming voice traffic
            </div>
          </div>

          <div className="p-4 rounded-2xl border glass-card border-white/5 flex flex-col justify-between space-y-2">
            <div>
              <h4 className="text-xs font-bold text-ivory">Auth ID</h4>
              <p className="text-[11px] font-mono text-mutedgrey mt-0.5">
                {settings.plivo_auth_id_masked || 'Not configured'}
              </p>
            </div>
            <div className="text-[10px] font-mono text-mutedgrey pt-2 border-t border-white/5">
              Authenticated via HTTP Basic HMAC
            </div>
          </div>
        </div>
      </div>

      {/* Inbound Webhook URL Display */}
      <div className="glass-panel p-6 rounded-3xl border border-graphite space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-ivory flex items-center gap-2">
              <Globe className="w-4 h-4 text-amber" /> Inbound Voice Webhook URL (Answer URL)
            </h3>
            <p className="text-xs text-mutedgrey mt-0.5">
              Paste this URL into your Plivo Console (Applications &gt; Primary XML Application &gt; Answer URL) as an HTTP POST webhook.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <input
            type="text"
            readOnly
            value={settings.inbound_webhook_url || ''}
            className="glass-input flex-1 font-mono text-xs text-ivory bg-warmblack/50"
          />
          <button
            onClick={handleCopyWebhook}
            className="px-4 py-2.5 rounded-xl bg-warmblack hover:bg-graphite border border-graphite text-xs font-semibold text-ivory flex items-center gap-1.5 transition-colors"
          >
            {copiedWebhook ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-400" /> Copied
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5" /> Copy URL
              </>
            )}
          </button>
        </div>
      </div>

      {/* Plivo Configuration & Trunk Test Card */}
      <div className="glass-panel p-6 rounded-3xl border border-graphite space-y-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="p-2 rounded-xl bg-burnt/15 text-burnt border border-burnt/30">
              <Radio className="w-4 h-4" />
            </span>
            <div>
              <h3 className="text-sm font-bold text-ivory">Plivo Programmable Voice Credentials</h3>
              <span className="text-[10px] font-mono text-mutedgrey">Live PSTN Connectivity & WebSocket Engine</span>
            </div>
          </div>

          <button
            onClick={handleTestConnection}
            disabled={testing}
            className="px-4 py-2 rounded-xl bg-graphite hover:bg-burnt/20 hover:text-burnt text-ivory border border-white/10 text-xs font-semibold transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${testing ? 'animate-spin' : ''}`} />
            {testing ? 'Testing Trunk...' : 'Ping Live Trunk'}
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
              Auth ID
            </label>
            <input
              type="text"
              value={settings.plivo_auth_id || settings.plivo_auth_id_masked || ''}
              onChange={(e) => setSettings({ ...settings, plivo_auth_id: e.target.value })}
              className="glass-input w-full font-mono text-xs"
              placeholder="MAMOCK••••••••••••••••••••"
            />
          </div>

          <div>
            <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
              Virtual Phone Number (DID)
            </label>
            <input
              type="text"
              value={settings.plivo_phone_number || ''}
              onChange={(e) => setSettings({ ...settings, plivo_phone_number: e.target.value })}
              className="glass-input w-full font-mono text-xs"
              placeholder="+918040001234"
            />
          </div>
        </div>

        {testResult && (
          <div
            className={`p-3 rounded-2xl text-xs flex items-center justify-between ${
              testResult.status === 'connected'
                ? 'bg-emerald-950/40 text-emerald-300 border border-emerald-500/30'
                : 'bg-rose-950/40 text-rose-300 border border-rose-500/30'
            }`}
          >
            <span>{testResult.message}</span>
            {testResult.latency_ms > 0 && (
              <span className="font-mono text-[10px] font-bold">{testResult.latency_ms}ms round-trip</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
