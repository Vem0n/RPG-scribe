import { useEffect, useState, useCallback } from "react";
import { Link, useParams } from "react-router-dom";
import { getUserPlaythroughs } from "@/lib/api";
import type { PlaythroughWithGame } from "@/lib/types";
import { useSyncRefresh } from "@/lib/useQuestEvents";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";

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
      <div className="flex items-center justify-center py-20">
        <div className="text-muted-foreground">Loading...</div>
      </div>
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
      <div className="space-y-8">
        {Array.from(byGame.entries()).map(([, gamePts]) => (
          <section key={gamePts[0].game.slug}>
            <h2 className="text-xl font-medium mb-4">
              {gamePts[0].game.name}
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {gamePts.map((pt) => {
                const total = pt.quest_summary.total;
                const finished = pt.quest_summary.finished;
                const pct =
                  total > 0 ? Math.round((finished / total) * 100) : 0;
                const slug = pt.game.slug;

                return (
                  <Link key={pt.id} to={`/${username}/${pt.id}`}>
                    <div className="group relative overflow-hidden rounded-xl ring-1 ring-foreground/10 hover:ring-foreground/20 transition-all cursor-pointer">
                      {/* Background art */}
                      <div
                        className="absolute inset-0 bg-cover bg-center transition-transform duration-500 group-hover:scale-105"
                        style={{ backgroundImage: `url(/backgrounds/${slug}.jpg)` }}
                      />
                      <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/60 to-black/40" />

                      {/* Content */}
                      <div className="relative p-6 min-h-[180px] flex flex-col justify-end gap-3">
                        <div>
                          <div className="font-semibold text-lg text-white">
                            {pt.name}
                          </div>
                          <div className="text-sm text-white/60">
                            {pt.last_synced_at
                              ? `Last synced ${new Date(pt.last_synced_at).toLocaleString()}`
                              : "Never synced"}
                          </div>
                        </div>

                        <div className="flex items-center gap-2">
                          <Progress value={pct} className="flex-1 bg-white/20" />
                          <span className="text-sm text-white/70 w-12 text-right">
                            {pct}%
                          </span>
                        </div>

                        <div className="flex gap-2 flex-wrap">
                          {pt.quest_summary.finished > 0 && (
                            <Badge variant="secondary" className="bg-white/15 text-white border-0">
                              {pt.quest_summary.finished} finished
                            </Badge>
                          )}
                          {pt.quest_summary.started > 0 && (
                            <Badge variant="outline" className="bg-white/10 text-white/80 border-white/20">
                              {pt.quest_summary.started} in progress
                            </Badge>
                          )}
                          {pt.quest_summary.failed > 0 && (
                            <Badge variant="destructive">
                              {pt.quest_summary.failed} failed
                            </Badge>
                          )}
                          <Badge variant="secondary" className="bg-white/10 text-white/50 border-0">
                            {pt.quest_summary.total} total
                          </Badge>
                        </div>
                      </div>
                    </div>
                  </Link>
                );
              })}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}

function Breadcrumb({ username }: { username: string }) {
  return (
    <nav className="flex items-center gap-2 text-sm text-muted-foreground mb-6">
      <Link to="/" className="hover:text-foreground transition-colors">
        Home
      </Link>
      <span>/</span>
      <span className="text-foreground">{username}</span>
    </nav>
  );
}
