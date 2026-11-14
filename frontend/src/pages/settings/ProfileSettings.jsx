import React, { useState, useEffect } from 'react';
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
  Users,
  CreditCard,
  Plus,
  Trash2,
  AlertTriangle,
  Receipt,
  Download,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { staffService, subscriptionService } from '../../services/api';
import Modal from '../../components/common/Modal';
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
  const [activeTab, setActiveTab] = useState('general'); // 'general' | 'staff' | 'billing' | 'security' | 'api'

  // Staff State
  const [staffList, setStaffList] = useState([]);
  const [staffModal, setStaffModal] = useState(false);
  const [newStaff, setNewStaff] = useState({
    full_name: '',
    email: '',
    password: '',
    role: 'staff',
  });
  const [staffLoading, setStaffLoading] = useState(false);

  // Billing State
  const [subscription, setSubscription] = useState(null);
  const [plans, setPlans] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [billingLoading, setBillingLoading] = useState(false);
  const [billingCycle, setBillingCycle] = useState('monthly');

  const demoApiKey = 'vat_live_98a7fbc20419d8e7c10b429184aa39';

  const loadStaffAndBilling = async () => {
    try {
      const [staffData, subData, plansData, invData] = await Promise.all([
        staffService.getStaff(),
        subscriptionService.getCurrent(),
        subscriptionService.getPlans(),
        subscriptionService.getInvoices(),
      ]);
      setStaffList(staffData);
      setSubscription(subData);
      setPlans(plansData);
      setInvoices(invData);
    } catch (err) {
      console.error('Failed to load staff/billing data:', err);
    }
  };

  useEffect(() => {
    loadStaffAndBilling();
  }, []);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleCopyKey = () => {
    navigator.clipboard.writeText(demoApiKey);
    setCopiedKey(true);
    setTimeout(() => setCopiedKey(false), 2000);
  };

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(''), 4000);
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
      showToast('Organization and profile settings saved successfully!');
      setFormData({ ...formData, current_password: '', new_password: '' });
    } catch (err) {
      console.error(err);
      alert(err.response?.data?.detail || 'Failed to update profile settings.');
    } finally {
      setSaving(false);
    }
  };

  const handleCreateStaff = async (e) => {
    e.preventDefault();
    setStaffLoading(true);
    try {
      const created = await staffService.createStaff(newStaff);
      setStaffList([...staffList, created]);
      setStaffModal(false);
      setNewStaff({ full_name: '', email: '', password: '', role: 'staff' });
      showToast(`Staff member "${created.full_name}" registered.`);
      await loadStaffAndBilling();
    } catch (err) {
      console.error(err);
      alert(err.response?.data?.detail || 'Failed to create staff member.');
    } finally {
      setStaffLoading(false);
    }
  };

  const handleDeleteStaff = async (id) => {
    if (!window.confirm('Are you sure you want to remove this staff member?')) return;
    try {
      await staffService.deleteStaff(id);
      setStaffList(staffList.filter((s) => s.id !== id));
      showToast('Staff member removed.');
      await loadStaffAndBilling();
    } catch (err) {
      console.error(err);
      alert(err.response?.data?.detail || 'Failed to delete staff member.');
    }
  };

  const handleChangePlan = async (planId) => {
    try {
      await subscriptionService.changePlan({ plan: planId, billing_cycle: billingCycle });
      showToast(`Subscription plan updated to ${planId.toUpperCase()} (${billingCycle}).`);
      await loadStaffAndBilling();
    } catch (err) {
      console.error(err);
      alert(err.response?.data?.detail || 'Failed to change subscription plan.');
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
                Workspace Identity & Operations
              </span>
              <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-emerald-500/15 border border-emerald-500/30 text-emerald-400">
                <ShieldCheck className="w-3 h-3" /> Multi-Tenant Active
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-ivory tracking-tight">
              Organization, Staff & Billing Settings
            </h1>
            <p className="text-xs sm:text-sm text-mutedgrey max-w-xl">
              Configure tenant profile, manage clinical staff members and role authorizations,
              inspect SaaS subscription limits, and manage billing invoices.
            </p>
          </div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex items-center gap-2 border-b border-graphite pb-3 overflow-x-auto">
        {[
          { id: 'general', label: 'Business Profile', icon: Building2 },
          { id: 'staff', label: `Staff & Team (${staffList.length})`, icon: Users },
          { id: 'billing', label: 'Subscription & Quotas', icon: CreditCard },
          { id: 'security', label: 'Security & Auth', icon: Lock },
          { id: 'api', label: 'Developer API Keys', icon: Key },
        ].map((tab) => {
          const Icon = tab.icon;
          const isSelected = activeTab === tab.id;

          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 whitespace-nowrap transition-all ${
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
              <span className="inline-block mt-2 px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-burnt/15 border border-burnt/30 text-burnt uppercase">
                {user?.role || 'admin'}
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
                <span>Active Tier</span>
                <span className="text-amber font-mono font-bold uppercase">
                  {subscription?.plan || 'Professional'}
                </span>
              </div>
              <div className="flex items-center justify-between text-mutedgrey">
                <span>Staff Capacity</span>
                <span className="text-ivory font-mono">
                  {staffList.length} / {subscription?.max_staff || 10} seats
                </span>
              </div>
              <div className="flex items-center justify-between text-mutedgrey">
                <span>Voice Minutes</span>
                <span className="text-ivory font-mono">
                  {subscription?.used_call_minutes || 0} / {subscription?.max_monthly_call_minutes || 2000} mins
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Settings Tab Content */}
        <div className="lg:col-span-2">
          {/* TAB 1: General Business Profile */}
          {activeTab === 'general' && (
            <form onSubmit={handleSubmit} className="space-y-6">
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
          )}

          {/* TAB 2: Staff & Team Management */}
          {activeTab === 'staff' && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="glass-panel p-6 sm:p-7 rounded-3xl border border-graphite space-y-5"
            >
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-base font-bold text-ivory flex items-center gap-2">
                    <Users className="w-4 h-4 text-burnt" /> Doctor & Staff Roster
                  </h3>
                  <p className="text-xs text-mutedgrey mt-0.5">
                    Team members available for patient appointment bookings and console access.
                  </p>
                </div>

                <button
                  onClick={() => setStaffModal(true)}
                  className="px-4 py-2 rounded-xl bg-burnt text-warmblack font-bold text-xs flex items-center gap-1.5 shadow-md hover:bg-burnt-dark transition-all"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Add Team Member
                </button>
              </div>

              {/* Staff Quota Banner */}
              <div className="p-3.5 rounded-2xl bg-warmblack/60 border border-white/5 flex items-center justify-between text-xs">
                <span className="text-mutedgrey">
                  Current Quota Usage:{' '}
                  <span className="text-ivory font-bold">{staffList.length}</span> of{' '}
                  <span className="text-amber font-bold">{subscription?.max_staff || 10}</span> maximum staff members
                </span>
                <span className="text-[10px] font-mono text-mutedgrey">
                  Tier: <span className="text-burnt uppercase font-bold">{subscription?.plan || 'Professional'}</span>
                </span>
              </div>

              {/* Staff Table */}
              <div className="overflow-x-auto rounded-2xl border border-white/5">
                <table className="w-full text-left text-xs">
                  <thead className="bg-warmblack text-mutedgrey uppercase tracking-wider text-[10px] font-mono border-b border-white/5">
                    <tr>
                      <th className="py-3 px-4">Member Name</th>
                      <th className="py-3 px-4">Email Address</th>
                      <th className="py-3 px-4">Role</th>
                      <th className="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5 bg-charcoal/50">
                    {staffList.map((member) => (
                      <tr key={member.id} className="hover:bg-warmblack/40 transition-colors">
                        <td className="py-3.5 px-4 font-bold text-ivory">
                          {member.full_name}
                        </td>
                        <td className="py-3.5 px-4 font-mono text-mutedgrey">
                          {member.email}
                        </td>
                        <td className="py-3.5 px-4">
                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-mono uppercase font-bold ${
                            member.role === 'doctor'
                              ? 'bg-amber/15 text-amber border border-amber/30'
                              : member.role === 'admin'
                              ? 'bg-burnt/15 text-burnt border border-burnt/30'
                              : 'bg-graphite text-ivory border border-white/10'
                          }`}>
                            {member.role}
                          </span>
                        </td>
                        <td className="py-3.5 px-4 text-right">
                          <button
                            onClick={() => handleDeleteStaff(member.id)}
                            className="p-1.5 text-mutedgrey hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors"
                            title="Remove Member"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </motion.div>
          )}

          {/* TAB 3: Subscription & Billing */}
          {activeTab === 'billing' && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-6"
            >
              {/* Current Tier Overview */}
              <div className="glass-panel p-6 sm:p-7 rounded-3xl border border-graphite space-y-5">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-[10px] font-mono uppercase font-bold tracking-wider text-burnt">
                      Active SaaS Tier
                    </span>
                    <h3 className="text-xl font-extrabold text-ivory uppercase">
                      {subscription?.plan || 'Professional'} Plan
                    </h3>
                  </div>

                  <div className="flex items-center gap-1 bg-warmblack/70 p-1 rounded-xl border border-graphite text-xs">
                    <button
                      onClick={() => setBillingCycle('monthly')}
                      className={`px-3 py-1 rounded-lg font-semibold transition-all ${
                        billingCycle === 'monthly' ? 'bg-burnt text-warmblack font-bold' : 'text-mutedgrey'
                      }`}
                    >
                      Monthly
                    </button>
                    <button
                      onClick={() => setBillingCycle('annual')}
                      className={`px-3 py-1 rounded-lg font-semibold transition-all ${
                        billingCycle === 'annual' ? 'bg-burnt text-warmblack font-bold' : 'text-mutedgrey'
                      }`}
                    >
                      Annual (Save 20%)
                    </button>
                  </div>
                </div>

                {/* Quota Progress Bars */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 pt-2">
                  <div className="p-4 rounded-2xl bg-warmblack/60 border border-white/5 space-y-2">
                    <div className="flex justify-between text-xs">
                      <span className="text-mutedgrey">Monthly Telephony Minutes</span>
                      <span className="text-amber font-mono font-bold">
                        {subscription?.used_call_minutes || 0} / {subscription?.max_monthly_call_minutes || 2000} mins
                      </span>
                    </div>
                    <div className="w-full h-2 rounded-full bg-graphite overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-burnt to-amber"
                        style={{
                          width: `${Math.min(
                            100,
                            Math.round(
                              ((subscription?.used_call_minutes || 0) /
                                (subscription?.max_monthly_call_minutes || 2000)) *
                                100
                            )
                          )}%`,
                        }}
                      />
                    </div>
                  </div>

                  <div className="p-4 rounded-2xl bg-warmblack/60 border border-white/5 space-y-2">
                    <div className="flex justify-between text-xs">
                      <span className="text-mutedgrey">Team Member Seats</span>
                      <span className="text-burnt font-mono font-bold">
                        {staffList.length} / {subscription?.max_staff || 10} staff
                      </span>
                    </div>
                    <div className="w-full h-2 rounded-full bg-graphite overflow-hidden">
                      <div
                        className="h-full bg-burnt"
                        style={{
                          width: `${Math.min(
                            100,
                            Math.round((staffList.length / (subscription?.max_staff || 10)) * 100)
                          )}%`,
                        }}
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Tier Selection Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {plans.map((p) => {
                  const isCurrent = subscription?.plan === p.id;
                  const price = billingCycle === 'annual' ? `₹${p.annual_price} / yr` : `₹${p.monthly_price} / mo`;
                  return (
                    <div
                      key={p.id}
                      className={`glass-panel p-5 rounded-3xl border flex flex-col justify-between space-y-4 ${
                        isCurrent ? 'border-burnt ring-1 ring-burnt bg-burnt/10' : 'border-graphite'
                      }`}
                    >
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <h4 className="text-sm font-bold text-ivory">{p.name}</h4>
                          {isCurrent && (
                            <span className="text-[9px] font-mono px-2 py-0.5 rounded-full bg-burnt text-warmblack font-bold uppercase">
                              Current
                            </span>
                          )}
                        </div>
                        <div className="text-lg font-black text-ivory font-mono">{price}</div>
                        <p className="text-[11px] text-mutedgrey">
                          Up to {p.max_staff} staff • {p.max_monthly_call_minutes} monthly mins
                        </p>

                        <ul className="pt-2 space-y-1.5 text-[11px] text-mutedgrey">
                          {p.features?.map((f, i) => (
                            <li key={i} className="flex items-center gap-1.5">
                              <Check className="w-3 h-3 text-burnt shrink-0" />
                              <span>{f}</span>
                            </li>
                          ))}
                        </ul>
                      </div>

                      <button
                        onClick={() => handleChangePlan(p.id)}
                        disabled={isCurrent}
                        className={`w-full py-2 rounded-xl text-xs font-bold transition-all ${
                          isCurrent
                            ? 'bg-graphite text-mutedgrey cursor-default'
                            : 'bg-burnt hover:bg-burnt-dark text-warmblack shadow-md'
                        }`}
                      >
                        {isCurrent ? 'Current Plan' : `Switch to ${p.name}`}
                      </button>
                    </div>
                  );
                })}
              </div>

              {/* Invoices Ledger Table */}
              <div className="glass-panel p-6 rounded-3xl border border-graphite space-y-4">
                <div className="flex items-center gap-2">
                  <Receipt className="w-4 h-4 text-amber" />
                  <h3 className="text-sm font-bold text-ivory">Billing History & Invoices</h3>
                </div>

                <div className="overflow-x-auto rounded-2xl border border-white/5">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-warmblack text-mutedgrey uppercase tracking-wider text-[10px] font-mono border-b border-white/5">
                      <tr>
                        <th className="py-2.5 px-4">Invoice #</th>
                        <th className="py-2.5 px-4">Period</th>
                        <th className="py-2.5 px-4">Amount</th>
                        <th className="py-2.5 px-4">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5 bg-charcoal/50">
                      {invoices.length === 0 ? (
                        <tr>
                          <td colSpan={4} className="py-4 text-center text-mutedgrey">
                            No invoices generated yet.
                          </td>
                        </tr>
                      ) : (
                        invoices.map((inv) => (
                          <tr key={inv.id} className="hover:bg-warmblack/40">
                            <td className="py-3 px-4 font-mono font-bold text-ivory">
                              {inv.invoice_number}
                            </td>
                            <td className="py-3 px-4 text-mutedgrey font-mono text-[11px]">
                              {new Date(inv.billing_period_start).toLocaleDateString()} -{' '}
                              {new Date(inv.billing_period_end).toLocaleDateString()}
                            </td>
                            <td className="py-3 px-4 font-mono font-bold text-amber">
                              ₹{inv.amount} {inv.currency}
                            </td>
                            <td className="py-3 px-4">
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-mono uppercase font-bold bg-emerald-950/60 text-emerald-400 border border-emerald-500/30">
                                {inv.status}
                              </span>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </motion.div>
          )}

          {/* TAB 4: Security & Credentials */}
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

              <div className="flex items-center justify-end pt-2">
                <button
                  type="button"
                  onClick={handleSubmit}
                  disabled={saving}
                  className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-burnt to-amber text-warmblack font-bold text-xs flex items-center gap-2 shadow-lg shadow-burnt/20 hover:scale-[1.02] active:scale-[0.98] transition-all disabled:opacity-50"
                >
                  <Save className="w-4 h-4" />
                  {saving ? 'Saving...' : 'Update Password'}
                </button>
              </div>
            </motion.div>
          )}

          {/* TAB 5: Developer API Keys */}
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
        </div>
      </div>

      {/* Modal: Add Staff Member */}
      <Modal isOpen={staffModal} onClose={() => setStaffModal(false)} title="Register Team Member">
        <form onSubmit={handleCreateStaff} className="space-y-4">
          <div>
            <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
              Full Name *
            </label>
            <input
              type="text"
              required
              value={newStaff.full_name}
              onChange={(e) => setNewStaff({ ...newStaff, full_name: e.target.value })}
              className="w-full px-4 py-2.5 glass-input rounded-xl text-xs font-medium"
              placeholder="e.g. Dr. Kavitha Raman"
            />
          </div>

          <div>
            <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
              Email Address *
            </label>
            <input
              type="email"
              required
              value={newStaff.email}
              onChange={(e) => setNewStaff({ ...newStaff, email: e.target.value })}
              className="w-full px-4 py-2.5 glass-input rounded-xl text-xs font-mono"
              placeholder="doctor@vattaraclinic.com"
            />
          </div>

          <div>
            <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
              Initial Password *
            </label>
            <input
              type="password"
              required
              minLength={8}
              value={newStaff.password}
              onChange={(e) => setNewStaff({ ...newStaff, password: e.target.value })}
              className="w-full px-4 py-2.5 glass-input rounded-xl text-xs font-mono"
              placeholder="At least 8 characters"
            />
          </div>

          <div>
            <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
              Clinical / Staff Role *
            </label>
            <select
              value={newStaff.role}
              onChange={(e) => setNewStaff({ ...newStaff, role: e.target.value })}
              className="w-full px-4 py-2.5 glass-input rounded-xl text-xs font-medium bg-charcoal"
            >
              <option value="doctor" className="bg-charcoal text-ivory">Doctor / Practitioner</option>
              <option value="manager" className="bg-charcoal text-ivory">Practice Manager</option>
              <option value="receptionist" className="bg-charcoal text-ivory">Front Desk Receptionist</option>
              <option value="staff" className="bg-charcoal text-ivory">General Clinic Staff</option>
            </select>
          </div>

          <div className="pt-2 flex justify-end gap-2 border-t border-white/5">
            <button
              type="button"
              onClick={() => setStaffModal(false)}
              className="px-4 py-2 text-xs font-semibold text-mutedgrey hover:text-ivory"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={staffLoading}
              className="px-5 py-2.5 bg-gradient-to-r from-burnt to-amber text-warmblack font-extrabold rounded-xl text-xs uppercase tracking-wider disabled:opacity-50"
            >
              {staffLoading ? 'Registering...' : 'Add Member'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
