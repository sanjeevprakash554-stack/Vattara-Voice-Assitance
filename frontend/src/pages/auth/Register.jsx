import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  AudioWaveform,
  Building2,
  Phone,
  Mail,
  Lock,
  User,
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
  Sparkles,
  Stethoscope,
  Hotel,
  Scissors,
  Wrench,
  Home,
  Headphones,
  Check,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import confetti from 'canvas-confetti';

const VERTICALS = [
  {
    id: 'clinic',
    name: 'Clinic & Hospital',
    icon: Stethoscope,
    desc: 'Patient appointment triage, doctor schedules, consultation inquiry answering',
    badge: 'Popular',
  },
  {
    id: 'hotel',
    name: 'Hotel & Hospitality',
    icon: Hotel,
    desc: 'Room reservation queries, concierge offloading, check-in instructions',
    badge: '24/7 Concierge',
  },
  {
    id: 'salon',
    name: 'Salon & Spa',
    icon: Scissors,
    desc: 'Stylist slot scheduling, treatment catalogs, automatic reminder dispatches',
    badge: 'Auto-Booking',
  },
  {
    id: 'service_centre',
    name: 'Auto Service Centre',
    icon: Wrench,
    desc: 'Repair slot booking, service estimate FAQs, vehicle pickup notifications',
    badge: 'Fleet Ready',
  },
  {
    id: 'real_estate',
    name: 'Real Estate Agency',
    icon: Home,
    desc: 'Property inquiry qualification, site visit schedules, lead routing',
    badge: 'Lead Gen',
  },
  {
    id: 'other',
    name: 'General Service Business',
    icon: Headphones,
    desc: 'Custom appointment booking, billing inquiries, staff escalation routing',
    badge: 'Customizable',
  },
];

