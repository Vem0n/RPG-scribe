import { useMemo } from "react";

/* ------------------------------------------------------------------
 * Per-game accent colors. Values map to CSS custom properties that
 * override --primary / --ring / --primary-foreground / --dial-*
 * within any wrapper that spreads `getThemeStyle(slug)`.
 *
 * Must be applied to a descendant of the .dark wrapper in App.tsx —
 * otherwise .dark's redeclarations shadow whatever is set higher up.
 * ------------------------------------------------------------------ */
export type Theme = {
  primary: string;
  primaryFg: string;
  ring: string;
  dialFrom: string;
  dialTo: string;
};

export const THEMES: Record<string, Theme> = {
  cyberpunk2077: {
    primary: "oklch(0.7 0.15 270)",
    primaryFg: "oklch(0.98 0 0)",
    ring: "oklch(0.7 0.15 270)",
    dialFrom: "oklch(0.75 0.18 270)",
    dialTo: "oklch(0.65 0.18 330)",
  },
  kotor: {
    primary: "oklch(0.7 0.14 225)",
    primaryFg: "oklch(0.98 0 0)",
    ring: "oklch(0.7 0.14 225)",
    dialFrom: "oklch(0.78 0.15 225)",
    dialTo: "oklch(0.72 0.16 195)",
  },
  fallout_new_vegas: {
    primary: "oklch(0.74 0.16 70)",
    primaryFg: "oklch(0.18 0.02 70)",
    ring: "oklch(0.74 0.16 70)",
    dialFrom: "oklch(0.82 0.17 80)",
    dialTo: "oklch(0.65 0.2 45)",
  },
  dragon_age_origins: {
    primary: "oklch(0.62 0.19 25)",
    primaryFg: "oklch(0.98 0 0)",
    ring: "oklch(0.62 0.19 25)",
    dialFrom: "oklch(0.7 0.2 25)",
    dialTo: "oklch(0.55 0.2 10)",
  },
};

export const DEFAULT_THEME = THEMES.cyberpunk2077;

export function getTheme(slug?: string): Theme {
  return (slug && THEMES[slug]) || DEFAULT_THEME;
}

export function getThemeStyle(slug?: string): React.CSSProperties {
  const t = getTheme(slug);
  return {
    "--primary": t.primary,
    "--primary-foreground": t.primaryFg,
    "--ring": t.ring,
    "--dial-from": t.dialFrom,
    "--dial-to": t.dialTo,
  } as React.CSSProperties;
}

/* Memoised theme-style hook for React consumers. */
export function useThemeStyle(slug?: string): React.CSSProperties {
  return useMemo(() => getThemeStyle(slug), [slug]);
}
