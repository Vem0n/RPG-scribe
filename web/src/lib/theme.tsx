import { useEffect, useMemo, useState } from "react";

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

/* ------------------------------------------------------------------
 * Circular progress dial that reads --dial-from / --dial-to for its
 * gradient, so it picks up whichever theme wraps it.
 * ------------------------------------------------------------------ */
export function ProgressDial({ pct, size = 64, gradId = "dialGrad" }: { pct: number; size?: number; gradId?: string }) {
  const stroke = 3;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const offset = c - (pct / 100) * c;
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth={stroke} />
        <circle
          cx={size / 2} cy={size / 2} r={r} fill="none"
          stroke={`url(#${gradId})`} strokeWidth={stroke}
          strokeDasharray={c} strokeDashoffset={offset} strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 600ms ease-out" }}
        />
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="var(--dial-from, oklch(0.75 0.18 270))" />
            <stop offset="100%" stopColor="var(--dial-to, oklch(0.65 0.18 330))" />
          </linearGradient>
        </defs>
      </svg>
      <div className="absolute inset-0 grid place-items-center text-xs font-semibold tabular-nums" style={{ fontFamily: "'Orbitron', sans-serif" }}>
        {Math.round(pct)}%
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------
 * Relative-time sync stamp with a pulsing green dot. Ticks every 30s.
 * ------------------------------------------------------------------ */
export function SyncStamp({ at, className }: { at: string; className?: string }) {
  const [, bump] = useState(0);
  useEffect(() => {
    const i = setInterval(() => bump(x => x + 1), 30000);
    return () => clearInterval(i);
  }, []);
  const d = new Date(at);
  const mins = Math.floor((Date.now() - d.getTime()) / 60000);
  let label: string;
  if (mins < 1) label = "Synced just now";
  else if (mins < 60) label = `Synced ${mins}m ago`;
  else if (mins < 1440) label = `Synced ${Math.floor(mins / 60)}h ago`;
  else label = `Synced ${d.toLocaleDateString()}`;
  return (
    <span className={`inline-flex items-center gap-1.5 ${className ?? ""}`} title={d.toLocaleString()}>
      <span className="relative flex h-1.5 w-1.5">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
        <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-green-400" />
      </span>
      {label}
    </span>
  );
}

/* ------------------------------------------------------------------
 * Memoised theme-style hook for React consumers.
 * ------------------------------------------------------------------ */
export function useThemeStyle(slug?: string): React.CSSProperties {
  return useMemo(() => getThemeStyle(slug), [slug]);
}
