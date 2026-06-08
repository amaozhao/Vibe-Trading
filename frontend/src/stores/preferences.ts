import { create } from "zustand";

export const LANGUAGE_STORAGE_KEY = "vibe-language";
export const DEFAULT_LANGUAGE = "en";

export type Language = "en" | "zh-CN";

interface PreferencesState {
  language: Language;
  setLanguage: (language: Language) => void;
}

export function isSupportedLanguage(value: string | null | undefined): value is Language {
  return value === "en" || value === "zh-CN";
}

function readInitialLanguage(): Language {
  if (typeof localStorage === "undefined") return DEFAULT_LANGUAGE;
  const stored = localStorage.getItem(LANGUAGE_STORAGE_KEY);
  return isSupportedLanguage(stored) ? stored : DEFAULT_LANGUAGE;
}

function applyDocumentLanguage(language: Language): void {
  if (typeof document !== "undefined") {
    document.documentElement.lang = language;
  }
}

const initialLanguage = readInitialLanguage();
applyDocumentLanguage(initialLanguage);

export const usePreferencesStore = create<PreferencesState>((set) => ({
  language: initialLanguage,
  setLanguage: (language) => {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
    applyDocumentLanguage(language);
    set({ language });
  },
}));
