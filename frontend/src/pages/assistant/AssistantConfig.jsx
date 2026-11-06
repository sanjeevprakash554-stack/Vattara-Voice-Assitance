import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Bot,
  Volume2,
  Globe,
  Clock,
  Sparkles,
  Save,
  Plus,
  Trash2,
  CheckCircle2,
  HelpCircle,
  Briefcase,
  ToggleLeft,
  ToggleRight,
  Radio,
  Play,
  Pause,
  Wand2,
  Sliders,
} from 'lucide-react';
import Modal from '../../components/common/Modal';
import Badge from '../../components/common/Badge';
import VoiceOrb from '../../components/common/VoiceOrb';
import WaveformVisualizer from '../../components/common/WaveformVisualizer';
import { assistantService } from '../../services/api';

const VOICES = [
  { id: 'alloy', name: 'Alloy', tone: 'Neutral & Friendly', sampleText: 'Hello! Welcome to our clinic, how may I assist you today?' },
  { id: 'echo', name: 'Echo', tone: 'Warm & Professional', sampleText: 'Good day. I can confirm your appointment schedule right now.' },
  { id: 'fable', name: 'Fable', tone: 'Expressive & Clear', sampleText: 'Thank you for reaching out, let me check available slots.' },
  { id: 'onyx', name: 'Onyx', tone: 'Deep & Authoritative', sampleText: 'Our clinical team is available Monday through Saturday.' },
  { id: 'nova', name: 'Nova', tone: 'Energetic & Helpful', sampleText: 'Hi there! I would be delighted to help you book a visit.' },
  { id: 'shimmer', name: 'Shimmer', tone: 'Soothing & Gentle', sampleText: 'We care about your comfort. Your consultation is reserved.' },
];

const LANGUAGES = [
  { code: 'en-US', name: 'English (United States)' },
  { code: 'en-IN', name: 'English (India)' },
  { code: 'hi-IN', name: 'Hindi (India)' },
  { code: 'ta-IN', name: 'Tamil (India)' },
  { code: 'es-ES', name: 'Spanish' },
  { code: 'fr-FR', name: 'French' },
];

