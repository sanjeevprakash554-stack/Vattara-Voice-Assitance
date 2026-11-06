import axios from 'axios';

const api = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10000,
});

// Attach Authorization Bearer token from localStorage
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('vattara_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for session expiration handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      // Do not redirect on login route itself
      if (!window.location.pathname.includes('/login')) {
        console.warn('Session expired or unauthorized request. Redirecting to login.');
      }
    }
    return Promise.reject(error);
  }
);

// ------------------------------------------------------------------------------
// Fallback Mock Data Store (used gracefully if local backend is offline)
// ------------------------------------------------------------------------------
export const isUsingMockFallback = { current: false };

const MOCK_STORAGE_KEY = 'vattara_mock_db';
function getMockDb() {
  const existing = localStorage.getItem(MOCK_STORAGE_KEY);
  if (existing) {
    try {
      return JSON.parse(existing);
    } catch (e) {
      // parse failed, regenerate
    }
  }

  const initial = {
    business: {
      id: 'demo-biz-1',
      name: 'Vattara City Clinic & Diagnostics',
      vertical: 'clinic',
      phone: '+91 44 2828 9000',
      email: 'contact@vattaraclinic.com',
      timezone: 'Asia/Kolkata',
      address: '42, Anna Salai, Chennai, Tamil Nadu',
      is_active: true,
    },
    user: {
      id: 'demo-user-1',
      full_name: 'Dr. Rajesh Kumar',
      email: 'admin@vattara.com',
      role: 'admin',
    },
    assistant: {
      assistant_name: 'Vattara Voice AI',
      language: 'en-US',
      voice: 'alloy',
      system_prompt: 'You are Vattara AI, the voice receptionist for Vattara City Clinic.',
      business_info: 'Multi-specialty healthcare centre offering physician consultations and lab diagnostics.',
      working_hours: '{"monday":{"open":"08:30","close":"20:00","enabled":true},"tuesday":{"open":"08:30","close":"20:00","enabled":true},"wednesday":{"open":"08:30","close":"20:00","enabled":true},"thursday":{"open":"08:30","close":"20:00","enabled":true},"friday":{"open":"08:30","close":"20:00","enabled":true},"saturday":{"open":"09:00","close":"18:00","enabled":true},"sunday":{"open":"10:00","close":"14:00","enabled":false}}',
      is_active: true,
    },
    services: [
      { id: 'srv-1', name: 'General Physician Consultation', description: 'Routine health checkup', duration_minutes: 30, price: 500, is_active: true },
      { id: 'srv-2', name: 'Cardiology Consultation & ECG', description: 'Cardiac checkup with ECG', duration_minutes: 45, price: 1200, is_active: true },
      { id: 'srv-3', name: 'Pediatric Health Checkup', description: 'Child immunization & review', duration_minutes: 30, price: 700, is_active: true },
      { id: 'srv-4', name: 'Full Body Blood Diagnostics', description: 'Lipid, CBC, and diabetes test', duration_minutes: 15, price: 1500, is_active: true },
    ],
    faqs: [
      { id: 'faq-1', category: 'Appointments', question: 'How do I book an appointment?', answer: 'Call our AI receptionist anytime or reserve online.', is_active: true },
      { id: 'faq-2', category: 'Pricing', question: 'What is the consultation fee for a General Physician?', answer: 'Standard fee is ₹500.', is_active: true },
      { id: 'faq-3', category: 'Insurance', question: 'Do you accept cashless health insurance?', answer: 'Yes, all major TPAs are supported.', is_active: true },
    ],
    customers: [
      { id: 'cust-1', name: 'Ananya Sharma', phone: '+91 98401 23456', email: 'ananya.sharma@example.com', notes: 'Seasonal allergies', total_calls: 3, total_appointments: 1 },
      { id: 'cust-2', name: 'Vikramaditya Raman', phone: '+91 98840 98765', email: 'vikram.raman@example.com', notes: 'Cardiac patient', total_calls: 2, total_appointments: 1 },
      { id: 'cust-3', name: 'Meera Swaminathan', phone: '+91 94441 55678', email: 'meera.s@example.com', notes: 'Pediatric visits', total_calls: 1, total_appointments: 1 },
      { id: 'cust-4', name: 'Karthik Natarajan', phone: '+91 97910 11223', email: 'karthik.n@example.com', notes: 'Dental checkups', total_calls: 4, total_appointments: 2 },
    ],
    calls: [
      { id: 'call-1', caller_name: 'Ananya Sharma', caller_phone: '+91 98401 23456', call_type: 'incoming', status: 'completed', duration_seconds: 168, summary: 'Inquired about Saturday morning cardiology slots and booked consultation.', transcript: 'AI: Hello, thank you for calling Vattara City Clinic.\nCaller: I want to know about Saturday cardiology.\nAI: We have a slot at 10:30 AM with Dr. Raghavan.\nCaller: Great, book it please!\nAI: Confirmed for Saturday 10:30 AM.', initiated_at: new Date(Date.now() - 3600000 * 2).toISOString() },
      { id: 'call-2', caller_name: 'Vikramaditya Raman', caller_phone: '+91 98840 98765', call_type: 'incoming', status: 'completed', duration_seconds: 195, summary: 'Clarified fasting requirements for complete blood lipid panel.', transcript: 'Caller asked about lipid profile fasting. AI instructed 10-12 hours fasting with water allowed.', initiated_at: new Date(Date.now() - 3600000 * 5).toISOString() },
      { id: 'call-3', caller_name: 'Meera Swaminathan', caller_phone: '+91 94441 55678', call_type: 'outgoing', status: 'completed', duration_seconds: 84, summary: 'Automated voice reminder for upcoming pediatric booster.', transcript: 'AI delivered reminder for pediatric immunization.', initiated_at: new Date(Date.now() - 3600000 * 8).toISOString() },
      { id: 'call-4', caller_name: 'Unknown Caller', caller_phone: '+91 98412 88990', call_type: 'incoming', status: 'missed', duration_seconds: 0, summary: 'Missed call after clinic hours.', transcript: 'Disconnected after 4 rings.', initiated_at: new Date(Date.now() - 3600000 * 14).toISOString() },
    ],
    appointments: [
      { id: 'appt-1', customer_id: 'cust-1', service_id: 'srv-2', appointment_time: new Date(Date.now() + 86400000).toISOString(), status: 'upcoming', source: 'ai_call', notes: 'Referred for cardiology checkup', customer: { name: 'Ananya Sharma', phone: '+91 98401 23456' }, service: { name: 'Cardiology Consultation & ECG' } },
      { id: 'appt-2', customer_id: 'cust-2', service_id: 'srv-4', appointment_time: new Date(Date.now() + 172800000).toISOString(), status: 'upcoming', source: 'ai_call', notes: 'Fasting blood panel', customer: { name: 'Vikramaditya Raman', phone: '+91 98840 98765' }, service: { name: 'Full Body Blood Diagnostics' } },
      { id: 'appt-3', customer_id: 'cust-3', service_id: 'srv-3', appointment_time: new Date(Date.now() - 172800000).toISOString(), status: 'completed', source: 'manual', notes: '18-month vaccine complete', customer: { name: 'Meera Swaminathan', phone: '+91 94441 55678' }, service: { name: 'Pediatric Health Checkup' } },
      { id: 'appt-4', customer_id: 'cust-4', service_id: 'srv-1', appointment_time: new Date(Date.now() - 432000000).toISOString(), status: 'cancelled', source: 'ai_call', notes: 'Patient rescheduled due to travel', customer: { name: 'Karthik Natarajan', phone: '+91 97910 11223' }, service: { name: 'General Physician Consultation' } },
    ],
    reminders: [
      { id: 'rem-1', customer_id: 'cust-1', appointment_id: 'appt-1', reminder_type: 'sms', scheduled_time: new Date(Date.now() + 43200000).toISOString(), status: 'pending', message: 'Reminder: Your Cardiology Consultation is tomorrow at 10:30 AM at Vattara City Clinic.', customer: { name: 'Ananya Sharma', phone: '+91 98401 23456' } },
      { id: 'rem-2', customer_id: 'cust-2', appointment_id: 'appt-2', reminder_type: 'voice', scheduled_time: new Date(Date.now() + 86400000).toISOString(), status: 'pending', message: 'Automated Voice Reminder: Fasting blood profile scheduled for Friday morning.', customer: { name: 'Vikramaditya Raman', phone: '+91 98840 98765' } },
      { id: 'rem-3', customer_id: 'cust-3', appointment_id: 'appt-3', reminder_type: 'sms', scheduled_time: new Date(Date.now() - 172800000).toISOString(), status: 'sent', message: 'Reminder: Pediatric Checkup today at 11:00 AM.', customer: { name: 'Meera Swaminathan', phone: '+91 94441 55678' } },
    ],
  };

  localStorage.setItem(MOCK_STORAGE_KEY, JSON.stringify(initial));
  return initial;
}

