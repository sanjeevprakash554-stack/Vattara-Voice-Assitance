import React, { useState } from 'react';
import { motion } from 'framer-motion';
import {
  User,
  Building2,
  Lock,
  Phone,
  Mail,
  MapPin,
  Save,
  CheckCircle2,
  Key,
  Radio,
  ShieldCheck,
  Copy,
  Check,
  Eye,
  EyeOff,
  Sparkles,
  RefreshCw,
  Sliders,
  Globe,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import confetti from 'canvas-confetti';

export default function ProfileSettings() {
  const { user, business, updateProfile } = useAuth();
  const [formData, setFormData] = useState({
    full_name: user?.full_name || '',
    business_name: business?.name || '',
    phone: business?.phone || '',
    address: business?.address || '',
    current_password: '',
    new_password: '',
  });
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState('');
  const [copiedKey, setCopiedKey] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const [activeTab, setActiveTab] = useState('general'); // 'general' | 'security' | 'api'

  const demoApiKey = 'vat_live_98a7fbc20419d8e7c10b429184aa39';

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleCopyKey = () => {
    navigator.clipboard.writeText(demoApiKey);
    setCopiedKey(true);
    setTimeout(() => setCopiedKey(false), 2000);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await updateProfile(formData);
      confetti({
        particleCount: 50,
        spread: 60,
        origin: { y: 0.7 },
        colors: ['#E47745', '#F0AD57', '#A78BFA'],
      });
      setToast('Organization and profile settings saved successfully!');
      setTimeout(() => setToast(''), 4000);
      setFormData({ ...formData, current_password: '', new_password: '' });
    } catch (err) {
      console.error(err);
      alert(err.response?.data?.detail || 'Failed to update profile settings.');
    } finally {
      setSaving(false);
    }
  };

  const initials = formData.full_name
    ? formData.full_name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
        .substring(0, 2)
    : 'AD';

  return (
    <div className="space-y-8 pb-12 max-w-6xl">
      {/* Toast Notification */}
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

        <div className="relative z-10 flex flex-col sm:flex-row sm:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <span className="p-2.5 rounded-xl bg-burnt/15 border border-burnt/30 text-burnt">
                <Building2 className="w-5 h-5 animate-pulse" />
              </span>
              <span className="text-xs font-semibold tracking-wider uppercase text-burnt">
                Workspace Identity & Security
              </span>
              <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-emerald-500/15 border border-emerald-500/30 text-emerald-400">
                <ShieldCheck className="w-3 h-3" /> Enterprise Auth
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-ivory tracking-tight">
              Organization & Profile Settings
            </h1>
            <p className="text-xs sm:text-sm text-mutedgrey max-w-xl">
              Configure tenant business metadata, administrator credentials, API developer tokens,
              and operational access policies.
            </p>
          </div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex items-center gap-2 border-b border-graphite pb-3">
        {[
          { id: 'general', label: 'Business & Profile', icon: Building2 },
          { id: 'security', label: 'Credentials & Security', icon: Lock },
          { id: 'api', label: 'Developer API Keys', icon: Key },
        ].map((tab) => {
          const Icon = tab.icon;
          const isSelected = activeTab === tab.id;

          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition-all ${
                isSelected
                  ? 'bg-burnt text-warmblack font-bold shadow-md shadow-burnt/20'
                  : 'bg-warmblack/50 text-mutedgrey hover:text-ivory border border-white/5'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Settings Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Organization Summary Card */}
        <div className="space-y-6">
          <div className="glass-panel p-6 rounded-3xl border border-graphite text-center space-y-4">
            <div className="relative mx-auto w-20 h-20 rounded-3xl bg-gradient-to-br from-burnt to-amber p-0.5 shadow-xl shadow-burnt/20">
              <div className="w-full h-full rounded-[22px] bg-charcoal flex items-center justify-center text-burnt font-black text-2xl">
                {initials}
              </div>
              <span className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full bg-emerald-500 border-2 border-charcoal flex items-center justify-center">
                <Check className="w-3 h-3 text-white stroke-[3]" />
              </span>
            </div>

            <div>
              <h3 className="text-lg font-bold text-ivory">
                {formData.business_name || 'Organization'}
              </h3>
              <p className="text-xs text-mutedgrey font-mono mt-0.5">
                {user?.email || 'admin@vattara.ai'}
              </p>
              <span className="inline-block mt-2 px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-burnt/15 border border-burnt/30 text-burnt">
                Primary Administrator
              </span>
            </div>

            <div className="pt-4 border-t border-white/5 space-y-2 text-left text-xs">
              <div className="flex items-center justify-between text-mutedgrey">
                <span>Account Status</span>
                <span className="text-emerald-400 font-semibold flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  Active / Healthy
                </span>
              </div>
              <div className="flex items-center justify-between text-mutedgrey">
                <span>Platform Tier</span>
                <span className="text-ivory font-mono">Enterprise AI Suite</span>
              </div>
              <div className="flex items-center justify-between text-mutedgrey">
                <span>Timezone</span>
                <span className="text-ivory font-mono">UTC (Coordinated)</span>
              </div>
            </div>
          </div>

          {/* Quick Help Card */}
          <div className="glass-panel p-5 rounded-2xl border border-graphite space-y-2">
            <h4 className="text-xs font-bold text-ivory flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-burnt" /> AI Assistant Status
            </h4>
            <p className="text-xs text-mutedgrey leading-relaxed">
              Your voice assistant is actively configured to route inbound calls and coordinate
              appointment schedules during your specified working hours.
            </p>
          </div>
        </div>

        {/* Right Column: Settings Form Panels */}
        <div className="lg:col-span-2">
          <form onSubmit={handleSubmit} className="space-y-6">
            {activeTab === 'general' && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="glass-panel p-6 sm:p-7 rounded-3xl border border-graphite space-y-5"
              >
                <div>
                  <h3 className="text-base font-bold text-ivory flex items-center gap-2">
                    <Building2 className="w-4 h-4 text-burnt" /> Organization Profile
                  </h3>
                  <p className="text-xs text-mutedgrey mt-0.5">
                    Public contact details spoken by the AI assistant when answering caller questions.
                  </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-mutedgrey uppercase tracking-wider mb-1.5">
                      Business Name
                    </label>
                    <input
                      type="text"
                      name="business_name"
                      value={formData.business_name}
                      onChange={handleChange}
                      className="glass-input w-full font-semibold"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-mutedgrey uppercase tracking-wider mb-1.5">
                      Business Phone Line
                    </label>
                    <input
                      type="tel"
                      name="phone"
                      value={formData.phone}
                      onChange={handleChange}
                      className="glass-input w-full font-mono"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-mutedgrey uppercase tracking-wider mb-1.5">
                    Physical Address / Clinic Location
                  </label>
                  <input
                    type="text"
                    name="address"
                    value={formData.address}
                    onChange={handleChange}
                    className="glass-input w-full"
                  />
                </div>

                <div className="pt-4 border-t border-white/5 space-y-4">
                  <h4 className="text-xs font-bold text-ivory flex items-center gap-2">
                    <User className="w-3.5 h-3.5 text-amber" /> Administrator Contact
                  </h4>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-semibold text-mutedgrey uppercase tracking-wider mb-1.5">
                        Administrator Full Name
                      </label>
                      <input
                        type="text"
                        name="full_name"
                        value={formData.full_name}
                        onChange={handleChange}
                        className="glass-input w-full"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-mutedgrey uppercase tracking-wider mb-1.5">
                        Account Email (Verified)
                      </label>
                      <input
                        type="email"
                        disabled
                        value={user?.email || 'admin@vattara.ai'}
                        className="glass-input w-full opacity-60 cursor-not-allowed bg-warmblack/50 font-mono text-xs"
                      />
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            {activeTab === 'security' && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="glass-panel p-6 sm:p-7 rounded-3xl border border-graphite space-y-5"
              >
                <div>
                  <h3 className="text-base font-bold text-ivory flex items-center gap-2">
                    <Lock className="w-4 h-4 text-burnt" /> Change Password & Security
                  </h3>
                  <p className="text-xs text-mutedgrey mt-0.5">
                    Update your account authentication credentials with secure encryption standards.
                  </p>
                </div>

                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-semibold text-mutedgrey uppercase tracking-wider mb-1.5">
                      Current Password
                    </label>
                    <input
                      type="password"
                      name="current_password"
                      placeholder="Enter current password..."
                      value={formData.current_password}
                      onChange={handleChange}
                      className="glass-input w-full font-mono text-xs"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-mutedgrey uppercase tracking-wider mb-1.5">
                      New Password
                    </label>
                    <input
                      type="password"
                      name="new_password"
                      placeholder="Enter at least 8 characters..."
                      value={formData.new_password}
                      onChange={handleChange}
                      className="glass-input w-full font-mono text-xs"
                    />
                  </div>
                </div>

                <div className="p-4 rounded-2xl bg-warmblack/60 border border-white/5 space-y-2">
                  <span className="text-xs font-bold text-ivory flex items-center gap-1.5">
                    <ShieldCheck className="w-4 h-4 text-emerald-400" /> Multi-Factor Authentication
                  </span>
                  <p className="text-xs text-mutedgrey">
                    Biometric passes and OTP verification are actively monitored for all admin logins.
                  </p>
                </div>
              </motion.div>
            )}

            {activeTab === 'api' && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="glass-panel p-6 sm:p-7 rounded-3xl border border-graphite space-y-5"
              >
                <div>
                  <h3 className="text-base font-bold text-ivory flex items-center gap-2">
                    <Key className="w-4 h-4 text-amber" /> Live API Secret Keys
                  </h3>
                  <p className="text-xs text-mutedgrey mt-0.5">
                    Connect external CRM workflows, EMR/EHR systems, and calendar dispatch webhooks.
                  </p>
                </div>

                <div className="space-y-3">
                  <label className="block text-xs font-semibold text-mutedgrey uppercase tracking-wider">
                    Production Secret Token
                  </label>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 py-2.5 px-4 rounded-xl bg-warmblack border border-graphite font-mono text-xs text-ivory flex items-center justify-between">
                      <span>{showKey ? demoApiKey : '••••••••••••••••••••••••••••••••••••••'}</span>
                      <button
                        type="button"
                        onClick={() => setShowKey(!showKey)}
                        className="text-mutedgrey hover:text-ivory ml-2"
                      >
                        {showKey ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                      </button>
                    </div>

                    <button
                      type="button"
                      onClick={handleCopyKey}
                      className="px-3.5 py-2.5 rounded-xl bg-warmblack hover:bg-graphite border border-graphite text-xs font-semibold text-ivory flex items-center gap-1.5 transition-colors"
                    >
                      {copiedKey ? (
                        <>
                          <Check className="w-3.5 h-3.5 text-emerald-400" /> Copied
                        </>
                      ) : (
                        <>
                          <Copy className="w-3.5 h-3.5" /> Copy
                        </>
                      )}
                    </button>
                  </div>
                  <p className="text-[11px] text-mutedgrey">
                    Do not share your API key in publicly accessible areas. Pass this as{' '}
                    <code className="text-burnt font-mono">Authorization: Bearer &lt;TOKEN&gt;</code>.
                  </p>
                </div>
              </motion.div>
            )}

            {/* Save Button Ribbon */}
            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="submit"
                disabled={saving}
                className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-burnt to-amber text-warmblack font-bold text-xs flex items-center gap-2 shadow-lg shadow-burnt/20 hover:scale-[1.02] active:scale-[0.98] transition-all disabled:opacity-50"
              >
                <Save className="w-4 h-4" />
                {saving ? 'Saving Changes...' : 'Save Settings'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
