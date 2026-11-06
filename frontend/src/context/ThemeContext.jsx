import React, { createContext, useContext, useState, useEffect } from 'react';

// Helper to convert hex to space-separated RGB string ("R G B")
export function hexToRgb(hex) {
  if (!hex) return '228 119 69';
  let c = hex.replace('#', '');
  if (c.length === 3) c = c.split('').map((x) => x + x).join('');
  const num = parseInt(c, 16);
  return `${(num >> 16) & 255} ${(num >> 8) & 255} ${num & 255}`;
}

export const PREDEFINED_THEMES = [
  {
    id: 'signature',
    name: 'Signature Vattara',
    description: 'Original burnt orange & warm charcoal AI aesthetic',
    preview: ['#E47745', '#F0AD57', '#171816', '#10110F'],
    dark: {
      warmblack: '#10110F',
      charcoal: '#171816',
      graphite: '#242622',
      burnt: '#E47745',
      amber: '#F0AD57',
      lavender: '#A78BFA',
      ivory: '#F2EEE6',
      mutedgrey: '#AAA99F',
    },
    light: {
      warmblack: '#FBF9F5',
      charcoal: '#FFFFFF',
      graphite: '#EFECE6',
      burnt: '#D05C28',
      amber: '#D98A2B',
      lavender: '#7C3AED',
      ivory: '#191A18',
      mutedgrey: '#66655E',
    },
  },
  {
    id: 'obsidian-violet',
    name: 'Obsidian Violet',
    description: 'Deep royal amethyst & glowing lavender neural tones',
    preview: ['#8B5CF6', '#C084FC', '#151322', '#0B0A10'],
    dark: {
      warmblack: '#0B0A10',
      charcoal: '#151322',
      graphite: '#232035',
      burnt: '#8B5CF6',
      amber: '#C084FC',
      lavender: '#A78BFA',
      ivory: '#F5F3FF',
      mutedgrey: '#A39EBD',
    },
    light: {
      warmblack: '#F5F3FF',
      charcoal: '#FFFFFF',
      graphite: '#E9E5F5',
      burnt: '#7C3AED',
      amber: '#9333EA',
      lavender: '#8B5CF6',
      ivory: '#1E1B4B',
      mutedgrey: '#6B7280',
    },
  },
  {
    id: 'emerald-midnight',
    name: 'Emerald Midnight',
    description: 'Luminous clinical emerald with deep jade shadow surfaces',
    preview: ['#10B981', '#34D399', '#0C2018', '#06130E'],
    dark: {
      warmblack: '#06130E',
      charcoal: '#0C2018',
      graphite: '#183328',
      burnt: '#10B981',
      amber: '#34D399',
      lavender: '#6EE7B7',
      ivory: '#ECFDF5',
      mutedgrey: '#89A69A',
    },
    light: {
      warmblack: '#F0FDF4',
      charcoal: '#FFFFFF',
      graphite: '#DCFCE7',
      burnt: '#059669',
      amber: '#10B981',
      lavender: '#34D399',
      ivory: '#064E3B',
      mutedgrey: '#64748B',
    },
  },
  {
    id: 'burgundy-champagne',
    name: 'Burgundy Champagne',
    description: 'Opulent velvet wine with warm champagne gold accents',
    preview: ['#E07A5F', '#F4A261', '#221218', '#12090C'],
    dark: {
      warmblack: '#12090C',
      charcoal: '#221218',
      graphite: '#361F27',
      burnt: '#E07A5F',
      amber: '#F4A261',
      lavender: '#DDA15E',
      ivory: '#FFF8F0',
      mutedgrey: '#B89E9F',
    },
    light: {
      warmblack: '#FFF7F2',
      charcoal: '#FFFFFF',
      graphite: '#FDE8E0',
      burnt: '#BE185D',
      amber: '#D97706',
      lavender: '#F43F5E',
      ivory: '#4C0519',
      mutedgrey: '#78716C',
    },
  },
  {
    id: 'cyberpunk-neon',
    name: 'Cyberpunk Neon',
    description: 'High-voltage electric cyan & synthwave magenta',
    preview: ['#06B6D4', '#EC4899', '#0C1222', '#050811'],
    dark: {
      warmblack: '#050811',
      charcoal: '#0C1222',
      graphite: '#16213A',
      burnt: '#06B6D4',
      amber: '#EC4899',
      lavender: '#8B5CF6',
      ivory: '#F0FDF4',
      mutedgrey: '#7DD3FC',
    },
    light: {
      warmblack: '#ECFEFF',
      charcoal: '#FFFFFF',
      graphite: '#CFFAFE',
      burnt: '#0891B2',
      amber: '#DB2777',
      lavender: '#7C3AED',
      ivory: '#083344',
      mutedgrey: '#64748B',
    },
  },
  {
    id: 'mocha-copper',
    name: 'Mocha Copper',
    description: 'Roasted espresso grounds with burnished copper sheen',
    preview: ['#D97736', '#E6A15C', '#1F1813', '#120E0B'],
    dark: {
      warmblack: '#120E0B',
      charcoal: '#1F1813',
      graphite: '#30261F',
      burnt: '#D97736',
      amber: '#E6A15C',
      lavender: '#C88A58',
      ivory: '#FDF8F5',
      mutedgrey: '#B5A599',
    },
    light: {
      warmblack: '#FAF5F0',
      charcoal: '#FFFFFF',
      graphite: '#EDE0D4',
      burnt: '#B45309',
      amber: '#D97706',
      lavender: '#92400E',
      ivory: '#451A03',
      mutedgrey: '#78716C',
    },
  },
  {
    id: 'forest-lime',
    name: 'Forest Lime',
    description: 'Deep canopy pine with zesty electric citrus lime',
    preview: ['#84CC16', '#A3E635', '#142010', '#0A1108'],
    dark: {
      warmblack: '#0A1108',
      charcoal: '#142010',
      graphite: '#21331B',
      burnt: '#84CC16',
      amber: '#A3E635',
      lavender: '#4ADE80',
      ivory: '#F7FEE7',
      mutedgrey: '#9DB392',
    },
    light: {
      warmblack: '#F7FEE7',
      charcoal: '#FFFFFF',
      graphite: '#ECFCCB',
      burnt: '#65A30D',
      amber: '#84CC16',
      lavender: '#16A34A',
      ivory: '#1A2E05',
      mutedgrey: '#64748B',
    },
  },
  {
    id: 'midnight-plum-rose',
    name: 'Midnight Plum Rose',
    description: 'Nocturnal purple velvet kissed with vivid hot rose',
    preview: ['#F43F5E', '#FB7185', '#1E1022', '#110813'],
    dark: {
      warmblack: '#110813',
      charcoal: '#1E1022',
      graphite: '#301A37',
      burnt: '#F43F5E',
      amber: '#FB7185',
      lavender: '#C084FC',
      ivory: '#FFF1F2',
      mutedgrey: '#BA9EBE',
    },
    light: {
      warmblack: '#FFF1F2',
      charcoal: '#FFFFFF',
      graphite: '#FFE4E6',
      burnt: '#E11D48',
      amber: '#F43F5E',
      lavender: '#9333EA',
      ivory: '#4C0519',
      mutedgrey: '#78716C',
    },
  },
  {
    id: 'sand-terracotta',
    name: 'Sand Terracotta',
    description: 'Earthy desert dunes and fired terracotta warmth',
    preview: ['#E76F51', '#F4A261', '#221C17', '#14110E'],
    dark: {
      warmblack: '#14110E',
      charcoal: '#221C17',
      graphite: '#352C25',
      burnt: '#E76F51',
      amber: '#F4A261',
      lavender: '#E9C46A',
      ivory: '#FAF0CA',
      mutedgrey: '#B8AFA6',
    },
    light: {
      warmblack: '#FDFBF7',
      charcoal: '#FFFFFF',
      graphite: '#F4EDE4',
      burnt: '#C55337',
      amber: '#E76F51',
      lavender: '#D4A373',
      ivory: '#2B1D14',
      mutedgrey: '#78716C',
    },
  },
  {
    id: 'arctic-graphite-mint',
    name: 'Arctic Graphite Mint',
    description: 'Glacial frost cyan over aerospace graphite matrix',
    preview: ['#14B8A6', '#2DD4BF', '#101B24', '#080E14'],
    dark: {
      warmblack: '#080E14',
      charcoal: '#101B24',
      graphite: '#1A2C3A',
      burnt: '#14B8A6',
      amber: '#2DD4BF',
      lavender: '#38BDF8',
      ivory: '#F0FDFA',
      mutedgrey: '#8EAAB8',
    },
    light: {
      warmblack: '#F0FDFA',
      charcoal: '#FFFFFF',
      graphite: '#CCFBF1',
      burnt: '#0D9488',
      amber: '#14B8A6',
      lavender: '#0284C7',
      ivory: '#134E4A',
      mutedgrey: '#64748B',
    },
  },
  {
    id: 'indigo-solar-yellow',
    name: 'Indigo Solar Yellow',
    description: 'Deep cosmic indigo sky with brilliant solar gold rays',
    preview: ['#EAB308', '#FACC15', '#12182E', '#0A0D1A'],
    dark: {
      warmblack: '#0A0D1A',
      charcoal: '#12182E',
      graphite: '#1D2647',
      burnt: '#EAB308',
      amber: '#FACC15',
      lavender: '#6366F1',
      ivory: '#FEFCE8',
      mutedgrey: '#939AB9',
    },
    light: {
      warmblack: '#FEFCE8',
      charcoal: '#FFFFFF',
      graphite: '#FEF08A',
      burnt: '#CA8A04',
      amber: '#EAB308',
      lavender: '#4F46E5',
      ivory: '#1E1B4B',
      mutedgrey: '#64748B',
    },
  },
  {
    id: 'slate-coral',
    name: 'Slate Coral',
    description: 'Dark slate oceanic floor illuminated with living coral reef',
    preview: ['#FF6B6B', '#FFA07A', '#181E26', '#0E1116'],
    dark: {
      warmblack: '#0E1116',
      charcoal: '#181E26',
      graphite: '#262F3C',
      burnt: '#FF6B6B',
      amber: '#FFA07A',
      lavender: '#4ECDC4',
      ivory: '#F8FAFC',
      mutedgrey: '#94A3B8',
    },
    light: {
      warmblack: '#F8FAFC',
      charcoal: '#FFFFFF',
      graphite: '#E2E8F0',
      burnt: '#E11D48',
      amber: '#F43F5E',
      lavender: '#0D9488',
      ivory: '#0F172A',
      mutedgrey: '#64748B',
    },
  },
  {
    id: 'holographic-rainbow',
    name: 'Holographic Rainbow',
    description: 'Prismatic multi-spectrum neon against dark nebula glass',
    preview: ['#D946EF', '#06B6D4', '#141224', '#0A0912'],
    dark: {
      warmblack: '#0A0912',
      charcoal: '#141224',
      graphite: '#221F3B',
      burnt: '#D946EF',
      amber: '#06B6D4',
      lavender: '#8B5CF6',
      ivory: '#FAF5FF',
      mutedgrey: '#A8A2BF',
    },
    light: {
      warmblack: '#FAF5FF',
      charcoal: '#FFFFFF',
      graphite: '#F3E8FF',
      burnt: '#C026D3',
      amber: '#0891B2',
      lavender: '#7C3AED',
      ivory: '#2E1065',
      mutedgrey: '#64748B',
    },
  },
];