function saveMockDb(db) {
  localStorage.setItem(MOCK_STORAGE_KEY, JSON.stringify(db));
}

// ------------------------------------------------------------------------------
// Safe API Invocation Wrapper (Tries live backend first, falls back gracefully)
// ------------------------------------------------------------------------------
async function safeApiCall(apiFn, mockFallbackFn) {
  try {
    const res = await apiFn();
    isUsingMockFallback.current = false;
    return res.data;
  } catch (err) {
    // If backend is unreachable or CORS blocked, use realistic mock fallback
    if (!err.response || err.code === 'ERR_NETWORK' || err.response.status >= 500) {
      console.info('Live backend unreachable or server error, falling back to local mock client state.');
      isUsingMockFallback.current = true;
      return mockFallbackFn();
    }
    throw err;
  }
}

// ------------------------------------------------------------------------------
// Exported API Services
// ------------------------------------------------------------------------------
export const authService = {
  login: async (credentials) => {
    return safeApiCall(
      () => api.post('/auth/login', credentials),
      () => {
        const db = getMockDb();
        const token = 'mock_jwt_token_' + Date.now();
        localStorage.setItem('vattara_token', token);
        return {
          access_token: token,
          token_type: 'bearer',
          user: db.user,
          business: db.business,
        };
      }
    );
  },

  register: async (payload) => {
    return safeApiCall(
      () => api.post('/auth/register', payload),
      () => {
        const db = getMockDb();
        db.business.name = payload.business_name;
        db.business.vertical = payload.vertical;
        db.business.phone = payload.business_phone;
        db.business.email = payload.business_email;
        db.user.email = payload.admin_email;
        db.user.full_name = payload.admin_name;
        saveMockDb(db);
        const token = 'mock_jwt_token_' + Date.now();
        localStorage.setItem('vattara_token', token);
        return {
          access_token: token,
          token_type: 'bearer',
          user: db.user,
          business: db.business,
        };
      }
    );
  },

  getProfile: async () => {
    return safeApiCall(
      () => api.get('/auth/me'),
      () => {
        const db = getMockDb();
        return { user: db.user, business: db.business };
      }
    );
  },

  updateProfile: async (data) => {
    return safeApiCall(
      () => api.put('/auth/profile', data),
      () => {
        const db = getMockDb();
        if (data.full_name) db.user.full_name = data.full_name;
        if (data.business_name) db.business.name = data.business_name;
        if (data.phone) db.business.phone = data.phone;
        if (data.address) db.business.address = data.address;
        saveMockDb(db);
        return { user: db.user, business: db.business };
      }
    );
  },

  forgotPassword: async (email) => {
    return safeApiCall(
      () => api.post('/auth/forgot-password', { email }),
      () => ({ status: 'success', message: `Password reset instructions sent to ${email}` })
    );
  },

  resetPassword: async (data) => {
    return safeApiCall(
      () => api.post('/auth/reset-password', data),
      () => ({ status: 'success', message: 'Password reset successfully' })
    );
  },
};

