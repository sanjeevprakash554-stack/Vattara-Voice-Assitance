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
  const [testing, setTesting] = useState({});
  const [testResults, setTestResults] = useState({});
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
        plivo_auth_id: 'MAMOCK••••••••12345',
        plivo_phone_number: '+918040001234',
        is_plivo_verified: true,
        twilio_account_sid: 'ACmo••••••••9000',
        twilio_phone_number: '+14155552671',
        is_twilio_verified: true,
        smartflo_caller_id: '918040001234',
        smartflo_api_key: 'tsf_••••••••abcd',
        is_smartflo_verified: true,
        exotel_sid: 'ex_••••••••9999',
        exotel_caller_id: '08088887777',
        is_exotel_verified: false,
        inbound_webhook_url: 'https://api.vattara.com/api/v1/plivo/incoming',
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

  const handleTestConnection = async (provider) => {
    setTesting((prev) => ({ ...prev, [provider]: true }));
    try {
      const res = await integrationsService.testConnection({ provider });
      setTestResults((prev) => ({ ...prev, [provider]: res }));
      if (res.status === 'connected') {
        confetti({
          particleCount: 30,
          spread: 50,
          origin: { y: 0.6 },
          colors: ['#E47745', '#10B981'],
        });
      }
      showToast(`${provider.toUpperCase()} trunk test: ${res.status}`);
    } catch (err) {
      console.error(err);
      setTestResults((prev) => ({
        ...prev,
        [provider]: { status: 'failed', message: 'Connection ping failed or timeout.' },
      }));
      showToast(`Failed to test connection for ${provider}.`);
    } finally {
      setTesting((prev) => ({ ...prev, [provider]: false }));
    }
  };

  const handleSaveSettings = async (e) => {
    e?.preventDefault();
    setSaving(true);
    try {
      await integrationsService.updateSettings({
        primary_provider: settings.primary_provider,
        plivo_auth_id: settings.plivo_auth_id,
        plivo_phone_number: settings.plivo_phone_number,
        twilio_account_sid: settings.twilio_account_sid,
        twilio_phone_number: settings.twilio_phone_number,
        smartflo_caller_id: settings.smartflo_caller_id,
        smartflo_api_key: settings.smartflo_api_key,
        exotel_sid: settings.exotel_sid,
        exotel_caller_id: settings.exotel_caller_id,
      });
      showToast('Telephony integration credentials updated successfully!');
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
          QUERYING TELEPHONY INTEGRATION STATUS...
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
              Telephony Integrations & SIP Trunks
            </h1>
            <p className="text-xs sm:text-sm text-mutedgrey max-w-2xl">
              Configure and test multi-provider PSTN carriers: Twilio Media Streams, Tata Smartflo Enterprise SIP,
              and Exotel. Secrets are stored securely and masked in the UI.
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

      {/* Primary Gateway Selector */}
      <div className="glass-panel p-6 sm:p-7 rounded-3xl border border-graphite space-y-4">
        <div>
          <span className="text-[10px] font-mono uppercase font-bold tracking-wider text-burnt">
            Routing Priority
          </span>
          <h3 className="text-base font-bold text-ivory">Active Primary Telephony Carrier</h3>
          <p className="text-xs text-mutedgrey mt-0.5">
            Incoming phone calls and outbound reminder dispatches default to this telephony provider.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-2">
          {[
            {
              id: 'plivo',
              name: 'Plivo Voice',
              sub: 'Primary Indian PSTN • Bidirectional Audio',
              verified: settings.is_plivo_verified,
            },
            {
              id: 'twilio',
              name: 'Twilio Media Streams',
              sub: 'Full Duplex Streaming • Global Coverage',
              verified: settings.is_twilio_verified,
            },
            {
              id: 'smartflo',
              name: 'Tata Smartflo',
              sub: 'Enterprise Indian SIP Trunk • Low Latency',
              verified: settings.is_smartflo_verified,
            },
            {
              id: 'exotel',
              name: 'Exotel Voice Gateway',
              sub: 'Legacy Indian Telecom Voice API',
              verified: settings.is_exotel_verified,
            },
          ].map((prov) => {
            const isSelected = settings.primary_provider === prov.id;
            return (
              <div
                key={prov.id}
                onClick={() => setSettings({ ...settings, primary_provider: prov.id })}
                className={`p-4 rounded-2xl border cursor-pointer transition-all flex flex-col justify-between space-y-3 ${
                  isSelected
                    ? 'bg-burnt/15 border-burnt ring-1 ring-burnt shadow-md shadow-burnt/10'
                    : 'glass-card border-white/5 hover:border-white/15'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h4 className="text-xs font-bold text-ivory">{prov.name}</h4>
                    <p className="text-[11px] text-mutedgrey mt-0.5">{prov.sub}</p>
                  </div>
                  {isSelected && <span className="w-2.5 h-2.5 rounded-full bg-burnt animate-pulse" />}
                </div>

                <div className="flex items-center justify-between text-[10px] font-mono">
                  <span className="text-mutedgrey">Status:</span>
                  <span className={prov.verified ? 'text-emerald-400 font-bold' : 'text-amber font-bold'}>
                    {prov.verified ? 'Verified Active' : 'Unverified'}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Inbound Webhook URL Display */}
      <div className="glass-panel p-6 rounded-3xl border border-graphite space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-ivory flex items-center gap-2">
              <Globe className="w-4 h-4 text-amber" /> Inbound Voice Webhook URL
            </h3>
            <p className="text-xs text-mutedgrey mt-0.5">
              Paste this URL into your Twilio, Smartflo, or Exotel phone number console as the HTTP POST webhook.
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

      {/* Provider Details & Credential Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Card 1: Plivo Configuration (Primary Indian Telephony) */}
        <div className="glass-panel p-6 rounded-3xl border border-graphite space-y-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <span className="p-2 rounded-xl bg-burnt/15 text-burnt border border-burnt/30">
                <Radio className="w-4 h-4" />
              </span>
              <div>
                <h3 className="text-sm font-bold text-ivory">Plivo Programmable Voice</h3>
                <span className="text-[10px] font-mono text-mutedgrey">Primary India PSTN • 8kHz μ-law WebSocket</span>
              </div>
            </div>

            <button
              onClick={() => handleTestConnection('plivo')}
              disabled={testing.plivo}
              className="px-3 py-1.5 rounded-xl bg-graphite hover:bg-burnt/20 hover:text-burnt text-ivory border border-white/10 text-xs font-semibold transition-colors disabled:opacity-50"
            >
              {testing.plivo ? 'Testing...' : 'Ping Trunk'}
            </button>
          </div>

          <div className="space-y-3">
            <div>
              <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
                Auth ID (Masked)
              </label>
              <input
                type="text"
                value={settings.plivo_auth_id || ''}
                onChange={(e) => setSettings({ ...settings, plivo_auth_id: e.target.value })}
                className="glass-input w-full font-mono text-xs"
                placeholder="MA••••••••••••••••••••••••"
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

          {testResults.plivo && (
            <div className={`p-3 rounded-2xl text-xs flex items-center justify-between ${
              testResults.plivo.status === 'connected'
                ? 'bg-emerald-950/40 text-emerald-300 border border-emerald-500/30'
                : 'bg-rose-950/40 text-rose-300 border border-rose-500/30'
            }`}>
              <span>{testResults.plivo.message}</span>
              {testResults.plivo.latency_ms && (
                <span className="font-mono text-[10px] font-bold">{testResults.plivo.latency_ms}ms</span>
              )}
            </div>
          )}
        </div>

        {/* Card 2: Twilio Configuration */}
        <div className="glass-panel p-6 rounded-3xl border border-graphite space-y-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <span className="p-2 rounded-xl bg-burnt/15 text-burnt border border-burnt/30">
                <Radio className="w-4 h-4" />
              </span>
              <div>
                <h3 className="text-sm font-bold text-ivory">Twilio Media Stream</h3>
                <span className="text-[10px] font-mono text-mutedgrey">Live WebSocket Full-Duplex</span>
              </div>
            </div>

            <button
              onClick={() => handleTestConnection('twilio')}
              disabled={testing.twilio}
              className="px-3 py-1.5 rounded-xl bg-graphite hover:bg-burnt/20 hover:text-burnt text-ivory border border-white/10 text-xs font-semibold transition-colors disabled:opacity-50"
            >
              {testing.twilio ? 'Testing...' : 'Ping Trunk'}
            </button>
          </div>

          <div className="space-y-3">
            <div>
              <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
                Account SID (Masked)
              </label>
              <input
                type="text"
                value={settings.twilio_account_sid || ''}
                onChange={(e) => setSettings({ ...settings, twilio_account_sid: e.target.value })}
                className="glass-input w-full font-mono text-xs"
                placeholder="AC••••••••••••••••••••••••"
              />
            </div>

            <div>
              <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
                DID Inbound Phone Number
              </label>
              <input
                type="text"
                value={settings.twilio_phone_number || ''}
                onChange={(e) => setSettings({ ...settings, twilio_phone_number: e.target.value })}
                className="glass-input w-full font-mono text-xs"
                placeholder="+14155552671"
              />
            </div>
          </div>

          {testResults.twilio && (
            <div className={`p-3 rounded-2xl text-xs flex items-center justify-between ${
              testResults.twilio.status === 'connected'
                ? 'bg-emerald-950/40 text-emerald-300 border border-emerald-500/30'
                : 'bg-rose-950/40 text-rose-300 border border-rose-500/30'
            }`}>
              <span>{testResults.twilio.message}</span>
              {testResults.twilio.latency_ms && (
                <span className="font-mono text-[10px] font-bold">{testResults.twilio.latency_ms}ms</span>
              )}
            </div>
          )}
        </div>

        {/* Card 2: Tata Smartflo Configuration */}
        <div className="glass-panel p-6 rounded-3xl border border-graphite space-y-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <span className="p-2 rounded-xl bg-amber/15 text-amber border border-amber/30">
                <Server className="w-4 h-4" />
              </span>
              <div>
                <h3 className="text-sm font-bold text-ivory">Tata Smartflo Enterprise</h3>
                <span className="text-[10px] font-mono text-mutedgrey">SIP Trunking & Dial-in</span>
              </div>
            </div>

            <button
              onClick={() => handleTestConnection('smartflo')}
              disabled={testing.smartflo}
              className="px-3 py-1.5 rounded-xl bg-graphite hover:bg-amber/20 hover:text-amber text-ivory border border-white/10 text-xs font-semibold transition-colors disabled:opacity-50"
            >
              {testing.smartflo ? 'Testing...' : 'Ping Trunk'}
            </button>
          </div>

          <div className="space-y-3">
            <div>
              <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
                Smartflo Caller ID / DID
              </label>
              <input
                type="text"
                value={settings.smartflo_caller_id || ''}
                onChange={(e) => setSettings({ ...settings, smartflo_caller_id: e.target.value })}
                className="glass-input w-full font-mono text-xs"
                placeholder="918040001234"
              />
            </div>

            <div>
              <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
                API Authentication Key (Masked)
              </label>
              <input
                type="text"
                value={settings.smartflo_api_key || ''}
                onChange={(e) => setSettings({ ...settings, smartflo_api_key: e.target.value })}
                className="glass-input w-full font-mono text-xs"
                placeholder="tsf_••••••••••••••••••••••••"
              />
            </div>
          </div>

          {testResults.smartflo && (
            <div className={`p-3 rounded-2xl text-xs flex items-center justify-between ${
              testResults.smartflo.status === 'connected'
                ? 'bg-emerald-950/40 text-emerald-300 border border-emerald-500/30'
                : 'bg-rose-950/40 text-rose-300 border border-rose-500/30'
            }`}>
              <span>{testResults.smartflo.message}</span>
              {testResults.smartflo.latency_ms && (
                <span className="font-mono text-[10px] font-bold">{testResults.smartflo.latency_ms}ms</span>
              )}
            </div>
          )}
        </div>

        {/* Card 3: Exotel Configuration */}
        <div className="glass-panel p-6 rounded-3xl border border-graphite space-y-5 lg:col-span-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <span className="p-2 rounded-xl bg-lavender/15 text-lavender border border-lavender/30">
                <PhoneCall className="w-4 h-4" />
              </span>
              <div>
                <h3 className="text-sm font-bold text-ivory">Exotel Voice Gateway</h3>
                <span className="text-[10px] font-mono text-mutedgrey">Inbound Webhooks & Voice Appointment Integration</span>
              </div>
            </div>

            <button
              onClick={() => handleTestConnection('exotel')}
              disabled={testing.exotel}
              className="px-3 py-1.5 rounded-xl bg-graphite hover:bg-lavender/20 hover:text-lavender text-ivory border border-white/10 text-xs font-semibold transition-colors disabled:opacity-50"
            >
              {testing.exotel ? 'Testing...' : 'Ping Trunk'}
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
                Exotel Account SID (Masked)
              </label>
              <input
                type="text"
                value={settings.exotel_sid || ''}
                onChange={(e) => setSettings({ ...settings, exotel_sid: e.target.value })}
                className="glass-input w-full font-mono text-xs"
                placeholder="ex_••••••••••••••••••••••••"
              />
            </div>

            <div>
              <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
                Caller ID (Virtual Number)
              </label>
              <input
                type="text"
                value={settings.exotel_caller_id || ''}
                onChange={(e) => setSettings({ ...settings, exotel_caller_id: e.target.value })}
                className="glass-input w-full font-mono text-xs"
                placeholder="08088887777"
              />
            </div>
          </div>

          {testResults.exotel && (
            <div className={`p-3 rounded-2xl text-xs flex items-center justify-between ${
              testResults.exotel.status === 'connected'
                ? 'bg-emerald-950/40 text-emerald-300 border border-emerald-500/30'
                : 'bg-rose-950/40 text-rose-300 border border-rose-500/30'
            }`}>
              <span>{testResults.exotel.message}</span>
              {testResults.exotel.latency_ms && (
                <span className="font-mono text-[10px] font-bold">{testResults.exotel.latency_ms}ms</span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
