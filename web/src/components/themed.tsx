// Themed visual components shared across pages. Co-located here (not in
// `lib/theme.ts`) because Fast Refresh requires component files to *only*
// export components — utilities live in `lib/theme.ts`.
import { useSyncExternalStore } from "react";

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
 * Relative-time sync stamp with a pulsing green dot. Re-renders every
 * 30s via useSyncExternalStore — the canonical React way to bind a
 * component to a wall-clock tick without violating render purity.
 * ------------------------------------------------------------------ */
function subscribeClock(callback: () => void): () => void {
  const id = setInterval(callback, 30000);
  return () => clearInterval(id);
}
function nowSnapshot(): number {
  return Date.now();
}
function formatSyncLabel(at: string, now: number): string {
  const ts = new Date(at).getTime();
  const mins = Math.floor((now - ts) / 60000);
  if (mins < 1) return "Synced just now";
  if (mins < 60) return `Synced ${mins}m ago`;
  if (mins < 1440) return `Synced ${Math.floor(mins / 60)}h ago`;
  return `Synced ${new Date(at).toLocaleDateString()}`;
}

export function SyncStamp({ at, className }: { at: string; className?: string }) {
  const now = useSyncExternalStore(subscribeClock, nowSnapshot, nowSnapshot);
  const label = formatSyncLabel(at, now);
  return (
    <span className={`inline-flex items-center gap-1.5 ${className ?? ""}`} title={new Date(at).toLocaleString()}>
      <span className="relative flex h-1.5 w-1.5">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
        <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-green-400" />
      </span>
      {label}
    </span>
  );
}