export const dashboardService = {
  getStats: async () => {
    return safeApiCall(
      () => api.get('/dashboard/stats'),
      () => {
        const db = getMockDb();
        const incoming = db.calls.filter((c) => c.call_type === 'incoming').length;
        const outgoing = db.calls.filter((c) => c.call_type === 'outgoing').length;
        const successful = db.calls.filter((c) => c.status === 'completed').length;
        const missed = db.calls.filter((c) => c.status === 'missed').length;
        return {
          total_incoming_calls: incoming,
          total_outgoing_calls: outgoing,
          total_appointments: db.appointments.length,
          total_customers: db.customers.length,
          successful_calls: successful,
          missed_calls: missed,
          active_assistant: db.assistant.is_active,
          upcoming_appointments_count: db.appointments.filter((a) => a.status === 'upcoming').length,
        };
      }
    );
  },

  getActivities: async () => {
    return safeApiCall(
      () => api.get('/dashboard/activities'),
      () => {
        const db = getMockDb();
        const activities = [];
        db.calls.slice(0, 4).forEach((c) => {
          activities.push({
            id: 'act-' + c.id,
            type: 'call',
            title: `${c.call_type === 'incoming' ? 'Incoming' : 'Outgoing'} call (${c.caller_phone})`,
            description: c.summary,
            status: c.status,
            timestamp: c.initiated_at,
          });
        });
        db.appointments.slice(0, 3).forEach((a) => {
          activities.push({
            id: 'act-' + a.id,
            type: 'appointment',
            title: `Appointment: ${a.customer?.name || 'Customer'}`,
            description: `${a.service?.name || 'Consultation'} (${a.source})`,
            status: a.status,
            timestamp: a.appointment_time,
          });
        });
        return activities.sort((x, y) => new Date(y.timestamp) - new Date(x.timestamp));
      }
    );
  },

  getAnalytics: async (days = 7) => {
    return safeApiCall(
      () => api.get(`/dashboard/analytics?days=${days}`),
      () => {
        const stats = {
          total_incoming_calls: 32,
          total_outgoing_calls: 14,
          total_appointments: 18,
          total_customers: 24,
          successful_calls: 42,
          missed_calls: 4,
          active_assistant: true,
          upcoming_appointments_count: 5,
        };
        const call_trends = [
          { date: 'Mon', incoming: 5, outgoing: 2, missed: 0 },
          { date: 'Tue', incoming: 8, outgoing: 3, missed: 1 },
          { date: 'Wed', incoming: 6, outgoing: 2, missed: 0 },
          { date: 'Thu', incoming: 10, outgoing: 4, missed: 1 },
          { date: 'Fri', incoming: 7, outgoing: 3, missed: 0 },
          { date: 'Sat', incoming: 4, outgoing: 1, missed: 2 },
          { date: 'Sun', incoming: 2, outgoing: 0, missed: 0 },
        ];
        const appointment_breakdown = [
          { status: 'Upcoming', count: 6 },
          { status: 'Completed', count: 10 },
          { status: 'Cancelled', count: 2 },
          { status: 'Rescheduled', count: 3 },
        ];
        const duration_distribution = [
          { range_label: '< 1 min', count: 6 },
          { range_label: '1 - 2 mins', count: 14 },
          { range_label: '2 - 3 mins', count: 11 },
          { range_label: '3 - 5 mins', count: 8 },
          { range_label: '> 5 mins', count: 3 },
        ];
        return { stats, call_trends, appointment_breakdown, duration_distribution };
      }
    );
  },
};

