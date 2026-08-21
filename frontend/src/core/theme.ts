import { useEffect, useState } from "react";

export type AppTheme = "light" | "dark";
export const THEME_STORAGE_KEY = "dermai-theme";

function systemTheme(): AppTheme {
  return typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

export function currentTheme(): AppTheme {
  if (typeof document === "undefined") return "light";
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

export function applyTheme(theme: AppTheme) {
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
  window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  window.dispatchEvent(new CustomEvent("dermai-theme-changed", { detail: theme }));
}

export function useAppTheme() {
  const [theme, setTheme] = useState<AppTheme>(() => currentTheme());

  useEffect(() => {
    if (!document.documentElement.dataset.theme) {
      const stored = window.localStorage.getItem(THEME_STORAGE_KEY) as AppTheme | null;
      applyTheme(stored === "dark" || stored === "light" ? stored : systemTheme());
    }
    const sync = (event: Event) => setTheme((event as CustomEvent<AppTheme>).detail || currentTheme());
    window.addEventListener("dermai-theme-changed", sync);
    return () => window.removeEventListener("dermai-theme-changed", sync);
  }, []);

  return {
    theme,
    toggleTheme: () => applyTheme(theme === "dark" ? "light" : "dark"),
  };
}