export default function Register() {
  const navigate = useNavigate();
  const { register } = useAuth();
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({
    business_name: '',
    vertical: 'clinic',
    business_phone: '',
    business_email: '',
    address: '',
    admin_name: '',
    admin_email: '',
    admin_password: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleNext = (e) => {
    e?.preventDefault();
    if (step === 1 && (!formData.business_name || !formData.business_phone || !formData.business_email)) {
      setError('Please fill in all required business information.');
      return;
    }
    setError('');
    setStep(step + 1);
  };

  const handlePrev = () => {
    setError('');
    setStep(step - 1);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await register(formData);
      confetti({
        particleCount: 50,
        spread: 80,
        origin: { y: 0.6 },
        colors: ['#E47745', '#F0AD57', '#A78BFA'],
      });
      navigate('/');
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed. Please check form fields.');
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-warmblack text-ivory py-12 px-4 sm:px-6 lg:px-8 relative overflow-hidden bg-mesh-pattern flex flex-col justify-center">
      {/* Background ambient flares */}
      <div className="absolute top-[-10%] right-[-10%] w-[550px] h-[550px] bg-burnt/[0.08] rounded-full blur-[160px] pointer-events-none" />
      <div className="absolute bottom-[-10%] left-[-10%] w-[550px] h-[550px] bg-amber/[0.06] rounded-full blur-[160px] pointer-events-none" />

      {/* Brand Header */}
      <div className="sm:mx-auto sm:w-full sm:max-w-2xl text-center mb-6 relative z-10">
        <div className="inline-flex w-12 h-12 rounded-2xl bg-gradient-to-tr from-burnt to-amber items-center justify-center text-warmblack shadow-xl shadow-burnt/30 mb-3">
          <AudioWaveform className="w-6 h-6 animate-pulse" />
        </div>
        <h2 className="text-3xl font-extrabold text-ivory tracking-tight">Deploy Vattara Voice AI</h2>
        <p className="mt-1 text-xs text-mutedgrey max-w-md mx-auto">
          Equip your clinic, hotel, salon or enterprise with an autonomous voice receptionist in 3 quick steps.
        </p>

        {/* 3-Step Visual Progress Bar */}
        <div className="mt-6 max-w-md mx-auto flex items-center justify-between relative">
          <div className="absolute left-6 right-6 top-1/2 -translate-y-1/2 h-[2px] bg-graphite -z-0" />
          <div
            className="absolute left-6 top-1/2 -translate-y-1/2 h-[2px] bg-gradient-to-r from-burnt to-amber transition-all duration-300 -z-0"
            style={{ width: `${((step - 1) / 2) * 88}%` }}
          />

          {[
            { s: 1, label: 'Organization' },
            { s: 2, label: 'Industry Vertical' },
            { s: 3, label: 'Admin & AI Setup' },
          ].map((item) => {
            const isCompleted = step > item.s;
            const isCurrent = step === item.s;

            return (
              <div key={item.s} className="flex flex-col items-center relative z-10">
                <div
                  className={`w-9 h-9 rounded-full flex items-center justify-center font-mono font-bold text-xs transition-all duration-200 ${
                    isCompleted
                      ? 'bg-burnt text-warmblack shadow-md shadow-burnt/40'
                      : isCurrent
                      ? 'bg-amber text-warmblack ring-4 ring-amber/20 shadow-md shadow-amber/30'
                      : 'bg-graphite text-mutedgrey border border-ivory/10'
                  }`}
                >
                  {isCompleted ? <Check className="w-4 h-4 stroke-[3]" /> : item.s}
                </div>
                <span
                  className={`text-[10px] font-mono mt-1.5 font-bold uppercase tracking-wider ${
                    isCurrent ? 'text-amber' : isCompleted ? 'text-burnt' : 'text-mutedgrey/70'
                  }`}
                >
                  {item.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Main Wizard Form Card */}
      <div className="sm:mx-auto sm:w-full sm:max-w-2xl relative z-10">
        <div className="glass-panel-glow py-8 px-6 sm:px-10 rounded-3xl shadow-2xl border border-ivory/10">
          {error && (
            <div className="mb-6 p-3.5 rounded-2xl bg-rose-950/40 border border-rose-500/30 text-rose-300 text-xs">
              {error}
            </div>
          )}

          <AnimatePresence mode="wait">
            {/* STEP 1: Organization Information */}
            {step === 1 && (
              <motion.div
                key="step1"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.25 }}
                className="space-y-4"
              >
                <div className="border-b border-ivory/10 pb-3 mb-4">
                  <h3 className="text-base font-bold text-ivory">Step 1: Organization Profile</h3>
                  <p className="text-xs text-mutedgrey">Provide your business identification and phone presence.</p>
                </div>

                <div>
                  <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
                    Business / Clinic Name *
                  </label>
                  <div className="relative">
                    <Building2 className="w-4 h-4 text-mutedgrey absolute left-3.5 top-3.5" />
                    <input
                      type="text"
                      required
                      name="business_name"
                      value={formData.business_name}
                      onChange={handleChange}
                      className="w-full pl-10 pr-4 py-3 glass-input rounded-xl text-xs font-medium focus:ring-1 focus:ring-burnt"
                      placeholder="e.g. Apex Multi-Specialty Clinic"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
                      Business Reception Phone *
                    </label>
                    <div className="relative">
                      <Phone className="w-4 h-4 text-mutedgrey absolute left-3.5 top-3.5" />
                      <input
                        type="text"
                        required
                        name="business_phone"
                        value={formData.business_phone}
                        onChange={handleChange}
                        className="w-full pl-10 pr-4 py-3 glass-input rounded-xl text-xs font-medium focus:ring-1 focus:ring-burnt"
                        placeholder="+91 44 2828 9000"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
                      Official Contact Email *
                    </label>
                    <div className="relative">
                      <Mail className="w-4 h-4 text-mutedgrey absolute left-3.5 top-3.5" />
                      <input
                        type="email"
                        required
                        name="business_email"
                        value={formData.business_email}
                        onChange={handleChange}
                        className="w-full pl-10 pr-4 py-3 glass-input rounded-xl text-xs font-medium focus:ring-1 focus:ring-burnt"
                        placeholder="contact@apexclinic.com"
                      />
                    </div>
                  </div>
                </div>

                <div>
                  <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
                    Street Address & Location
                  </label>
                  <input
                    type="text"
                    name="address"
                    value={formData.address}
                    onChange={handleChange}
                    className="w-full px-4 py-3 glass-input rounded-xl text-xs font-medium focus:ring-1 focus:ring-burnt"
                    placeholder="42, Anna Salai, Chennai, Tamil Nadu 600002"
                  />
                </div>

                <div className="pt-4 flex justify-end">
                  <button
                    type="button"
                    onClick={handleNext}
                    className="flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-burnt to-amber text-warmblack font-bold text-xs uppercase tracking-wider shadow-lg shadow-burnt/25 hover:shadow-burnt/40 transition-all"
                  >
                    <span>Proceed to Industry Vertical</span>
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              </motion.div>
            )}

            {/* STEP 2: Industry Vertical Cards */}
            {step === 2 && (
              <motion.div
                key="step2"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.25 }}
                className="space-y-4"
              >
                <div className="border-b border-ivory/10 pb-3 mb-4">
                  <h3 className="text-base font-bold text-ivory">Step 2: Select Your Industry Vertical</h3>
                  <p className="text-xs text-mutedgrey">
                    This automatically tunes the AI speech model and default services for your domain.
                  </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                  {VERTICALS.map((item) => {
                    const isSelected = formData.vertical === item.id;
                    const Icon = item.icon;

                    return (
                      <div
                        key={item.id}
                        onClick={() => setFormData({ ...formData, vertical: item.id })}
                        className={`p-4 rounded-2xl border cursor-pointer transition-all duration-200 relative ${
                          isSelected
                            ? 'bg-burnt/15 border-burnt ring-2 ring-burnt/30 shadow-lg shadow-burnt/20'
                            : 'glass-card border-ivory/10 hover:border-ivory/20'
                        }`}
                      >
                        <div className="flex items-start justify-between mb-2">
                          <div
                            className={`p-2.5 rounded-xl border ${
                              isSelected
                                ? 'bg-burnt text-warmblack border-burnt'
                                : 'bg-charcoal text-amber border-ivory/10'
                            }`}
                          >
                            <Icon className="w-5 h-5" />
                          </div>

                          <span
                            className={`text-[9px] font-mono font-bold px-2 py-0.5 rounded-full border uppercase tracking-wider ${
                              isSelected
                                ? 'bg-burnt text-warmblack border-burnt font-extrabold'
                                : 'bg-graphite text-mutedgrey border-ivory/10'
                            }`}
                          >
                            {item.badge}
                          </span>
                        </div>

                        <h4 className="text-xs font-bold text-ivory tracking-wide">{item.name}</h4>
                        <p className="text-[11px] text-mutedgrey mt-1 leading-relaxed">{item.desc}</p>
                      </div>
                    );
                  })}
                </div>

                <div className="pt-4 flex items-center justify-between">
                  <button
                    type="button"
                    onClick={handlePrev}
                    className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-mutedgrey hover:text-ivory text-xs font-semibold"
                  >
                    <ArrowLeft className="w-4 h-4" /> Back
                  </button>

                  <button
                    type="button"
                    onClick={handleNext}
                    className="flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-burnt to-amber text-warmblack font-bold text-xs uppercase tracking-wider shadow-lg shadow-burnt/25 hover:shadow-burnt/40 transition-all"
                  >
                    <span>Proceed to Admin Setup</span>
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              </motion.div>
            )}

            {/* STEP 3: Admin User & Launch */}
            {step === 3 && (
              <motion.div
                key="step3"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.25 }}
                className="space-y-4"
              >
                <div className="border-b border-ivory/10 pb-3 mb-4">
                  <h3 className="text-base font-bold text-ivory">Step 3: Administrator Credentials</h3>
                  <p className="text-xs text-mutedgrey">Create the root account that will manage this tenant.</p>
                </div>

                <div>
                  <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
                    Administrator Full Name *
                  </label>
                  <div className="relative">
                    <User className="w-4 h-4 text-mutedgrey absolute left-3.5 top-3.5" />
                    <input
                      type="text"
                      required
                      name="admin_name"
                      value={formData.admin_name}
                      onChange={handleChange}
                      className="w-full pl-10 pr-4 py-3 glass-input rounded-xl text-xs font-medium focus:ring-1 focus:ring-burnt"
                      placeholder="Dr. Rajesh Kumar"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
                    Admin Work Email *
                  </label>
                  <div className="relative">
                    <Mail className="w-4 h-4 text-mutedgrey absolute left-3.5 top-3.5" />
                    <input
                      type="email"
                      required
                      name="admin_email"
                      value={formData.admin_email}
                      onChange={handleChange}
                      className="w-full pl-10 pr-4 py-3 glass-input rounded-xl text-xs font-medium focus:ring-1 focus:ring-burnt"
                      placeholder="admin@apexclinic.com"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
                    Password *
                  </label>
                  <div className="relative">
                    <Lock className="w-4 h-4 text-mutedgrey absolute left-3.5 top-3.5" />
                    <input
                      type="password"
                      required
                      name="admin_password"
                      value={formData.admin_password}
                      onChange={handleChange}
                      className="w-full pl-10 pr-4 py-3 glass-input rounded-xl text-xs font-medium focus:ring-1 focus:ring-burnt"
                      placeholder="At least 6 characters"
                    />
                  </div>
                </div>

                {/* Summary preview pill */}
                <div className="p-3.5 rounded-2xl bg-charcoal border border-ivory/10 text-xs flex items-center justify-between">
                  <div>
                    <span className="text-[10px] font-mono uppercase tracking-wider text-mutedgrey block">
                      Ready to Provision
                    </span>
                    <span className="font-bold text-ivory">
                      {formData.business_name || 'Organization'} ({formData.vertical})
                    </span>
                  </div>
                  <span className="text-[11px] font-mono font-bold text-amber bg-amber/15 px-2.5 py-1 rounded-full border border-amber/30">
                    Alloy Neural Voice
                  </span>
                </div>

                <div className="pt-4 flex items-center justify-between">
                  <button
                    type="button"
                    onClick={handlePrev}
                    className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-mutedgrey hover:text-ivory text-xs font-semibold"
                  >
                    <ArrowLeft className="w-4 h-4" /> Back
                  </button>

                  <button
                    type="button"
                    onClick={handleSubmit}
                    disabled={loading}
                    className="flex items-center gap-2 px-8 py-3.5 rounded-xl bg-gradient-to-r from-burnt via-burnt to-amber text-warmblack font-extrabold text-xs uppercase tracking-wider shadow-xl shadow-burnt/30 hover:shadow-burnt/50 transition-all disabled:opacity-50"
                  >
                    <Sparkles className="w-4 h-4" />
                    <span>{loading ? 'Deploying Voice AI...' : 'Complete & Launch Platform'}</span>
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <div className="mt-6 text-center text-xs text-mutedgrey pt-4 border-t border-ivory/10">
            Already have an active tenant?{' '}
            <Link to="/login" className="font-bold text-amber hover:text-amber-light underline underline-offset-4">
              Sign In to Console
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