export const assistantService = {
  getConfig: async () => {
    return safeApiCall(
      () => api.get('/assistant'),
      () => getMockDb().assistant
    );
  },

  updateConfig: async (config) => {
    return safeApiCall(
      () => api.put('/assistant', config),
      () => {
        const db = getMockDb();
        db.assistant = { ...db.assistant, ...config };
        saveMockDb(db);
        return db.assistant;
      }
    );
  },

  toggleAssistant: async (isActive) => {
    return safeApiCall(
      () => api.post('/assistant/toggle', { is_active: isActive }),
      () => {
        const db = getMockDb();
        db.assistant.is_active = isActive;
        saveMockDb(db);
        return db.assistant;
      }
    );
  },

  getServices: async () => {
    return safeApiCall(
      () => api.get('/assistant/services'),
      () => getMockDb().services
    );
  },

  createService: async (data) => {
    return safeApiCall(
      () => api.post('/assistant/services', data),
      () => {
        const db = getMockDb();
        const srv = { id: 'srv-' + Date.now(), ...data };
        db.services.push(srv);
        saveMockDb(db);
        return srv;
      }
    );
  },

  deleteService: async (id) => {
    return safeApiCall(
      () => api.delete(`/assistant/services/${id}`),
      () => {
        const db = getMockDb();
        db.services = db.services.filter((s) => s.id !== id);
        saveMockDb(db);
        return { success: true };
      }
    );
  },

  getFaqs: async () => {
    return safeApiCall(
      () => api.get('/assistant/faqs'),
      () => getMockDb().faqs
    );
  },

  createFaq: async (data) => {
    return safeApiCall(
      () => api.post('/assistant/faqs', data),
      () => {
        const db = getMockDb();
        const faq = { id: 'faq-' + Date.now(), ...data };
        db.faqs.push(faq);
        saveMockDb(db);
        return faq;
      }
    );
  },

  deleteFaq: async (id) => {
    return safeApiCall(
      () => api.delete(`/assistant/faqs/${id}`),
      () => {
        const db = getMockDb();
        db.faqs = db.faqs.filter((f) => f.id !== id);
        saveMockDb(db);
        return { success: true };
      }
    );
  },
};

