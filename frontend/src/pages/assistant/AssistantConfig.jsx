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
  Calendar,
  Coffee,
  CalendarOff,
  AlertCircle,
} from 'lucide-react';
import Modal from '../../components/common/Modal';
import Badge from '../../components/common/Badge';
import VoiceOrb from '../../components/common/VoiceOrb';
import WaveformVisualizer from '../../components/common/WaveformVisualizer';
import { assistantService, availabilityService } from '../../services/api';

const VOICES = [
  { id: 'alloy', name: 'Alloy', tone: 'Neutral & Friendly', sampleText: 'Hello! Welcome to our clinic, how may I assist you today?' },
  { id: 'echo', name: 'Echo', tone: 'Warm & Professional', sampleText: 'Good day. I can confirm your appointment schedule right now.' },
  { id: 'fable', name: 'Fable', tone: 'Expressive & Clear', sampleText: 'Thank you for reaching out, let me check available slots.' },
  { id: 'onyx', name: 'Onyx', tone: 'Deep & Authoritative', sampleText: 'Our clinical team is available Monday through Saturday.' },
  { id: 'nova', name: 'Nova', tone: 'Energetic & Helpful', sampleText: 'Hi there! I would be delighted to help you book a visit.' },
  { id: 'shimmer', name: 'Shimmer', tone: 'Soothing & Gentle', sampleText: 'We care about your comfort. Your consultation is reserved.' },
];

const LOCALIZED_GREETINGS = {
  'en-US': (name) => `Hello! I am ${name}, your AI voice assistant at Vattara City Clinic. How may I assist your appointment today?`,
  'en-IN': (name) => `Namaste! I am ${name}, your AI receptionist at Vattara City Clinic. How may I help you book a doctor appointment today?`,
  'hi-IN': (name) => `नमस्ते! मैं ${name} हूँ, वत्तारा क्लिनिक का AI वॉइस असिस्टेंट। आज मैं आपकी क्या सहायता कर सकता हूँ?`,
  'ta-IN': (name) => `வணக்கம்! நான் ${name}, வட்டாரா மருத்துவமனையின் AI குரல் உதவியாளர். இன்று உங்கள் முன்பதிவுக்கு நான் எவ்வாறு உதவ முடியும்?`,
  'es-ES': (name) => `¡Hola! Soy ${name}, tu asistente de voz en la clínica Vattara. ¿Cómo puedo ayudarte hoy con tu cita médica?`,
  'fr-FR': (name) => `Bonjour! Je suis ${name}, votre assistant vocal à la clinique Vattara. Comment puis-je vous aider aujourd'hui?`,
};

const VOICE_PROFILES = {
  alloy: { pitch: 1.0, rate: 1.0, gender: 'neutral' },
  echo: { pitch: 0.85, rate: 0.94, gender: 'male' },
  fable: { pitch: 1.06, rate: 1.02, gender: 'neutral' },
  onyx: { pitch: 0.74, rate: 0.88, gender: 'male' },
  nova: { pitch: 1.22, rate: 1.08, gender: 'female' },
  shimmer: { pitch: 1.08, rate: 0.88, gender: 'female' },
};