export default function AssistantConfig() {
  const [activeTab, setActiveTab] = useState('persona');
  const [config, setConfig] = useState(null);
  const [services, setServices] = useState([]);
  const [faqs, setFaqs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState('');
  const [playingVoice, setPlayingVoice] = useState(null);

  // Service Modal
  const [serviceModal, setServiceModal] = useState(false);
  const [newService, setNewService] = useState({
    name: '',
    description: '',
    duration_minutes: 30,
    price: 500,
  });

  // FAQ Modal
  const [faqModal, setFaqModal] = useState(false);
  const [newFaq, setNewFaq] = useState({
    category: 'General',
    question: '',
    answer: '',
  });

  const loadData = async () => {
    try {
      const [cData, sData, fData] = await Promise.all([
        assistantService.getConfig(),
        assistantService.getServices(),
        assistantService.getFaqs(),
      ]);
      setConfig(cData);
      setServices(sData);
      setFaqs(fData);
    } catch (err) {
      console.error('Failed to load assistant configuration:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(''), 4000);
  };

  const handleSaveConfig = async (e) => {
    e?.preventDefault();
    setSaving(true);
    try {
      const updated = await assistantService.updateConfig(config);
      setConfig(updated);
      showToast('AI Assistant neural parameters updated!');
    } catch (err) {
      console.error(err);
      showToast('Failed to save configuration.');
    } finally {
      setSaving(false);
    }
  };

  const handleToggleActive = async () => {
    try {
      const updated = await assistantService.toggleAssistant(!config.is_active);
      setConfig(updated);
      showToast(
        updated.is_active ? 'AI Voice Receptionist is now ACTIVE.' : 'AI Voice Receptionist is now STANDBY.'
      );
    } catch (err) {
      console.error(err);
    }
  };

  const handlePlaySample = (voiceId) => {
    if (playingVoice === voiceId) {
      if ('speechSynthesis' in window) window.speechSynthesis.cancel();
      setPlayingVoice(null);
    } else {
      setPlayingVoice(voiceId);
      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        const voiceInfo = VOICES.find((v) => v.id === voiceId);
        const utterance = new SpeechSynthesisUtterance(
          `Hello! I am ${voiceInfo?.name || 'Vattara'}, your AI voice assistant. Thank you for calling Vattara Health Clinic. How may I assist your appointment today?`
        );
        if (voiceId === 'orion') {
          utterance.pitch = 0.85;
          utterance.rate = 0.95;
        } else if (voiceId === 'sol') {
          utterance.pitch = 1.15;
          utterance.rate = 1.05;
        } else if (voiceId === 'zephyr') {
          utterance.pitch = 0.95;
          utterance.rate = 0.92;
        } else {
          utterance.pitch = 1.1;
          utterance.rate = 1.0;
        }
        utterance.onend = () => setPlayingVoice(null);
        utterance.onerror = () => setPlayingVoice(null);
        window.speechSynthesis.speak(utterance);
      } else {
        setTimeout(() => setPlayingVoice(null), 3500);
      }
    }
  };

  const handleEnhancePrompt = () => {
    const enhanced =
      "You are Vattara AI, an empathetic, highly knowledgeable medical receptionist for Vattara City Clinic. Greet every patient warmly, triage consultation requests, clearly explain doctor consultation fees (General Physician: ₹500, Cardiology: ₹1200), book appointments with zero friction, and coordinate emergency escalations immediately.";
    setConfig({ ...config, system_prompt: enhanced });
    showToast('Prompt enhanced with clinical communication best practices!');
  };

  const handleCreateService = async (e) => {
    e.preventDefault();
    try {
      const created = await assistantService.createService(newService);
      setServices([...services, created]);
      setServiceModal(false);
      setNewService({ name: '', description: '', duration_minutes: 30, price: 500 });
      showToast('Service added to voice catalog.');
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeleteService = async (id) => {
    if (!window.confirm('Delete this service?')) return;
    try {
      await assistantService.deleteService(id);
      setServices(services.filter((s) => s.id !== id));
      showToast('Service removed.');
    } catch (err) {
      console.error(err);
    }
  };

  const handleCreateFaq = async (e) => {
    e.preventDefault();
    try {
      const created = await assistantService.createFaq(newFaq);
      setFaqs([...faqs, created]);
      setFaqModal(false);
      setNewFaq({ category: 'General', question: '', answer: '' });
      showToast('Knowledge Base FAQ saved.');
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeleteFaq = async (id) => {
    if (!window.confirm('Delete this FAQ entry?')) return;
    try {
      await assistantService.deleteFaq(id);
      setFaqs(faqs.filter((f) => f.id !== id));
      showToast('FAQ deleted.');
    } catch (err) {
      console.error(err);
    }
  };

  if (loading || !config) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="w-10 h-10 border-2 border-burnt border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 glass-panel-glow text-ivory text-xs font-bold px-4 py-3 rounded-2xl shadow-2xl flex items-center gap-2 border border-burnt/30 animate-fade-in">
          <CheckCircle2 className="w-4 h-4 text-amber" />
          <span>{toast}</span>
        </div>
      )}

      {/* Control Centre Header */}
      <div className="glass-panel rounded-3xl p-6 border border-ivory/10 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-burnt to-amber flex items-center justify-center text-warmblack shadow-xl shadow-burnt/25">
            <Sliders className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-extrabold text-ivory tracking-tight">AI Voice Control Centre</h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-burnt/15 text-burnt border border-burnt/30 uppercase font-bold">
                GPT-4o Realtime
              </span>
            </div>
            <p className="text-xs text-mutedgrey mt-0.5">
              Tune neural speech parameters, voice persona, services catalog, and knowledge base.
            </p>
          </div>
        </div>

        {/* Master Activation Switch */}
        <div className="flex items-center gap-3 glass-card px-4 py-2.5 rounded-2xl border border-ivory/10">
          <span className="text-xs font-mono font-bold uppercase tracking-wider text-mutedgrey">
            State: <span className={config.is_active ? 'text-amber font-extrabold' : 'text-rose-400 font-extrabold'}>{config.is_active ? 'ONLINE' : 'STANDBY'}</span>
          </span>
          <button
            onClick={handleToggleActive}
            className={`p-1 rounded-xl transition-colors ${
              config.is_active ? 'text-burnt hover:text-amber' : 'text-mutedgrey'
            }`}
          >
            {config.is_active ? (
              <ToggleRight className="w-9 h-9" />
            ) : (
              <ToggleLeft className="w-9 h-9" />
            )}
          </button>
        </div>
      </div>

      {/* Main Grid: Left interactive preview / Right command tabs */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* LEFT COLUMN (Span 4): Interactive AI Voice Orb & Preview Console */}
        <div className="lg:col-span-4 glass-panel rounded-3xl p-6 border border-ivory/10 flex flex-col items-center justify-between space-y-6 sticky top-24">
          <div className="w-full text-center">
            <span className="text-[10px] font-mono uppercase tracking-widest text-amber font-bold block mb-1">
              Neural Preview Console
            </span>
            <h3 className="text-base font-extrabold text-ivory">
              {config.assistant_name}
            </h3>
            <p className="text-[11px] text-mutedgrey mt-0.5 capitalize">
              Voice: {config.voice} • {config.language}
            </p>
          </div>

          <VoiceOrb size="md" isSpeaking={!!playingVoice || config.is_active} />

          <div className="w-full">
            <WaveformVisualizer barCount={26} height={32} color="burnt" isPlaying={!!playingVoice || config.is_active} />
          </div>

          {/* Voice sample speech trigger */}
          <div className="w-full p-4 rounded-2xl bg-charcoal border border-ivory/10 space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-ivory flex items-center gap-1.5">
                <Volume2 className="w-3.5 h-3.5 text-amber" /> Audio Sample
              </span>
              <button
                onClick={() => handlePlaySample(config.voice)}
                className="flex items-center gap-1 text-[11px] font-mono font-bold text-amber hover:text-amber-light"
              >
                {playingVoice === config.voice ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                {playingVoice === config.voice ? 'Synthesizing...' : 'Listen'}
              </button>
            </div>
            <p className="text-[11px] text-mutedgrey italic leading-relaxed">
              "{VOICES.find((v) => v.id === config.voice)?.sampleText}"
            </p>
          </div>

          <div className="w-full text-center">
            <button
              onClick={handleSaveConfig}
              disabled={saving}
              className="w-full py-3 rounded-xl bg-gradient-to-r from-burnt to-amber text-warmblack font-extrabold text-xs uppercase tracking-wider shadow-lg shadow-burnt/25 hover:shadow-burnt/40 transition-all disabled:opacity-50"
            >
              {saving ? 'Saving...' : 'Deploy Changes to Production'}
            </button>
          </div>
        </div>

        {/* RIGHT COLUMN (Span 8): Settings Deck */}
        <div className="lg:col-span-8 space-y-6">
          {/* Module Navigation Tabs */}
          <div className="flex border-b border-ivory/10 glass-panel px-6 rounded-t-3xl shadow-sm gap-6 overflow-x-auto">
            {[
              { id: 'persona', label: 'Persona & Voice', icon: Bot },
              { id: 'prompt', label: 'System Instructions', icon: Sparkles },
              { id: 'services', label: `Services (${services.length})`, icon: Briefcase },
              { id: 'faqs', label: `FAQs (${faqs.length})`, icon: HelpCircle },
              { id: 'hours', label: 'Working Hours', icon: Clock },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`py-4 text-xs font-bold border-b-2 whitespace-nowrap transition-all flex items-center gap-2 ${
                  activeTab === tab.id
                    ? 'border-burnt text-amber'
                    : 'border-transparent text-mutedgrey hover:text-ivory'
                }`}
              >
                <tab.icon className="w-4 h-4" />
                <span>{tab.label}</span>
              </button>
            ))}
          </div>

          {/* Tab 1: Persona & Voice */}
          {activeTab === 'persona' && (
            <div className="glass-panel rounded-b-3xl p-6 sm:p-8 border border-ivory/10 space-y-6">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1.5">
                    AI Assistant Name
                  </label>
                  <input
                    type="text"
                    required
                    value={config.assistant_name}
                    onChange={(e) => setConfig({ ...config, assistant_name: e.target.value })}
                    className="w-full px-4 py-3 glass-input rounded-xl text-xs font-medium focus:ring-1 focus:ring-burnt"
                    placeholder="e.g. Vattara AI"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1.5">
                    Spoken Language Dialect
                  </label>
                  <div className="relative">
                    <Globe className="w-4 h-4 text-mutedgrey absolute left-3.5 top-3.5" />
                    <select
                      value={config.language}
                      onChange={(e) => setConfig({ ...config, language: e.target.value })}
                      className="w-full pl-10 pr-4 py-3 glass-input rounded-xl text-xs font-medium focus:ring-1 focus:ring-burnt"
                    >
                      {LANGUAGES.map((lang) => (
                        <option key={lang.code} value={lang.code} className="bg-charcoal text-ivory">
                          {lang.name}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>

              {/* Voice Selection Cards */}
              <div>
                <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-2">
                  Select Speech Tone Persona
                </label>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {VOICES.map((v) => {
                    const isSelected = config.voice === v.id;
                    return (
                      <div
                        key={v.id}
                        onClick={() => setConfig({ ...config, voice: v.id })}
                        className={`p-4 rounded-2xl border cursor-pointer transition-all ${
                          isSelected
                            ? 'bg-burnt/15 border-burnt ring-2 ring-burnt/30 shadow-md shadow-burnt/20'
                            : 'glass-card border-ivory/10 hover:border-ivory/20'
                        }`}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <Volume2 className={`w-4 h-4 ${isSelected ? 'text-burnt' : 'text-mutedgrey'}`} />
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              handlePlaySample(v.id);
                            }}
                            className="p-1 rounded-lg text-mutedgrey hover:text-amber"
                          >
                            {playingVoice === v.id ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                          </button>
                        </div>

                        <h4 className="text-xs font-bold text-ivory tracking-wide">{v.name}</h4>
                        <p className="text-[10px] text-mutedgrey mt-0.5">{v.tone}</p>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* Tab 2: System Prompt & AI Instructions */}
          {activeTab === 'prompt' && (
            <div className="glass-panel rounded-b-3xl p-6 sm:p-8 border border-ivory/10 space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-ivory">Conversational Persona & Protocol</h3>
                  <p className="text-xs text-mutedgrey">Direct how the voice model communicates with patients and callers.</p>
                </div>
                <button
                  type="button"
                  onClick={handleEnhancePrompt}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-amber/15 text-amber border border-amber/30 text-xs font-mono font-bold hover:bg-amber/25 transition-colors"
                >
                  <Wand2 className="w-3.5 h-3.5" /> Enhance Prompt with AI
                </button>
              </div>

              <div>
                <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1.5">
                  System Prompt
                </label>
                <textarea
                  rows={5}
                  value={config.system_prompt || ''}
                  onChange={(e) => setConfig({ ...config, system_prompt: e.target.value })}
                  className="w-full p-4 glass-input rounded-2xl text-xs font-mono leading-relaxed focus:ring-1 focus:ring-burnt"
                  placeholder="Set conversational instructions, empathy level, triage rules..."
                />
              </div>

              <div>
                <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1.5">
                  Business Overview & Clinical Context
                </label>
                <textarea
                  rows={3}
                  value={config.business_info || ''}
                  onChange={(e) => setConfig({ ...config, business_info: e.target.value })}
                  className="w-full p-4 glass-input rounded-2xl text-xs font-mono leading-relaxed focus:ring-1 focus:ring-burnt"
                  placeholder="Describe your specialties, clinic departments, doctors, and location..."
                />
              </div>
            </div>
          )}

          {/* Tab 3: Services Catalog */}
          {activeTab === 'services' && (
            <div className="glass-panel rounded-b-3xl p-6 sm:p-8 border border-ivory/10 space-y-4">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <h3 className="text-sm font-bold text-ivory">Services Catalog</h3>
                  <p className="text-xs text-mutedgrey">Treatments and consultation offerings referenced by the voice assistant.</p>
                </div>
                <button
                  onClick={() => setServiceModal(true)}
                  className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-burnt hover:bg-burnt-dark text-warmblack font-extrabold text-xs shadow-md transition-all"
                >
                  <Plus className="w-3.5 h-3.5" /> Add Service
                </button>
              </div>

              <div className="space-y-3">
                {services.map((srv) => (
                  <div key={srv.id} className="p-4 rounded-2xl glass-card border border-ivory/10 flex items-center justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="text-xs font-bold text-ivory tracking-wide">{srv.name}</h4>
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-graphite border border-ivory/10 text-mutedgrey">
                          {srv.duration_minutes} mins
                        </span>
                      </div>
                      <p className="text-[11px] text-mutedgrey mt-0.5">{srv.description || 'Standard business service'}</p>
                    </div>

                    <div className="flex items-center gap-4">
                      <span className="font-mono font-extrabold text-amber text-sm">
                        ₹{srv.price}
                      </span>
                      <button
                        onClick={() => handleDeleteService(srv.id)}
                        className="p-1.5 text-mutedgrey hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Tab 4: Knowledge Base FAQs */}
          {activeTab === 'faqs' && (
            <div className="glass-panel rounded-b-3xl p-6 sm:p-8 border border-ivory/10 space-y-4">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <h3 className="text-sm font-bold text-ivory">Knowledge Base FAQs</h3>
                  <p className="text-xs text-mutedgrey">Autonomous caller question answering answers.</p>
                </div>
                <button
                  onClick={() => setFaqModal(true)}
                  className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-burnt hover:bg-burnt-dark text-warmblack font-extrabold text-xs shadow-md transition-all"
                >
                  <Plus className="w-3.5 h-3.5" /> Add FAQ
                </button>
              </div>

              <div className="space-y-3">
                {faqs.map((faq) => (
                  <div key={faq.id} className="p-4 rounded-2xl glass-card border border-ivory/10 space-y-1.5">
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-[9px] font-mono font-bold uppercase tracking-wider text-amber bg-amber/10 border border-amber/25 px-2 py-0.5 rounded-full">
                          {faq.category}
                        </span>
                        <h4 className="text-xs font-bold text-ivory">{faq.question}</h4>
                      </div>
                      <button
                        onClick={() => handleDeleteFaq(faq.id)}
                        className="p-1 text-mutedgrey hover:text-rose-400 rounded"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                    <p className="text-xs text-mutedgrey pl-1 leading-relaxed">{faq.answer}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Tab 5: Working Hours */}
          {activeTab === 'hours' && (
            <div className="glass-panel rounded-b-3xl p-6 sm:p-8 border border-ivory/10 space-y-4">
              <h3 className="text-sm font-bold text-ivory">Clinical Schedule Matrix</h3>
              <p className="text-xs text-mutedgrey">The AI receptionist schedules caller slots exclusively within these operational hours.</p>

              <div className="divide-y divide-ivory/10 max-w-xl">
                {['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'].map((day) => {
                  const isWeekend = day === 'Sunday';
                  return (
                    <div key={day} className="py-3 flex items-center justify-between text-xs">
                      <span className="font-bold text-ivory w-28">{day}</span>
                      <span className={`px-2.5 py-0.5 rounded-full font-mono font-bold text-[11px] ${
                        isWeekend
                          ? 'bg-rose-950/40 text-rose-300 border border-rose-500/30'
                          : 'bg-emerald-950/40 text-emerald-300 border border-emerald-500/30'
                      }`}>
                        {isWeekend ? 'Closed / Triage Only' : '08:30 AM - 08:00 PM'}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Modal: Add Service */}
      <Modal isOpen={serviceModal} onClose={() => setServiceModal(false)} title="Add Treatment / Service">
        <form onSubmit={handleCreateService} className="space-y-4">
          <div>
            <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
              Service Name *
            </label>
            <input
              type="text"
              required
              value={newService.name}
              onChange={(e) => setNewService({ ...newService, name: e.target.value })}
              className="w-full px-4 py-2.5 glass-input rounded-xl text-xs"
              placeholder="e.g. Pediatric Immunization"
            />
          </div>

          <div>
            <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
              Description
            </label>
            <textarea
              rows={2}
              value={newService.description}
              onChange={(e) => setNewService({ ...newService, description: e.target.value })}
              className="w-full px-4 py-2.5 glass-input rounded-xl text-xs"
              placeholder="Short explanation of clinical procedure..."
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
                Duration (Mins)
              </label>
              <input
                type="number"
                min={5}
                max={240}
                value={newService.duration_minutes}
                onChange={(e) => setNewService({ ...newService, duration_minutes: parseInt(e.target.value) || 30 })}
                className="w-full px-4 py-2.5 glass-input rounded-xl text-xs"
              />
            </div>

            <div>
              <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
                Fee / Price (₹)
              </label>
              <input
                type="number"
                min={0}
                value={newService.price}
                onChange={(e) => setNewService({ ...newService, price: parseFloat(e.target.value) || 0 })}
                className="w-full px-4 py-2.5 glass-input rounded-xl text-xs"
              />
            </div>
          </div>

          <div className="pt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setServiceModal(false)}
              className="px-4 py-2 text-xs font-semibold text-mutedgrey hover:text-ivory"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-5 py-2.5 bg-gradient-to-r from-burnt to-amber text-warmblack font-extrabold rounded-xl text-xs uppercase tracking-wider"
            >
              Save Service
            </button>
          </div>
        </form>
      </Modal>

      {/* Modal: Add FAQ */}
      <Modal isOpen={faqModal} onClose={() => setFaqModal(false)} title="Add Knowledge Base FAQ">
        <form onSubmit={handleCreateFaq} className="space-y-4">
          <div>
            <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
              Category
            </label>
            <input
              type="text"
              value={newFaq.category}
              onChange={(e) => setNewFaq({ ...newFaq, category: e.target.value })}
              className="w-full px-4 py-2.5 glass-input rounded-xl text-xs"
              placeholder="Appointments, Fees, Insurance, Timings..."
            />
          </div>

          <div>
            <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
              Caller Question *
            </label>
            <input
              type="text"
              required
              value={newFaq.question}
              onChange={(e) => setNewFaq({ ...newFaq, question: e.target.value })}
              className="w-full px-4 py-2.5 glass-input rounded-xl text-xs"
              placeholder="e.g. Do you accept credit cards and cashless insurance?"
            />
          </div>

          <div>
            <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
              AI Answer Response *
            </label>
            <textarea
              rows={3}
              required
              value={newFaq.answer}
              onChange={(e) => setNewFaq({ ...newFaq, answer: e.target.value })}
              className="w-full px-4 py-2.5 glass-input rounded-xl text-xs"
              placeholder="Yes, we support all major cashless TPA insurance claims and card payments."
            />
          </div>

          <div className="pt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setFaqModal(false)}
              className="px-4 py-2 text-xs font-semibold text-mutedgrey hover:text-ivory"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-5 py-2.5 bg-gradient-to-r from-burnt to-amber text-warmblack font-extrabold rounded-xl text-xs uppercase tracking-wider"
            >
              Save FAQ
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