export const callsService = {
  getCalls: async (params = {}) => {
    return safeApiCall(
      () => api.get('/calls', { params }),
      () => {
        const db = getMockDb();
        let list = [...db.calls];
        if (params.call_type) list = list.filter((c) => c.call_type === params.call_type);
        if (params.status) list = list.filter((c) => c.status === params.status);
        if (params.search) {
          const s = params.search.toLowerCase();
          list = list.filter((c) => (c.caller_name || '').toLowerCase().includes(s) || c.caller_phone.includes(s));
        }
        return list;
      }
    );
  },

  getCall: async (id) => {
    return safeApiCall(
      () => api.get(`/calls/${id}`),
      () => getMockDb().calls.find((c) => c.id === id) || null
    );
  },

  simulateCall: async (payload) => {
    return safeApiCall(
      () => api.post('/calls/simulate', payload),
      () => {
        const db = getMockDb();
        const call = {
          id: 'call-' + Date.now(),
          caller_name: payload.caller_name,
          caller_phone: payload.caller_phone,
          call_type: payload.call_type,
          status: 'completed',
          duration_seconds: payload.duration_seconds || 120,
          summary: `Simulated ${payload.call_type} call regarding ${payload.scenario || 'General Inquiry'}.`,
          transcript: `AI: Hello, thank you for calling Vattara Clinic. How may I assist you today?\nCaller: Hi, I'm inquiring about ${payload.scenario || 'appointment'}.\nAI: I would be happy to schedule that for you!`,
          initiated_at: new Date().toISOString(),
        };
        db.calls.unshift(call);
        saveMockDb(db);
        return call;
      }
    );
  },
};

export const appointmentsService = {
  getAppointments: async (params = {}) => {
    return safeApiCall(
      () => api.get('/appointments', { params }),
      () => {
        const db = getMockDb();
        let list = [...db.appointments];
        if (params.status) list = list.filter((a) => a.status === params.status);
        return list;
      }
    );
  },

  createAppointment: async (data) => {
    return safeApiCall(
      () => api.post('/appointments', data),
      () => {
        const db = getMockDb();
        const appt = {
          id: 'appt-' + Date.now(),
          ...data,
          status: 'upcoming',
          customer: { name: data.customer_name || 'Walk-in Client', phone: data.customer_phone || '+91 99999 88888' },
          service: { name: 'Consultation & Examination' },
        };
        db.appointments.unshift(appt);
        saveMockDb(db);
        return appt;
      }
    );
  },

  updateAppointment: async (id, data) => {
    return safeApiCall(
      () => api.put(`/appointments/${id}`, data),
      () => {
        const db = getMockDb();
        const idx = db.appointments.findIndex((a) => a.id === id);
        if (idx !== -1) {
          db.appointments[idx] = { ...db.appointments[idx], ...data };
          saveMockDb(db);
          return db.appointments[idx];
        }
        return null;
      }
    );
  },

  cancelAppointment: async (id, reason) => {
    return safeApiCall(
      () => api.post(`/appointments/${id}/cancel?reason=${encodeURIComponent(reason || '')}`),
      () => {
        const db = getMockDb();
        const appt = db.appointments.find((a) => a.id === id);
        if (appt) {
          appt.status = 'cancelled';
          if (reason) appt.notes = `${appt.notes || ''} [Cancelled: ${reason}]`;
          saveMockDb(db);
        }
        return appt;
      }
    );
  },
};