const ThemeContext = createContext();

export function ThemeProvider({ children }) {
  const [themeId, setThemeIdState] = useState(() => {
    try {
      const saved = localStorage.getItem('vattara_theme_id');
      return saved || 'signature';
    } catch {
      return 'signature';
    }
  });

  const [mode, setModeState] = useState(() => {
    try {
      const saved = localStorage.getItem('vattara_theme_mode');
      return saved || 'dark';
    } catch {
      return 'dark';
    }
  });

  const [customAccent, setCustomAccentState] = useState(() => {
    try {
      const saved = localStorage.getItem('vattara_custom_accent');
      return saved || null;
    } catch {
      return null;
    }
  });

  const currentTheme =
    PREDEFINED_THEMES.find((t) => t.id === themeId) || PREDEFINED_THEMES[0];

  const palette = mode === 'light' ? currentTheme.light : currentTheme.dark;

  // Compute active colors with custom accent override if set
  const activeColors = {
    ...palette,
    burnt: customAccent || palette.burnt,
  };

  // Apply CSS variables to root
  useEffect(() => {
    const root = document.documentElement;

    root.setAttribute('data-theme', themeId);
    root.setAttribute('data-mode', mode);

    if (mode === 'light') {
      root.classList.remove('dark');
      root.classList.add('light');
    } else {
      root.classList.remove('light');
      root.classList.add('dark');
    }

    // Set RGB variables for Tailwind opacity utility classes
    root.style.setProperty('--color-warmblack-rgb', hexToRgb(activeColors.warmblack));
    root.style.setProperty('--color-charcoal-rgb', hexToRgb(activeColors.charcoal));
    root.style.setProperty('--color-graphite-rgb', hexToRgb(activeColors.graphite));
    root.style.setProperty('--color-burnt-rgb', hexToRgb(activeColors.burnt));
    root.style.setProperty('--color-amber-rgb', hexToRgb(activeColors.amber));
    root.style.setProperty('--color-lavender-rgb', hexToRgb(activeColors.lavender));
    root.style.setProperty('--color-ivory-rgb', hexToRgb(activeColors.ivory));
    root.style.setProperty('--color-mutedgrey-rgb', hexToRgb(activeColors.mutedgrey));

    // Hex values for SVG/direct inline styling
    root.style.setProperty('--color-warmblack', activeColors.warmblack);
    root.style.setProperty('--color-charcoal', activeColors.charcoal);
    root.style.setProperty('--color-graphite', activeColors.graphite);
    root.style.setProperty('--color-burnt', activeColors.burnt);
    root.style.setProperty('--color-amber', activeColors.amber);
    root.style.setProperty('--color-lavender', activeColors.lavender);
    root.style.setProperty('--color-ivory', activeColors.ivory);
    root.style.setProperty('--color-mutedgrey', activeColors.mutedgrey);
  }, [themeId, mode, customAccent]);

  const setThemeId = (id) => {
    setThemeIdState(id);
    try {
      localStorage.setItem('vattara_theme_id', id);
    } catch (e) {
      console.warn(e);
    }
  };

  const setMode = (m) => {
    setModeState(m);
    try {
      localStorage.setItem('vattara_theme_mode', m);
    } catch (e) {
      console.warn(e);
    }
  };

  const setCustomAccent = (hex) => {
    setCustomAccentState(hex);
    try {
      if (hex) {
        localStorage.setItem('vattara_custom_accent', hex);
      } else {
        localStorage.removeItem('vattara_custom_accent');
      }
    } catch (e) {
      console.warn(e);
    }
  };

  const resetToDefault = () => {
    setThemeIdState('signature');
    setModeState('dark');
    setCustomAccentState(null);
    try {
      localStorage.removeItem('vattara_theme_id');
      localStorage.removeItem('vattara_theme_mode');
      localStorage.removeItem('vattara_custom_accent');
    } catch (e) {
      console.warn(e);
    }
  };

  return (
    <ThemeContext.Provider
      value={{
        themes: PREDEFINED_THEMES,
        themeId,
        setThemeId,
        mode,
        setMode,
        customAccent,
        setCustomAccent,
        resetToDefault,
        currentTheme,
        colors: activeColors,
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
}

