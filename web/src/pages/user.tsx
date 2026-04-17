import { useEffect, useState, useCallback } from "react";
import { Link, useParams } from "react-router-dom";
import { getUserPlaythroughs } from "@/lib/api";
import type { PlaythroughWithGame } from "@/lib/types";
import { useSyncRefresh } from "@/lib/useQuestEvents";
import { ProgressDial, SyncStamp, getThemeStyle } from "@/lib/theme";

export default function UserPage() {
  const { username } = useParams<{ username: string }>();
  const [playthroughs, setPlaythroughs] = useState<PlaythroughWithGame[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(() => {
    if (!username) return;
    getUserPlaythroughs(username)
      .then(setPlaythroughs)
      .finally(() => setLoading(false));
  }, [username]);

  useEffect(() => { fetchData(); }, [fetchData]);
  useSyncRefresh(fetchData, { username: username || undefined });

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-muted-foreground">Loading...</div>
    );
  }

  if (playthroughs.length === 0) {
    return (
      <div>
        <Breadcrumb username={username!} />
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <div className="text-5xl">🎮</div>
          <h1 className="text-2xl font-semibold">No playthroughs yet</h1>
          <p className="text-muted-foreground text-center max-w-md">
            Sync a save file from the scraper to see playthroughs here.
          </p>
        </div>
      </div>
    );
  }

  const byGame = new Map<string, PlaythroughWithGame[]>();
  for (const pt of playthroughs) {
    const key = pt.game.slug;
    if (!byGame.has(key)) byGame.set(key, []);
    byGame.get(key)!.push(pt);
  }

  return (
    <div>
      <Breadcrumb username={username!} />
      <h1 className="text-2xl font-semibold mb-6">{username}'s Games</h1>
      <div className="space-y-10">
        {Array.from(byGame.entries()).map(([slug, gamePts]) => {
          // Theme scoped to each game section so accent colours match per-card.
          // Descendant of .dark (App.tsx) — inline style wins the cascade.
          const themeStyle = getThemeStyle(slug);
          return (
            <section key={slug} style={themeStyle}>
              <div className="flex items-baseline gap-3 mb-4">
                <h2 className="text-xl font-medium">{gamePts[0].game.name}</h2>
                <span className="text-sm text-muted-foreground">{gamePts.length}</span>
                <div className="flex-1 h-px bg-border/40" />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {gamePts.map((pt) => (
                  <PlaythroughCard key={pt.id} username={username!} pt={pt} />
                ))}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}

function PlaythroughCard({ username, pt }: { username: string; pt: PlaythroughWithGame }) {
  const total = pt.quest_summary.total;
  const finished = pt.quest_summary.finished;
  const started = pt.quest_summary.started;
  const failed = pt.quest_summary.failed;
  const pct = total > 0 ? (finished / total) * 100 : 0;

  // Segmented progress bar: finished (primary) + started (primary/40) fill.
  const finishedPct = total > 0 ? (finished / total) * 100 : 0;
  const startedPct = total > 0 ? (started / total) * 100 : 0;

  return (
    <Link to={`/${username}/${pt.id}`}>
      <div className="group relative overflow-hidden rounded-xl ring-1 ring-foreground/10 transition-all cursor-pointer">
        {/* Background art */}
        <div
          className="absolute inset-0 bg-cover bg-center transition-transform duration-500 group-hover:scale-105"
          style={{ backgroundImage: `url(/backgrounds/${pt.game.slug}.jpg)` }}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/95 via-black/70 to-black/40" />

        {/* Traced ring — draws itself around the card perimeter on hover.
            pathLength=1 normalises across any card size; non-scaling-stroke
            keeps stroke width consistent regardless of viewBox aspect ratio. */}
        <svg
          className="absolute inset-0 w-full h-full pointer-events-none overflow-visible"
          aria-hidden
        >
          <rect
            x="0" y="0"
            width="100%" height="100%"
            rx="12" ry="12"
            fill="none"
            stroke="var(--primary)"
            strokeWidth="2"
            pathLength="1"
            strokeDasharray="1"
            strokeDashoffset="1"
            vectorEffect="non-scaling-stroke"
            className="transition-[stroke-dashoffset] duration-[800ms] ease-out group-hover:[stroke-dashoffset:0]"
          />
        </svg>

        <div className="relative p-5 min-h-[180px] flex flex-col justify-end gap-4">
          <div className="flex items-start gap-4">
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-lg text-white truncate" style={{ fontFamily: "'Orbitron', sans-serif" }}>
                {pt.name}
              </div>
              <div className="text-xs text-white/60 mt-1 flex items-center gap-2 flex-wrap">
                {pt.last_synced_at ? (
                  <SyncStamp at={pt.last_synced_at} />
                ) : (
                  <span>Never synced</span>
                )}
                <span className="text-white/20">·</span>
                <span>{finished} / {total} quests</span>
              </div>
            </div>
            <ProgressDial pct={pct} size={52} gradId={`dial-${pt.id}`} />
          </div>

          {/* Segmented progress bar */}
          <div className="flex h-1.5 rounded-full overflow-hidden bg-white/10">
            <div className="bg-primary transition-all" style={{ width: `${finishedPct}%` }} />
            <div className="bg-primary/40 transition-all" style={{ width: `${startedPct}%` }} />
          </div>

          {/* Stat pills */}
          <div className="flex gap-3 text-xs text-white/80 flex-wrap">
            <Stat dotClass="bg-green-400" label="finished" value={finished} />
            {started > 0 && <Stat dotClass="bg-yellow-400" label="in progress" value={started} />}
            {failed > 0 && <Stat dotClass="bg-red-400" label="failed" value={failed} />}
          </div>
        </div>
      </div>
    </Link>
  );
}

function Stat({ dotClass, label, value }: { dotClass: string; label: string; value: number }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`w-1.5 h-1.5 rounded-full ${dotClass}`} />
      <span className="tabular-nums font-medium">{value}</span>
      <span className="text-white/50">{label}</span>
    </span>
  );
}

function Breadcrumb({ username }: { username: string }) {
  return (
    <nav className="flex items-center gap-2 text-sm text-muted-foreground mb-6">
      <Link to="/" className="hover:text-foreground transition-colors">Home</Link>
      <span>/</span>
      <span className="text-foreground">{username}</span>
    </nav>
  );
}