export const customersService = {
  getCustomers: async (params = {}) => {
    return safeApiCall(
      () => api.get('/customers', { params }),
      () => {
        const db = getMockDb();
        let list = [...db.customers];
        if (params.search) {
          const s = params.search.toLowerCase();
          list = list.filter((c) => c.name.toLowerCase().includes(s) || c.phone.includes(s));
        }
        return list;
      }
    );
  },

  getCustomer: async (id) => {
    return safeApiCall(
      () => api.get(`/customers/${id}`),
      () => {
        const db = getMockDb();
        const cust = db.customers.find((c) => c.id === id);
        if (!cust) return null;
        const calls = db.calls.filter((c) => c.caller_phone === cust.phone);
        const appointments = db.appointments.filter((a) => a.customer_id === cust.id);
        return { ...cust, calls, appointments };
      }
    );
  },

  createCustomer: async (data) => {
    return safeApiCall(
      () => api.post('/customers', data),
      () => {
        const db = getMockDb();
        const cust = { id: 'cust-' + Date.now(), total_calls: 0, total_appointments: 0, ...data };
        db.customers.push(cust);
        saveMockDb(db);
        return cust;
      }
    );
  },

  deleteCustomer: async (id) => {
    return safeApiCall(
      () => api.delete(`/customers/${id}`),
      () => {
        const db = getMockDb();
        db.customers = db.customers.filter((c) => c.id !== id);
        saveMockDb(db);
        return { success: true };
      }
    );
  },
};

export const remindersService = {
  getReminders: async (params = {}) => {
    return safeApiCall(
      () => api.get('/reminders', { params }),
      () => {
        const db = getMockDb();
        let list = [...db.reminders];
        if (params.status) list = list.filter((r) => r.status === params.status);
        if (params.reminder_type) list = list.filter((r) => r.reminder_type === params.reminder_type);
        return list;
      }
    );
  },

  createReminder: async (data) => {
    return safeApiCall(
      () => api.post('/reminders', data),
      () => {
        const db = getMockDb();
        const cust = db.customers.find((c) => c.id === data.customer_id) || { name: 'Client', phone: '+91 99999 00000' };
        const rem = {
          id: 'rem-' + Date.now(),
          ...data,
          status: 'pending',
          customer: cust,
        };
        db.reminders.push(rem);
        saveMockDb(db);
        return rem;
      }
    );
  },

  sendReminder: async (id) => {
    return safeApiCall(
      () => api.post(`/reminders/${id}/send`),
      () => {
        const db = getMockDb();
        const rem = db.reminders.find((r) => r.id === id);
        if (rem) {
          rem.status = 'sent';
          rem.sent_at = new Date().toISOString();
          saveMockDb(db);
        }
        return rem;
      }
    );
  },

  deleteReminder: async (id) => {
    return safeApiCall(
      () => api.delete(`/reminders/${id}`),
      () => {
        const db = getMockDb();
        db.reminders = db.reminders.filter((r) => r.id !== id);
        saveMockDb(db);
        return { success: true };
      }
    );
  },
};

export const reportsService = {
  getSummary: async (rangeType = '7d') => {
    return safeApiCall(
      () => api.get(`/reports/summary?range_type=${rangeType}`),
      () => ({
        range_type: rangeType,
        metrics: {
          total_calls: 48,
          incoming_calls: 34,
          outgoing_calls: 14,
          successful_calls: 43,
          missed_calls: 5,
          call_success_rate: 89.6,
          avg_call_duration_seconds: 142,
          total_appointments: 22,
          completed_appointments: 15,
          cancelled_appointments: 3,
          upcoming_appointments: 4,
          appointment_fulfillment_rate: 83.3,
        },
        timeline: [
          { date: 'Day 1', incoming: 6, outgoing: 2, missed: 1 },
          { date: 'Day 2', incoming: 8, outgoing: 3, missed: 0 },
          { date: 'Day 3', incoming: 7, outgoing: 2, missed: 1 },
          { date: 'Day 4', incoming: 9, outgoing: 4, missed: 0 },
          { date: 'Day 5', incoming: 11, outgoing: 3, missed: 2 },
          { date: 'Day 6', incoming: 5, outgoing: 1, missed: 1 },
          { date: 'Day 7', incoming: 2, outgoing: 0, missed: 0 },
        ],
        call_reasons: [
          { reason: 'Appointment Booking', percentage: 48 },
          { reason: 'Service Pricing & Timings', percentage: 26 },
          { reason: 'Reschedule / Cancellation', percentage: 14 },
          { reason: 'General Inquiry', percentage: 12 },
        ],
      })
    );
  },
};

export default api;