const LANGUAGES = [
  { code: 'en-US', name: 'English (United States)' },
  { code: 'en-IN', name: 'English (India)' },
  { code: 'hi-IN', name: 'Hindi (India) - हिन्दी' },
  { code: 'ta-IN', name: 'Tamil (India) - தமிழ்' },
  { code: 'es-ES', name: 'Spanish - Español' },
  { code: 'fr-FR', name: 'French - Français' },
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

  // Availability Management State
  const [availability, setAvailability] = useState({
    business_id: '',
    timezone: 'Asia/Kolkata',
    weekly_schedule: [
      { day_of_week: 0, day_name: 'Monday', open_time: '09:00', close_time: '18:00', is_closed: false },
      { day_of_week: 1, day_name: 'Tuesday', open_time: '09:00', close_time: '18:00', is_closed: false },
      { day_of_week: 2, day_name: 'Wednesday', open_time: '09:00', close_time: '18:00', is_closed: false },
      { day_of_week: 3, day_name: 'Thursday', open_time: '09:00', close_time: '18:00', is_closed: false },
      { day_of_week: 4, day_name: 'Friday', open_time: '09:00', close_time: '18:00', is_closed: false },
      { day_of_week: 5, day_name: 'Saturday', open_time: '09:00', close_time: '14:00', is_closed: false },
      { day_of_week: 6, day_name: 'Sunday', open_time: '10:00', close_time: '14:00', is_closed: true },
    ],
    breaks: [],
    settings: {
      default_duration_minutes: 30,
      buffer_time_minutes: 10,
      min_advance_hours: 2,
      max_advance_days: 30,
      same_day_booking: true,
      slot_interval_minutes: 30,
    },
    holidays: [],
    special_dates: [],
  });
  const [savingAvailability, setSavingAvailability] = useState(false);
  const [breakModal, setBreakModal] = useState(false);
  const [newBreak, setNewBreak] = useState({
    day_of_week: -1,
    start_time: '13:00',
    end_time: '14:00',
    description: 'Lunch Break',
    is_active: true,
  });
  const [holidayModal, setHolidayModal] = useState(false);
  const [newHoliday, setNewHoliday] = useState({
    holiday_date: '',
    name: '',
    description: '',
  });
  const [specialDateModal, setSpecialDateModal] = useState(false);
  const [newSpecialDate, setNewSpecialDate] = useState({
    override_date: '',
    is_closed: false,
    open_time: '09:00',
    close_time: '13:00',
    description: '',
  });

  const loadData = async () => {
    setLoading(true);
    try {
      const [cData, sData, fData, aData] = await Promise.all([
        assistantService.getConfig(),
        assistantService.getServices(),
        assistantService.getFaqs(),
        availabilityService.getFullConfig().catch(() => null),
      ]);
      const defaultConfig = {
        assistant_name: 'Vattara Voice AI',
        language: 'en-US',
        voice: 'alloy',
        system_prompt: 'You are Vattara AI, the courteous and intelligent voice receptionist for Vattara City Clinic & Diagnostics. You handle patient triage, schedule appointments, explain consultation fees and clinical timings, and answer FAQs. Always be compassionate, precise, and professional.',
        business_info: 'Vattara City Clinic & Diagnostics is a multi-specialty healthcare centre offering general physician consultations, cardiology checkups, pediatrics, and diagnostic lab services.',
        working_hours: '{"monday":{"open":"08:30","close":"20:00","enabled":true},"tuesday":{"open":"08:30","close":"20:00","enabled":true},"wednesday":{"open":"08:30","close":"20:00","enabled":true},"thursday":{"open":"08:30","close":"20:00","enabled":true},"friday":{"open":"08:30","close":"20:00","enabled":true},"saturday":{"open":"09:00","close":"18:00","enabled":true},"sunday":{"open":"10:00","close":"14:00","enabled":false}}',
        is_active: true,
        enable_tanglish: true,
        ai_provider: 'mock',
        ai_model: 'gpt-4o-mini',
        stt_provider: 'deepgram',
        tts_provider: 'openai',
      };
      setConfig(cData ? { ...defaultConfig, ...cData } : defaultConfig);
      setServices(Array.isArray(sData) ? sData : []);
      setFaqs(Array.isArray(fData) ? fData : []);
      if (aData && aData.weekly_schedule) {
        setAvailability(aData);
      }
    } catch (err) {
      console.error('Failed to load assistant configuration, applying fallback config:', err);
      setConfig({
        assistant_name: 'Vattara Voice AI',
        language: 'en-US',
        voice: 'alloy',
        system_prompt: 'You are Vattara AI, the courteous and intelligent voice receptionist for Vattara City Clinic & Diagnostics. You handle patient triage, schedule appointments, explain consultation fees and clinical timings, and answer FAQs. Always be compassionate, precise, and professional.',
        business_info: 'Vattara City Clinic & Diagnostics is a multi-specialty healthcare centre offering general physician consultations, cardiology checkups, pediatrics, and diagnostic lab services.',
        working_hours: '{"monday":{"open":"08:30","close":"20:00","enabled":true},"tuesday":{"open":"08:30","close":"20:00","enabled":true},"wednesday":{"open":"08:30","close":"20:00","enabled":true},"thursday":{"open":"08:30","close":"20:00","enabled":true},"friday":{"open":"08:30","close":"20:00","enabled":true},"saturday":{"open":"09:00","close":"18:00","enabled":true},"sunday":{"open":"10:00","close":"14:00","enabled":false}}',
        is_active: true,
        enable_tanglish: true,
        ai_provider: 'mock',
        ai_model: 'gpt-4o-mini',
        stt_provider: 'deepgram',
        tts_provider: 'openai',
      });
      setServices([]);
      setFaqs([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveAvailability = async () => {
    setSavingAvailability(true);
    try {
      const res = await availabilityService.updateFullConfig(availability);
      if (res) setAvailability(res);
      showToast('Availability schedule & rules saved successfully!');
    } catch (err) {
      console.error(err);
      showToast('Failed to save availability configuration.');
    } finally {
      setSavingAvailability(false);
    }
  };

  const handleDayScheduleChange = (dayIndex, field, value) => {
    setAvailability((prev) => {
      const updated = prev.weekly_schedule.map((item) => {
        if (item.day_of_week === dayIndex) {
          return { ...item, [field]: value };
        }
        return item;
      });
      return { ...prev, weekly_schedule: updated };
    });
  };

  const handleSettingsChange = (field, value) => {
    setAvailability((prev) => ({
      ...prev,
      settings: { ...prev.settings, [field]: value },
    }));
  };

  const handleAddBreak = async (e) => {
    e?.preventDefault();
    if (newBreak.start_time >= newBreak.end_time) {
      showToast('Error: Break start time must be before end time.');
      return;
    }
    try {
      const created = await availabilityService.addBreak(newBreak);
      setAvailability((prev) => ({
        ...prev,
        breaks: [...prev.breaks, created],
      }));
      setBreakModal(false);
      setNewBreak({ day_of_week: -1, start_time: '13:00', end_time: '14:00', description: 'Lunch Break', is_active: true });
      showToast('Break window added!');
    } catch (err) {
      console.error(err);
      showToast('Failed to add break.');
    }
  };

  const handleDeleteBreak = async (id) => {
    try {
      await availabilityService.deleteBreak(id);
      setAvailability((prev) => ({
        ...prev,
        breaks: prev.breaks.filter((b) => b.id !== id),
      }));
      showToast('Break removed.');
    } catch (err) {
      console.error(err);
      showToast('Failed to delete break.');
    }
  };

  const handleAddHoliday = async (e) => {
    e?.preventDefault();
    if (!newHoliday.holiday_date || !newHoliday.name) {
      showToast('Please provide holiday date and title.');
      return;
    }
    try {
      const created = await availabilityService.addHoliday(newHoliday);
      setAvailability((prev) => {
        const filtered = prev.holidays.filter((h) => h.holiday_date !== created.holiday_date);
        return {
          ...prev,
          holidays: [...filtered, created].sort((a, b) => a.holiday_date.localeCompare(b.holiday_date)),
        };
      });
      setHolidayModal(false);
      setNewHoliday({ holiday_date: '', name: '', description: '' });
      showToast('Holiday closure added!');
    } catch (err) {
      console.error(err);
      showToast('Failed to add holiday.');
    }
  };

  const handleDeleteHoliday = async (id) => {
    try {
      await availabilityService.deleteHoliday(id);
      setAvailability((prev) => ({
        ...prev,
        holidays: prev.holidays.filter((h) => h.id !== id),
      }));
      showToast('Holiday removed.');
    } catch (err) {
      console.error(err);
      showToast('Failed to delete holiday.');
    }
  };

  const handleAddSpecialDate = async (e) => {
    e?.preventDefault();
    if (!newSpecialDate.override_date) {
      showToast('Please select override date.');
      return;
    }
    if (!newSpecialDate.is_closed && (newSpecialDate.open_time >= newSpecialDate.close_time)) {
      showToast('Error: Open time must be earlier than close time.');
      return;
    }
    try {
      const created = await availabilityService.addSpecialDate(newSpecialDate);
      setAvailability((prev) => {
        const filtered = prev.special_dates.filter((s) => s.override_date !== created.override_date);
        return {
          ...prev,
          special_dates: [...filtered, created].sort((a, b) => a.override_date.localeCompare(b.override_date)),
        };
      });
      setSpecialDateModal(false);
      setNewSpecialDate({ override_date: '', is_closed: false, open_time: '09:00', close_time: '13:00', description: '' });
      showToast('Special date override saved!');
    } catch (err) {
      console.error(err);
      showToast('Failed to add special date override.');
    }
  };

  const handleDeleteSpecialDate = async (id) => {
    try {
      await availabilityService.deleteSpecialDate(id);
      setAvailability((prev) => ({
        ...prev,
        special_dates: prev.special_dates.filter((s) => s.id !== id),
      }));
      showToast('Special date override removed.');
    } catch (err) {
      console.error(err);
      showToast('Failed to delete override.');
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
        const voiceName = voiceInfo?.name || 'Vattara';
        
        // Generate phrase according to configured spoken language dialect
        const langCode = config?.language || 'en-US';
        const phraseGenerator = LOCALIZED_GREETINGS[langCode] || LOCALIZED_GREETINGS['en-US'];
        const sampleText = phraseGenerator(voiceName);

        const utterance = new SpeechSynthesisUtterance(sampleText);
        utterance.lang = langCode;

        // Apply distinct neural speech profile
        const profile = VOICE_PROFILES[voiceId] || { pitch: 1.0, rate: 1.0, gender: 'neutral' };
        utterance.pitch = profile.pitch;
        utterance.rate = profile.rate;

        // Match available browser voices for this language and persona gender
        const allVoices = window.speechSynthesis.getVoices();
        const langPrefix = langCode.split('-')[0].toLowerCase();
        const matchingVoices = allVoices.filter(
          (v) => v.lang.toLowerCase().startsWith(langPrefix) || v.lang.toLowerCase().replace('_', '-') === langCode.toLowerCase()
        );

        if (matchingVoices.length > 0) {
          if (profile.gender === 'female') {
            utterance.voice =
              matchingVoices.find((v) => /female|woman|zira|samantha|victoria|karen/i.test(v.name)) ||
              matchingVoices[0];
          } else if (profile.gender === 'male') {
            utterance.voice =
              matchingVoices.find((v) => /male|man|david|guy|george|alex/i.test(v.name)) ||
              matchingVoices[0];
          } else {
            utterance.voice = matchingVoices[0];
          }
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

  if (loading) {
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

          <VoiceOrb
            size="md"
            isSpeaking={!!playingVoice || config.is_active}
            isListening={!config.is_active}
          />

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
              "{(LOCALIZED_GREETINGS[config.language] || LOCALIZED_GREETINGS['en-US'])(VOICES.find((v) => v.id === config.voice)?.name || 'Vattara')}"
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
              { id: 'hours', label: 'Availability & Hours', icon: Clock },
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

              {/* AI Engine & Multilingual Configuration */}
              <div className="p-5 rounded-2xl bg-charcoal border border-ivory/10 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-amber" />
                    <h4 className="text-xs font-extrabold uppercase tracking-wider text-ivory">
                      AI Language Processing Engine
                    </h4>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-950/80 text-emerald-400 border border-emerald-500/30 font-bold">
                    Provider Independent
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-[10px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
                      AI Intelligence Provider
                    </label>
                    <select
                      value={config.ai_provider || 'mock'}
                      onChange={(e) => setConfig({ ...config, ai_provider: e.target.value })}
                      className="w-full px-3 py-2.5 glass-input rounded-xl text-xs font-medium focus:ring-1 focus:ring-burnt bg-charcoal"
                    >
                      <option value="mock" className="bg-charcoal text-ivory">Deterministic NLU Engine (Local & Offline)</option>
                      <option value="openai" className="bg-charcoal text-ivory">OpenAI (GPT-4o / GPT-4o-mini)</option>
                      <option value="deepseek" className="bg-charcoal text-ivory">DeepSeek (DeepSeek-V3 / Chat)</option>
                      <option value="gemini" className="bg-charcoal text-ivory">Google Gemini (Gemini 1.5 / 2.0)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-[10px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
                      Model Identifier
                    </label>
                    <input
                      type="text"
                      value={config.ai_model || 'gpt-4o-mini'}
                      onChange={(e) => setConfig({ ...config, ai_model: e.target.value })}
                      className="w-full px-3 py-2.5 glass-input rounded-xl text-xs font-medium focus:ring-1 focus:ring-burnt"
                      placeholder="e.g. gpt-4o-mini, deepseek-chat, gemini-1.5-flash"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                  <div>
                    <label className="block text-[10px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
                      Speech-to-Text (STT) Provider
                    </label>
                    <select
                      value={config.stt_provider || 'mock'}
                      onChange={(e) => setConfig({ ...config, stt_provider: e.target.value })}
                      className="w-full px-3 py-2.5 glass-input rounded-xl text-xs font-medium focus:ring-1 focus:ring-burnt bg-charcoal"
                    >
                      <option value="mock" className="bg-charcoal text-ivory">Mock / Offline STT</option>
                      <option value="deepgram" className="bg-charcoal text-ivory">Deepgram Nova-2 (Ultra-fast Streaming)</option>
                      <option value="openai" className="bg-charcoal text-ivory">OpenAI Whisper</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-[10px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
                      Text-to-Speech (TTS) Provider
                    </label>
                    <select
                      value={config.tts_provider || 'mock'}
                      onChange={(e) => setConfig({ ...config, tts_provider: e.target.value })}
                      className="w-full px-3 py-2.5 glass-input rounded-xl text-xs font-medium focus:ring-1 focus:ring-burnt bg-charcoal"
                    >
                      <option value="mock" className="bg-charcoal text-ivory">Mock / Offline Audio</option>
                      <option value="elevenlabs" className="bg-charcoal text-ivory">ElevenLabs Neural Voice</option>
                      <option value="openai" className="bg-charcoal text-ivory">OpenAI TTS-1-HD</option>
                      <option value="deepgram" className="bg-charcoal text-ivory">Deepgram Aura</option>
                    </select>
                  </div>
                </div>

                <div className="pt-2">
                  <label className="block text-[10px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
                    Emergency Fallback & Human Escalation Phone
                  </label>
                  <input
                    type="text"
                    value={config.fallback_number || ''}
                    onChange={(e) => setConfig({ ...config, fallback_number: e.target.value })}
                    className="w-full px-3 py-2.5 glass-input rounded-xl text-xs font-mono focus:ring-1 focus:ring-burnt"
                    placeholder="e.g. +91 44 2828 9000 (Transfers call if caller requests human receptionist)"
                  />
                </div>

                {/* Tanglish Toggle */}
                <div className="pt-3 border-t border-ivory/5 flex items-center justify-between">
                  <div>
                    <span className="text-xs font-bold text-ivory block">
                      Tanglish Language Support (தமிழ் + English)
                    </span>
                    <span className="text-[10px] text-mutedgrey block">
                      Allows patients to converse naturally in Tamil using English script (e.g., "naalaiki slot iruka").
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setConfig({ ...config, enable_tanglish: !config.enable_tanglish })}
                    className="flex items-center gap-1.5 text-xs font-bold focus:outline-none"
                  >
                    {config.enable_tanglish ? (
                      <span className="text-emerald-400 flex items-center gap-1">
                        <ToggleRight className="w-7 h-7 text-emerald-400" />
                        <span className="text-[10px] font-mono font-bold">Enabled</span>
                      </span>
                    ) : (
                      <span className="text-mutedgrey flex items-center gap-1">
                        <ToggleLeft className="w-7 h-7 text-mutedgrey" />
                        <span className="text-[10px] font-mono font-bold">Disabled</span>
                      </span>
                    )}
                  </button>
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

          {/* Tab 5: Availability & Working Hours */}
          {activeTab === 'hours' && (
            <div className="glass-panel rounded-b-3xl p-6 sm:p-8 border border-ivory/10 space-y-8">
              {/* Top Banner & Save Action */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-ivory/10">
                <div>
                  <h3 className="text-sm font-bold text-ivory flex items-center gap-2">
                    <Clock className="w-4 h-4 text-amber" />
                    Availability Management & Working Schedule
                  </h3>
                  <p className="text-xs text-mutedgrey mt-0.5">
                    Configure weekly hours, scheduled breaks, appointment buffer rules, holidays, and date overrides. Changes immediately govern autonomous AI voice bookings.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleSaveAvailability}
                  disabled={savingAvailability}
                  className="flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-burnt to-amber text-warmblack font-extrabold text-xs uppercase tracking-wider shadow-md hover:opacity-95 transition-all disabled:opacity-50 shrink-0"
                >
                  <Save className="w-4 h-4" />
                  {savingAvailability ? 'Saving Availability...' : 'Save Availability Changes'}
                </button>
              </div>

              {/* Section 1: Weekly Working Schedule */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="text-xs font-bold text-ivory uppercase tracking-wider flex items-center gap-2">
                      <Calendar className="w-3.5 h-3.5 text-amber" />
                      Weekly Working Schedule
                    </h4>
                    <p className="text-[11px] text-mutedgrey mt-0.5">
                      Enable or disable operating days and set shift opening and closing hours.
                    </p>
                  </div>
                </div>

                <div className="space-y-2.5 max-w-3xl">
                  {availability.weekly_schedule.map((item) => (
                    <div
                      key={item.day_of_week}
                      className={`p-3.5 rounded-2xl glass-card border flex flex-col sm:flex-row sm:items-center justify-between gap-3 transition-all ${
                        item.is_closed
                          ? 'border-ivory/5 bg-graphite/40 opacity-75'
                          : 'border-ivory/15 bg-graphite/80'
                      }`}
                    >
                      <div className="flex items-center gap-3 w-36">
                        <span className="text-xs font-bold text-ivory tracking-wide">{item.day_name}</span>
                      </div>

                      <div className="flex items-center gap-4">
                        <button
                          type="button"
                          onClick={() => handleDayScheduleChange(item.day_of_week, 'is_closed', !item.is_closed)}
                          className={`flex items-center gap-1.5 px-3 py-1 rounded-xl text-xs font-bold transition-all ${
                            item.is_closed
                              ? 'bg-rose-500/10 text-rose-300 border border-rose-500/30'
                              : 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/30'
                          }`}
                        >
                          {item.is_closed ? (
                            <ToggleLeft className="w-4 h-4 text-rose-400" />
                          ) : (
                            <ToggleRight className="w-4 h-4 text-emerald-400" />
                          )}
                          {item.is_closed ? 'Closed' : 'Open'}
                        </button>

                        {!item.is_closed ? (
                          <div className="flex items-center gap-2">
                            <input
                              type="time"
                              value={item.open_time}
                              onChange={(e) => handleDayScheduleChange(item.day_of_week, 'open_time', e.target.value)}
                              className="px-2.5 py-1.5 rounded-lg glass-input text-xs font-mono font-bold text-ivory border border-ivory/20 bg-warmblack/60 focus:border-amber outline-none"
                            />
                            <span className="text-mutedgrey text-xs">to</span>
                            <input
                              type="time"
                              value={item.close_time}
                              onChange={(e) => handleDayScheduleChange(item.day_of_week, 'close_time', e.target.value)}
                              className="px-2.5 py-1.5 rounded-lg glass-input text-xs font-mono font-bold text-ivory border border-ivory/20 bg-warmblack/60 focus:border-amber outline-none"
                            />
                          </div>
                        ) : (
                          <span className="text-xs text-mutedgrey italic py-1">Business Closed (No Slots Offered)</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Section 2: Break Management */}
              <div className="space-y-4 pt-4 border-t border-ivory/10">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="text-xs font-bold text-ivory uppercase tracking-wider flex items-center gap-2">
                      <Coffee className="w-3.5 h-3.5 text-amber" />
                      Break Management
                    </h4>
                    <p className="text-[11px] text-mutedgrey mt-0.5">
                      Configure recurring lunch hours and staff rest breaks. The AI voice agent will never offer slots overlapping these windows.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setBreakModal(true)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-burnt hover:bg-burnt-dark text-warmblack font-extrabold text-xs shadow transition-all"
                  >
                    <Plus className="w-3.5 h-3.5" /> Add Break
                  </button>
                </div>

                {availability.breaks.length === 0 ? (
                  <div className="p-4 rounded-2xl glass-card border border-ivory/10 text-center py-6">
                    <Coffee className="w-8 h-8 text-mutedgrey/50 mx-auto mb-2" />
                    <p className="text-xs text-mutedgrey">No breaks configured. The AI will consider daily working hours continuous.</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-3xl">
                    {availability.breaks.map((b) => {
                      const dayLabel = b.day_of_week === -1
                        ? 'All Days (Mon-Sun)'
                        : ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][b.day_of_week] || 'Custom Day';
                      return (
                        <div
                          key={b.id || `${b.day_of_week}-${b.start_time}`}
                          className="p-3.5 rounded-2xl glass-card border border-ivory/10 flex items-center justify-between gap-3"
                        >
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-bold text-ivory">{b.description || 'Break'}</span>
                              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber/10 text-amber border border-amber/20">
                                {dayLabel}
                              </span>
                            </div>
                            <p className="text-[11px] font-mono text-mutedgrey mt-1">
                              {b.start_time} - {b.end_time}
                            </p>
                          </div>
                          <button
                            type="button"
                            onClick={() => handleDeleteBreak(b.id)}
                            className="p-1.5 text-mutedgrey hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors"
                            title="Delete break"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Section 3: Appointment Rules & Settings */}
              <div className="space-y-4 pt-4 border-t border-ivory/10">
                <div>
                  <h4 className="text-xs font-bold text-ivory uppercase tracking-wider flex items-center gap-2">
                    <Sliders className="w-3.5 h-3.5 text-amber" />
                    Appointment Booking Rules & Buffer Settings
                  </h4>
                  <p className="text-[11px] text-mutedgrey mt-0.5">
                    Tune autonomous booking constraints, buffer windows between appointments, and advance reservation limits.
                  </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 max-w-3xl">
                  {/* Default Duration */}
                  <div className="p-4 rounded-2xl glass-card border border-ivory/10 space-y-1.5">
                    <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey">
                      Default Duration (Minutes)
                    </label>
                    <input
                      type="number"
                      min={5}
                      max={480}
                      step={5}
                      value={availability.settings.default_duration_minutes}
                      onChange={(e) => handleSettingsChange('default_duration_minutes', parseInt(e.target.value) || 30)}
                      className="w-full px-3 py-2 rounded-xl glass-input text-xs font-mono font-bold text-ivory border border-ivory/20 bg-warmblack/60 focus:border-amber outline-none"
                    />
                    <p className="text-[10px] text-mutedgrey">Base slot block length when no specific service duration is set.</p>
                  </div>

                  {/* Buffer Time */}
                  <div className="p-4 rounded-2xl glass-card border border-ivory/10 space-y-1.5">
                    <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey">
                      Buffer Time Between Appointments (Minutes)
                    </label>
                    <input
                      type="number"
                      min={0}
                      max={120}
                      step={5}
                      value={availability.settings.buffer_time_minutes}
                      onChange={(e) => handleSettingsChange('buffer_time_minutes', parseInt(e.target.value) || 0)}
                      className="w-full px-3 py-2 rounded-xl glass-input text-xs font-mono font-bold text-ivory border border-ivory/20 bg-warmblack/60 focus:border-amber outline-none"
                    />
                    <p className="text-[10px] text-mutedgrey">Rest/sanitization gap enforced between consecutive bookings.</p>
                  </div>

                  {/* Slot Interval */}
                  <div className="p-4 rounded-2xl glass-card border border-ivory/10 space-y-1.5">
                    <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey">
                      Slot Booking Interval (Minutes)
                    </label>
                    <input
                      type="number"
                      min={5}
                      max={120}
                      step={5}
                      value={availability.settings.slot_interval_minutes}
                      onChange={(e) => handleSettingsChange('slot_interval_minutes', parseInt(e.target.value) || 30)}
                      className="w-full px-3 py-2 rounded-xl glass-input text-xs font-mono font-bold text-ivory border border-ivory/20 bg-warmblack/60 focus:border-amber outline-none"
                    />
                    <p className="text-[10px] text-mutedgrey">Cadence for generated slot start times (e.g. every 15 or 30 mins).</p>
                  </div>

                  {/* Minimum Advance Notice */}
                  <div className="p-4 rounded-2xl glass-card border border-ivory/10 space-y-1.5">
                    <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey">
                      Minimum Advance Notice (Hours)
                    </label>
                    <input
                      type="number"
                      min={0}
                      max={720}
                      value={availability.settings.min_advance_hours}
                      onChange={(e) => handleSettingsChange('min_advance_hours', parseInt(e.target.value) || 0)}
                      className="w-full px-3 py-2 rounded-xl glass-input text-xs font-mono font-bold text-ivory border border-ivory/20 bg-warmblack/60 focus:border-amber outline-none"
                    />
                    <p className="text-[10px] text-mutedgrey">Earliest allowable booking from present call time.</p>
                  </div>

                  {/* Maximum Advance Booking Window */}
                  <div className="p-4 rounded-2xl glass-card border border-ivory/10 space-y-1.5">
                    <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey">
                      Max Advance Window (Days)
                    </label>
                    <input
                      type="number"
                      min={1}
                      max={365}
                      value={availability.settings.max_advance_days}
                      onChange={(e) => handleSettingsChange('max_advance_days', parseInt(e.target.value) || 30)}
                      className="w-full px-3 py-2 rounded-xl glass-input text-xs font-mono font-bold text-ivory border border-ivory/20 bg-warmblack/60 focus:border-amber outline-none"
                    />
                    <p className="text-[10px] text-mutedgrey">How far in advance customers can schedule future visits.</p>
                  </div>

                  {/* Same-Day Booking Toggle */}
                  <div className="p-4 rounded-2xl glass-card border border-ivory/10 space-y-1.5 flex flex-col justify-between">
                    <div>
                      <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey">
                        Same-Day Booking
                      </label>
                      <p className="text-[10px] text-mutedgrey mt-0.5">Permit customers to book slots for today if advance notice is met.</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleSettingsChange('same_day_booking', !availability.settings.same_day_booking)}
                      className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-bold transition-all w-fit ${
                        availability.settings.same_day_booking
                          ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/30'
                          : 'bg-rose-500/10 text-rose-300 border border-rose-500/30'
                      }`}
                    >
                      {availability.settings.same_day_booking ? (
                        <ToggleRight className="w-4 h-4 text-emerald-400" />
                      ) : (
                        <ToggleLeft className="w-4 h-4 text-rose-400" />
                      )}
                      {availability.settings.same_day_booking ? 'Allowed' : 'Disallowed'}
                    </button>
                  </div>
                </div>
              </div>

              {/* Section 4: Holiday Management */}
              <div className="space-y-4 pt-4 border-t border-ivory/10">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="text-xs font-bold text-ivory uppercase tracking-wider flex items-center gap-2">
                      <CalendarOff className="w-3.5 h-3.5 text-amber" />
                      Holiday Closures
                    </h4>
                    <p className="text-[11px] text-mutedgrey mt-0.5">
                      Mark official dates where the clinic/business is fully closed. Voice AI will inform callers and propose alternate days.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setHolidayModal(true)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-burnt hover:bg-burnt-dark text-warmblack font-extrabold text-xs shadow transition-all"
                  >
                    <Plus className="w-3.5 h-3.5" /> Add Holiday
                  </button>
                </div>

                {availability.holidays.length === 0 ? (
                  <div className="p-4 rounded-2xl glass-card border border-ivory/10 text-center py-6">
                    <CalendarOff className="w-8 h-8 text-mutedgrey/50 mx-auto mb-2" />
                    <p className="text-xs text-mutedgrey">No holidays scheduled. The AI will observe standard weekly schedules.</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-3xl">
                    {availability.holidays.map((h) => (
                      <div
                        key={h.id || h.holiday_date}
                        className="p-3.5 rounded-2xl glass-card border border-rose-500/20 bg-rose-950/20 flex items-center justify-between gap-3"
                      >
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-bold text-rose-200">{h.name}</span>
                            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300">
                              {h.holiday_date}
                            </span>
                          </div>
                          {h.description && (
                            <p className="text-[11px] text-mutedgrey mt-0.5">{h.description}</p>
                          )}
                        </div>
                        <button
                          type="button"
                          onClick={() => handleDeleteHoliday(h.id)}
                          className="p-1.5 text-mutedgrey hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors"
                          title="Delete holiday"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Section 5: Special Date Overrides */}
              <div className="space-y-4 pt-4 border-t border-ivory/10">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="text-xs font-bold text-ivory uppercase tracking-wider flex items-center gap-2">
                      <Sparkles className="w-3.5 h-3.5 text-amber" />
                      Special Date Overrides (Custom Hours / One-Off Closures)
                    </h4>
                    <p className="text-[11px] text-mutedgrey mt-0.5">
                      Configure custom hours for specific dates (e.g. half-day on festival eve) or full-day closures without altering regular weekly schedules.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setSpecialDateModal(true)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-burnt hover:bg-burnt-dark text-warmblack font-extrabold text-xs shadow transition-all"
                  >
                    <Plus className="w-3.5 h-3.5" /> Add Special Date
                  </button>
                </div>

                {availability.special_dates.length === 0 ? (
                  <div className="p-4 rounded-2xl glass-card border border-ivory/10 text-center py-6">
                    <Sparkles className="w-8 h-8 text-mutedgrey/50 mx-auto mb-2" />
                    <p className="text-xs text-mutedgrey">No special date overrides set. Standard weekly operating hours apply.</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-3xl">
                    {availability.special_dates.map((s) => (
                      <div
                        key={s.id || s.override_date}
                        className="p-3.5 rounded-2xl glass-card border border-ivory/10 flex items-center justify-between gap-3"
                      >
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-bold font-mono text-ivory">{s.override_date}</span>
                            <span
                              className={`text-[10px] font-mono px-2 py-0.5 rounded-full font-bold ${
                                s.is_closed
                                  ? 'bg-rose-500/20 text-rose-300'
                                  : 'bg-amber/15 text-amber border border-amber/30'
                              }`}
                            >
                              {s.is_closed ? 'Full Day Closed' : `${s.open_time} - ${s.close_time}`}
                            </span>
                          </div>
                          {s.description && (
                            <p className="text-[11px] text-mutedgrey mt-1">{s.description}</p>
                          )}
                        </div>
                        <button
                          type="button"
                          onClick={() => handleDeleteSpecialDate(s.id)}
                          className="p-1.5 text-mutedgrey hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors"
                          title="Delete special date"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Bottom Sticky Action Bar */}
              <div className="pt-6 border-t border-ivory/10 flex justify-end">
                <button
                  type="button"
                  onClick={handleSaveAvailability}
                  disabled={savingAvailability}
                  className="flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-burnt to-amber text-warmblack font-extrabold text-xs uppercase tracking-wider shadow-lg hover:opacity-95 transition-all disabled:opacity-50"
                >
                  <Save className="w-4 h-4" />
                  {savingAvailability ? 'Saving Availability Settings...' : 'Save All Availability Changes'}
                </button>
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

      {/* Modal: Add Scheduled Break */}
      <Modal isOpen={breakModal} onClose={() => setBreakModal(false)} title="Add Scheduled Break Window">
        <form onSubmit={handleAddBreak} className="space-y-4">
          <div>
            <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
              Applicable Day *
            </label>
            <select
              value={newBreak.day_of_week}
              onChange={(e) => setNewBreak({ ...newBreak, day_of_week: parseInt(e.target.value) })}
              className="w-full px-4 py-2.5 glass-input rounded-xl text-xs font-bold text-ivory bg-graphite"
            >
              <option value={-1} className="bg-graphite text-ivory">All Days (Monday - Sunday)</option>
              <option value={0} className="bg-graphite text-ivory">Monday</option>
              <option value={1} className="bg-graphite text-ivory">Tuesday</option>
              <option value={2} className="bg-graphite text-ivory">Wednesday</option>
              <option value={3} className="bg-graphite text-ivory">Thursday</option>
              <option value={4} className="bg-graphite text-ivory">Friday</option>
              <option value={5} className="bg-graphite text-ivory">Saturday</option>
              <option value={6} className="bg-graphite text-ivory">Sunday</option>
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
                Start Time *
              </label>
              <input
                type="time"
                required
                value={newBreak.start_time}
                onChange={(e) => setNewBreak({ ...newBreak, start_time: e.target.value })}
                className="w-full px-4 py-2.5 glass-input rounded-xl text-xs font-mono font-bold text-ivory"
              />
            </div>

            <div>
              <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
                End Time *
              </label>
              <input
                type="time"
                required
                value={newBreak.end_time}
                onChange={(e) => setNewBreak({ ...newBreak, end_time: e.target.value })}
                className="w-full px-4 py-2.5 glass-input rounded-xl text-xs font-mono font-bold text-ivory"
              />
            </div>
          </div>

          <div>
            <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
              Description / Label *
            </label>
            <input
              type="text"
              required
              value={newBreak.description}
              onChange={(e) => setNewBreak({ ...newBreak, description: e.target.value })}
              className="w-full px-4 py-2.5 glass-input rounded-xl text-xs text-ivory"
              placeholder="e.g. Lunch Hour, Doctor Rest Period"
            />
          </div>

          <div className="pt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setBreakModal(false)}
              className="px-4 py-2 text-xs font-semibold text-mutedgrey hover:text-ivory"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-5 py-2.5 bg-gradient-to-r from-burnt to-amber text-warmblack font-extrabold rounded-xl text-xs uppercase tracking-wider"
            >
              Save Break
            </button>
          </div>
        </form>
      </Modal>

      {/* Modal: Add Holiday */}
      <Modal isOpen={holidayModal} onClose={() => setHolidayModal(false)} title="Add Official Holiday Closure">
        <form onSubmit={handleAddHoliday} className="space-y-4">
          <div>
            <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
              Holiday Date *
            </label>
            <input
              type="date"
              required
              value={newHoliday.holiday_date}
              onChange={(e) => setNewHoliday({ ...newHoliday, holiday_date: e.target.value })}
              className="w-full px-4 py-2.5 glass-input rounded-xl text-xs font-mono font-bold text-ivory"
            />
          </div>

          <div>
            <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
              Holiday Name / Title *
            </label>
            <input
              type="text"
              required
              value={newHoliday.name}
              onChange={(e) => setNewHoliday({ ...newHoliday, name: e.target.value })}
              className="w-full px-4 py-2.5 glass-input rounded-xl text-xs text-ivory"
              placeholder="e.g. Diwali Festival, National Day"
            />
          </div>

          <div>
            <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
              Description / Notes (Optional)
            </label>
            <input
              type="text"
              value={newHoliday.description}
              onChange={(e) => setNewHoliday({ ...newHoliday, description: e.target.value })}
              className="w-full px-4 py-2.5 glass-input rounded-xl text-xs text-ivory"
              placeholder="e.g. Entire clinic and diagnostics facility closed for festival"
            />
          </div>

          <div className="pt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setHolidayModal(false)}
              className="px-4 py-2 text-xs font-semibold text-mutedgrey hover:text-ivory"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-5 py-2.5 bg-gradient-to-r from-burnt to-amber text-warmblack font-extrabold rounded-xl text-xs uppercase tracking-wider"
            >
              Save Holiday
            </button>
          </div>
        </form>
      </Modal>

      {/* Modal: Add Special Date Override */}
      <Modal isOpen={specialDateModal} onClose={() => setSpecialDateModal(false)} title="Add Date Hours Override">
        <form onSubmit={handleAddSpecialDate} className="space-y-4">
          <div>
            <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
              Target Date *
            </label>
            <input
              type="date"
              required
              value={newSpecialDate.override_date}
              onChange={(e) => setNewSpecialDate({ ...newSpecialDate, override_date: e.target.value })}
              className="w-full px-4 py-2.5 glass-input rounded-xl text-xs font-mono font-bold text-ivory"
            />
          </div>

          <div>
            <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
              Override Mode *
            </label>
            <div className="flex gap-4 pt-1">
              <label className="flex items-center gap-2 cursor-pointer text-xs font-bold text-ivory">
                <input
                  type="radio"
                  name="override_mode"
                  checked={!newSpecialDate.is_closed}
                  onChange={() => setNewSpecialDate({ ...newSpecialDate, is_closed: false })}
                  className="accent-amber"
                />
                Custom Operating Hours
              </label>
              <label className="flex items-center gap-2 cursor-pointer text-xs font-bold text-rose-300">
                <input
                  type="radio"
                  name="override_mode"
                  checked={newSpecialDate.is_closed}
                  onChange={() => setNewSpecialDate({ ...newSpecialDate, is_closed: true })}
                  className="accent-rose-500"
                />
                Full Day Closure
              </label>
            </div>
          </div>

          {!newSpecialDate.is_closed && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
                  Open Time *
                </label>
                <input
                  type="time"
                  required
                  value={newSpecialDate.open_time}
                  onChange={(e) => setNewSpecialDate({ ...newSpecialDate, open_time: e.target.value })}
                  className="w-full px-4 py-2.5 glass-input rounded-xl text-xs font-mono font-bold text-ivory"
                />
              </div>

              <div>
                <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
                  Close Time *
                </label>
                <input
                  type="time"
                  required
                  value={newSpecialDate.close_time}
                  onChange={(e) => setNewSpecialDate({ ...newSpecialDate, close_time: e.target.value })}
                  className="w-full px-4 py-2.5 glass-input rounded-xl text-xs font-mono font-bold text-ivory"
                />
              </div>
            </div>
          )}

          <div>
            <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-mutedgrey mb-1">
              Reason / Label (Optional)
            </label>
            <input
              type="text"
              value={newSpecialDate.description}
              onChange={(e) => setNewSpecialDate({ ...newSpecialDate, description: e.target.value })}
              className="w-full px-4 py-2.5 glass-input rounded-xl text-xs text-ivory"
              placeholder="e.g. Early closing for facility maintenance"
            />
          </div>

          <div className="pt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setSpecialDateModal(false)}
              className="px-4 py-2 text-xs font-semibold text-mutedgrey hover:text-ivory"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-5 py-2.5 bg-gradient-to-r from-burnt to-amber text-warmblack font-extrabold rounded-xl text-xs uppercase tracking-wider"
            >
              Save Override
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
