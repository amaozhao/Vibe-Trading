import { DEFAULT_LANGUAGE, LANGUAGE_STORAGE_KEY, isSupportedLanguage, usePreferencesStore } from "../preferences";

beforeEach(() => {
  localStorage.clear();
  usePreferencesStore.setState({ language: DEFAULT_LANGUAGE });
  document.documentElement.lang = "";
});

describe("preferences store", () => {
  it("defaults to English", () => {
    expect(usePreferencesStore.getState().language).toBe("en");
  });

  it("persists the selected language and updates document lang", () => {
    usePreferencesStore.getState().setLanguage("zh-CN");

    expect(usePreferencesStore.getState().language).toBe("zh-CN");
    expect(localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe("zh-CN");
    expect(document.documentElement.lang).toBe("zh-CN");
  });

  it("rejects unsupported language values", () => {
    expect(isSupportedLanguage("en")).toBe(true);
    expect(isSupportedLanguage("zh-CN")).toBe(true);
    expect(isSupportedLanguage("fr")).toBe(false);
  });
});
