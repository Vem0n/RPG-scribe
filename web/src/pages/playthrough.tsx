import { useEffect, useState, useCallback, useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import { getPlaythrough, getQuestDetail } from "@/lib/api";
import type { Playthrough, Game, QuestWithStatus, QuestDetail } from "@/lib/types";
import { useSyncRefresh } from "@/lib/useQuestEvents";
import { useThemeStyle } from "@/lib/theme";
import { ProgressDial, SyncStamp } from "@/components/themed";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Search, ChevronDown, CheckCircle2, Circle, XCircle,
  MapPin, Layers, Filter, BookOpen, X, SlidersHorizontal,
} from "lucide-react";

/* ------------------------------------------------------------------
 * Config (unchanged from original)
 * ------------------------------------------------------------------ */
const STATUS_CONFIG: Record<
  string,
  { label: string; variant: "default" | "secondary" | "outline" | "destructive"; dot: string; glow: string }
> = {
  finished: { label: "Finished", variant: "secondary", dot: "bg-green-400", glow: "shadow-[0_0_10px_rgba(74,222,128,0.6)]" },
  started:  { label: "In Progress", variant: "outline", dot: "bg-yellow-400", glow: "shadow-[0_0_10px_rgba(250,204,21,0.6)]" },
  failed:   { label: "Failed", variant: "destructive", dot: "bg-red-400", glow: "shadow-[0_0_10px_rgba(248,113,113,0.6)]" },
  unstarted:{ label: "Not Started", variant: "secondary", dot: "bg-muted-foreground/30", glow: "" },
};

const CATEGORY_LABELS: Record<string, Record<string, string>> = {
  default: { main: "Main Quests", prologue: "Prologue", side: "Side Quests", companion: "Companion Quests", board: "Board Quests", dlc: "DLC" },
  cyberpunk2077: { main: "Main Quests", side_job: "Side Jobs", gig: "Gigs", phantom_liberty: "Phantom Liberty" },
  fallout_new_vegas: { main: "Main Story", side: "Side Quests", companion: "Companion Quests", fo3_main: "Fallout 3 — Main", fo3_side: "Fallout 3 — Side", dlc_nv: "New Vegas DLC", dlc_fo3: "Fallout 3 DLC" },
};

const CATEGORY_ORDER: Record<string, string[]> = {
  default: ["main", "prologue", "side", "companion", "board", "dlc", "other"],
  cyberpunk2077: ["main", "side_job", "gig", "phantom_liberty"],
  fallout_new_vegas: ["main", "side", "companion", "fo3_main", "fo3_side", "dlc_nv", "dlc_fo3", "other"],
};


function isPhantomLiberty(q: QuestWithStatus): boolean {
  if (q.location === "Dogtown") return true;
  const k = q.quest_key;
  if (k.startsWith("q30") || k.startsWith("q31")) return true;
  if (k.startsWith("mq30")) return true;
  if (k.includes("ep1")) return true;
  return false;
}

function getDisplayCategory(q: QuestWithStatus, gameSlug?: string): string {
  if (gameSlug === "cyberpunk2077" && isPhantomLiberty(q)) return "phantom_liberty";
  return q.category || "other";
}

/* ------------------------------------------------------------------
 * Page
 * ------------------------------------------------------------------ */
export default function PlaythroughPage() {
  const { username, playthroughId } = useParams<{ username: string; playthroughId: string }>();

  const [playthrough, setPlaythrough] = useState<Playthrough | null>(null);
  const [game, setGame] = useState<Game | null>(null);
  const [quests, setQuests] = useState<QuestWithStatus[]>([]);
  const [loading, setLoading] = useState(true);

  const [filter, setFilter] = useState<string>("all");
  const [search, setSearch] = useState("");
  const [groupBy, setGroupBy] = useState<"category" | "location">("category");
  const [locationFilter, setLocationFilter] = useState<string>("all");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [showAdvanced, setShowAdvanced] = useState(false);

  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [detailCache, setDetailCache] = useState<Record<number, QuestDetail>>({});
  const [detailLoading, setDetailLoading] = useState<number | null>(null);

  // Walkthrough drawer
  const [guideQuest, setGuideQuest] = useState<QuestDetail | null>(null);

  // Ephemeral highlight of freshly-completed quest rows (triggered by WS sync)
  const [justChanged, setJustChanged] = useState<Set<number>>(new Set());

  const fetchData = useCallback(() => {
    if (!playthroughId) return;
    getPlaythrough(Number(playthroughId))
      .then((data) => {
        // diff against previous so we can briefly glow rows that just changed status
        setQuests((prev) => {
          const changed = new Set<number>();
          for (const q of data.quests) {
            const old = prev.find(p => p.quest_id === q.quest_id);
            if (old && old.status !== q.status) changed.add(q.quest_id);
          }
          if (changed.size) {
            setJustChanged(changed);
            setTimeout(() => setJustChanged(new Set()), 2500);
          }
          return data.quests;
        });
        setPlaythrough(data.playthrough);
        setGame(data.game);
        setDetailCache({});
      })
      .finally(() => setLoading(false));
  }, [playthroughId]);

  useEffect(() => { fetchData(); }, [fetchData]);
  useSyncRefresh(fetchData, { playthroughId: playthroughId ? Number(playthroughId) : undefined });

  // Per-game theme applied as inline CSS vars on the page wrapper below.
  const themeStyle = useThemeStyle(game?.slug);

  const toggleExpand = useCallback((questId: number) => {
    if (expandedId === questId) { setExpandedId(null); return; }
    setExpandedId(questId);
    if (!detailCache[questId] && playthroughId) {
      setDetailLoading(questId);
      getQuestDetail(Number(playthroughId), questId)
        .then((detail) => setDetailCache((prev) => ({ ...prev, [questId]: detail })))
        .finally(() => setDetailLoading(null));
    }
  }, [expandedId, detailCache, playthroughId]);

  /* ---------- derived data ---------- */
  const gameSlug = game?.slug;
  const catLabels = CATEGORY_LABELS[gameSlug || ""] || CATEGORY_LABELS.default;
  const catOrder = CATEGORY_ORDER[gameSlug || ""] || CATEGORY_ORDER.default;

  const allLocations = useMemo(
    () => [...new Set(quests.map((q) => q.location || "Unknown"))].sort(),
    [quests]
  );

  const allCategories = useMemo(() => {
    const cats = [...new Set(quests.map((q) => getDisplayCategory(q, gameSlug)))];
    cats.sort((a, b) => catOrder.indexOf(a) - catOrder.indexOf(b));
    return cats;
  }, [quests, gameSlug, catOrder]);

  const searchLower = search.toLowerCase();
  const filtered = quests.filter((q) => {
    if (filter !== "all" && q.status !== filter) return false;
    if (search && !q.name.toLowerCase().includes(searchLower)) return false;
    if (categoryFilter !== "all" && getDisplayCategory(q, gameSlug) !== categoryFilter) return false;
    if (groupBy === "location" && locationFilter !== "all" && (q.location || "Unknown") !== locationFilter) return false;
    return true;
  });

  const groups = new Map<string, QuestWithStatus[]>();
  for (const q of filtered) {
    const key = groupBy === "location" ? (q.location || "Unknown") : getDisplayCategory(q, gameSlug);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(q);
  }
  const sortedGroups = [...groups.keys()].sort((a, b) =>
    groupBy === "category" ? catOrder.indexOf(a) - catOrder.indexOf(b) : a.localeCompare(b)
  );
  const hasLocations = quests.some((q) => q.location);

  const statusCounts = {
    all: quests.length,
    finished: quests.filter((q) => q.status === "finished").length,
    started: quests.filter((q) => q.status === "started").length,
    failed: quests.filter((q) => q.status === "failed").length,
    unstarted: quests.filter((q) => q.status === "unstarted").length,
  };
  const completionPct = statusCounts.all > 0 ? (statusCounts.finished / statusCounts.all) * 100 : 0;

  // Open guide drawer — uses the currently-loaded detail for this quest
  const openGuideForExpanded = useCallback((questId: number) => {
    const d = detailCache[questId];
    if (d && d.guide_content) setGuideQuest(d);
  }, [detailCache]);

  /* ---------- render ---------- */
  if (loading) return <div className="flex items-center justify-center py-20 text-muted-foreground">Loading...</div>;
  if (!playthrough) return <div className="flex items-center justify-center py-20 text-muted-foreground">Playthrough not found</div>;

  const advancedFilterCount =
    (categoryFilter !== "all" ? 1 : 0) +
    (groupBy === "location" ? 1 : 0) +
    (locationFilter !== "all" ? 1 : 0);

  return (
    <div style={themeStyle}>
      {/* Persistent background — unchanged */}
      {gameSlug && (
        <>
          <div className="fixed inset-0 z-0 bg-cover bg-center bg-no-repeat pointer-events-none" style={{ backgroundImage: `url(/backgrounds/${gameSlug}.jpg)` }} />
          <div className="fixed inset-0 z-0 bg-background/80 pointer-events-none" />
        </>
      )}

      <div className="relative z-10">
        {/* Breadcrumb */}
        <nav className="flex items-center gap-2 text-sm text-muted-foreground mb-6">
          <Link to="/" className="hover:text-foreground transition-colors">Home</Link>
          <span>/</span>
          <Link to={`/${username}`} className="hover:text-foreground transition-colors">{username}</Link>
          <span>/</span>
          <span className="text-foreground">{playthrough.name}</span>
        </nav>

        {/* Header: title + compact progress dial + synced stamp */}
        <div className="flex items-center gap-6 mb-6">
          <ProgressDial pct={completionPct} size={64} />
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl font-semibold truncate" style={{ fontFamily: "'Orbitron', sans-serif" }}>
              {playthrough.name}
            </h1>
            <div className="flex items-center gap-3 mt-1 text-sm text-muted-foreground">
              <span>{statusCounts.finished} / {statusCounts.all} quests · {Math.round(completionPct)}%</span>
              {playthrough.last_synced_at && (
                <>
                  <span className="text-muted-foreground/50">·</span>
                  <SyncStamp at={playthrough.last_synced_at} />
                </>
              )}
            </div>
          </div>
        </div>

        {/* Search bar */}
        <div className="relative mb-3">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search quests..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 rounded-lg border border-border bg-card/60 backdrop-blur-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        {/* Status filter pills + Advanced toggle on the same row */}
        <div className="flex gap-2 mb-4 flex-wrap items-center">
          {(["all", "started", "finished", "failed", "unstarted"] as const).map((s) => (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                filter === s ? "bg-primary text-primary-foreground" : "bg-secondary text-secondary-foreground hover:bg-secondary/80"
              }`}
            >
              {s === "all" ? "All" : STATUS_CONFIG[s].label} ({statusCounts[s]})
            </button>
          ))}

          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={() => setShowAdvanced((v) => !v)}
              className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                showAdvanced ? "bg-primary/20 text-primary border border-primary/40" : "bg-secondary text-secondary-foreground hover:bg-secondary/80"
              }`}
            >
              <SlidersHorizontal className="w-3.5 h-3.5" />
              Filters
              {advancedFilterCount > 0 && (
                <span className="inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 text-[10px] font-semibold rounded-full bg-primary text-primary-foreground">
                  {advancedFilterCount}
                </span>
              )}
              <ChevronDown className={`w-3.5 h-3.5 transition-transform ${showAdvanced ? "rotate-180" : ""}`} />
            </button>
          </div>
        </div>

        {/* Advanced filters (collapsible) */}
        {showAdvanced && (
          <div className="mb-6 rounded-lg border border-border/70 bg-card/60 backdrop-blur-sm p-4 space-y-4 animate-in fade-in slide-in-from-top-1 duration-200">
            {allCategories.length > 1 && (
              <div>
                <div className="flex items-center gap-2 mb-2 text-xs uppercase tracking-wider text-muted-foreground">
                  <Filter className="w-3 h-3" />
                  Category
                </div>
                <div className="flex gap-2 flex-wrap">
                  <FilterPill active={categoryFilter === "all"} onClick={() => setCategoryFilter("all")}>
                    All <span className="opacity-60 ml-1">({quests.length})</span>
                  </FilterPill>
                  {allCategories.map((cat) => {
                    const count = quests.filter((q) => getDisplayCategory(q, gameSlug) === cat).length;
                    return (
                      <FilterPill key={cat} active={categoryFilter === cat} onClick={() => setCategoryFilter(cat)}>
                        {catLabels[cat] || cat} <span className="opacity-60 ml-1">({count})</span>
                      </FilterPill>
                    );
                  })}
                </div>
              </div>
            )}

            {hasLocations && (
              <div>
                <div className="flex items-center gap-2 mb-2 text-xs uppercase tracking-wider text-muted-foreground">
                  <Layers className="w-3 h-3" />
                  Group by
                </div>
                <div className="flex gap-2">
                  <FilterPill active={groupBy === "category"} onClick={() => { setGroupBy("category"); setLocationFilter("all"); }}>
                    <Layers className="w-3.5 h-3.5 inline mr-1.5" /> Category
                  </FilterPill>
                  <FilterPill active={groupBy === "location"} onClick={() => setGroupBy("location")}>
                    <MapPin className="w-3.5 h-3.5 inline mr-1.5" /> Location
                  </FilterPill>
                </div>
              </div>
            )}

            {groupBy === "location" && hasLocations && (
              <div>
                <div className="flex items-center gap-2 mb-2 text-xs uppercase tracking-wider text-muted-foreground">
                  <MapPin className="w-3 h-3" />
                  Location
                </div>
                <div className="flex gap-2 flex-wrap">
                  <FilterPill active={locationFilter === "all"} onClick={() => setLocationFilter("all")}>All locations</FilterPill>
                  {allLocations.map((loc) => (
                    <FilterPill key={loc} active={locationFilter === loc} onClick={() => setLocationFilter(loc)}>
                      <MapPin className="w-3 h-3 inline mr-1" /> {loc}
                    </FilterPill>
                  ))}
                </div>
              </div>
            )}

            {advancedFilterCount > 0 && (
              <div className="pt-2 border-t border-border/40">
                <button
                  onClick={() => { setCategoryFilter("all"); setLocationFilter("all"); setGroupBy("category"); }}
                  className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  Clear advanced filters
                </button>
              </div>
            )}
          </div>
        )}

        <Separator className="mb-6" />

        {filtered.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            {search ? `No quests matching "${search}"` : "No quests matching this filter"}
          </div>
        ) : (
          <div className="space-y-8">
            {sortedGroups.map((groupKey) => {
              const groupQuests = groups.get(groupKey)!;
              const label = groupBy === "category" ? (catLabels[groupKey] || groupKey) : groupKey;
              const groupFinished = groupQuests.filter(q => q.status === "finished").length;
              const groupPct = groupQuests.length > 0 ? (groupFinished / groupQuests.length) * 100 : 0;
              return (
                <section key={groupKey}>
                  <div className="flex items-baseline gap-3 mb-3">
                    {groupBy === "location" && <MapPin className="w-4 h-4 text-muted-foreground mt-0.5" />}
                    <h2 className="text-lg font-medium">{label}</h2>
                    <span className="text-sm text-muted-foreground">{groupFinished}/{groupQuests.length}</span>
                    <div className="flex-1 h-px bg-border/40 relative overflow-hidden">
                      <div className="absolute inset-y-0 left-0 bg-primary/50 transition-all" style={{ width: `${groupPct}%` }} />
                    </div>
                  </div>
                  <div className="rounded-lg border border-border overflow-hidden divide-y divide-border bg-card/60 backdrop-blur-sm">
                    {groupQuests.map((quest) => {
                      const cfg = STATUS_CONFIG[quest.status] || STATUS_CONFIG.unstarted;
                      const isExpanded = expandedId === quest.quest_id;
                      const detail = detailCache[quest.quest_id];
                      const isLoading = detailLoading === quest.quest_id;
                      const glowing = justChanged.has(quest.quest_id);

                      return (
                        <div key={quest.quest_id} className={`group relative transition-colors ${glowing ? "bg-primary/10" : ""}`}>
                          {/* hover edge tick */}
                          <span className="absolute left-0 top-0 bottom-0 w-0.5 bg-primary origin-top scale-y-0 group-hover:scale-y-100 transition-transform duration-200" />
                          <button
                            onClick={() => toggleExpand(quest.quest_id)}
                            className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-accent/30 transition-colors"
                          >
                            <div className="flex items-center gap-3 min-w-0">
                              <div className={`w-2 h-2 rounded-full shrink-0 ${cfg.dot} ${quest.status === "started" ? cfg.glow : ""}`} />
                              <span className="font-medium truncate">{quest.name}</span>
                              {quest.location && (
                                <span className="hidden md:inline-flex items-center gap-1 text-xs text-muted-foreground/70 ml-1">
                                  <MapPin className="w-3 h-3" />
                                  {quest.location}
                                </span>
                              )}
                            </div>
                            <div className="flex items-center gap-3 shrink-0 ml-4">
                              {quest.stages_total > 0 && (
                                <MiniStageBar completed={quest.stages_completed} total={quest.stages_total} />
                              )}
                              <Badge variant={cfg.variant}>{cfg.label}</Badge>
                              <ChevronDown className={`w-4 h-4 text-muted-foreground transition-transform ${isExpanded ? "rotate-180" : ""}`} />
                            </div>
                          </button>

                          {isExpanded && (
                            <div className="border-t border-border bg-background/40 backdrop-blur-sm px-4 py-4">
                              {isLoading ? (
                                <div className="text-sm text-muted-foreground py-2">Loading...</div>
                              ) : detail ? (
                                <QuestDrawer
                                  detail={detail}
                                  questStatus={quest.status}
                                  onOpenGuide={() => openGuideForExpanded(quest.quest_id)}
                                />
                              ) : (
                                <div className="text-sm text-muted-foreground py-2">Failed to load quest details.</div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </section>
              );
            })}
          </div>
        )}
      </div>

      {/* Walkthrough side drawer */}
      <GuideDrawer quest={guideQuest} onClose={() => setGuideQuest(null)} />
    </div>
  );
}

/* ------------------------------------------------------------------
 * Mini stage bar — tick-mark style, replaces "1/9" text
 * ------------------------------------------------------------------ */
function MiniStageBar({ completed, total }: { completed: number; total: number }) {
  // Filled portion uses the game-theme primary; status (green/yellow/red) is conveyed
  // by the dot + badge already.
  if (total <= 12) {
    return (
      <div className="flex items-center gap-2">
        <div className="flex gap-0.5">
          {Array.from({ length: total }).map((_, i) => (
            <span
              key={i}
              aria-hidden
              className={`w-1 h-3 rounded-sm ${i < completed ? "bg-primary" : "bg-muted-foreground/20"}`}
            />
          ))}
        </div>
        <span className="text-xs text-muted-foreground tabular-nums">{completed}/{total}</span>
      </div>
    );
  }
  const pct = (completed / total) * 100;
  return (
    <div className="flex items-center gap-2 w-28">
      <div className="flex-1 h-1 rounded-full bg-muted-foreground/20 overflow-hidden">
        <div className="h-full bg-primary transition-all" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-muted-foreground tabular-nums">{completed}/{total}</span>
    </div>
  );
}

/* ------------------------------------------------------------------
 * Filter pill (matches existing pill vocabulary)
 * ------------------------------------------------------------------ */
function FilterPill({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
        active ? "bg-primary text-primary-foreground" : "bg-secondary text-secondary-foreground hover:bg-secondary/80"
      }`}
    >
      {children}
    </button>
  );
}

/* ------------------------------------------------------------------
 * Quest drawer (inline) — now has "Open guide" button if guide_content exists
 * ------------------------------------------------------------------ */
function QuestDrawer({
  detail, questStatus, onOpenGuide,
}: { detail: QuestDetail; questStatus: string; onOpenGuide: () => void }) {
  return (
    <div className="space-y-4">
      {detail.description && <p className="text-sm text-muted-foreground">{detail.description}</p>}

      {detail.stages.length > 0 && (() => {
        const described = detail.stages.filter((s) => !/^Stage \d+$/.test(s.name));
        if (described.length === 0) return null;
        return (
          <div>
            <h3 className="text-sm font-medium mb-2">
              Stages ({described.filter((s) => s.completed).length}/{described.length})
            </h3>
            <div className="space-y-1.5">
              {described.map((stage) => (
                <div key={stage.stage_key} className="flex items-center gap-2 text-sm">
                  {stage.completed
                    ? <CheckCircle2 className="w-4 h-4 text-green-400 shrink-0" />
                    : questStatus === "finished" || questStatus === "failed"
                      ? <XCircle className="w-4 h-4 text-red-400/60 shrink-0" />
                      : <Circle className="w-4 h-4 text-muted-foreground/40 shrink-0" />}
                  <span className={stage.completed ? "line-through text-muted-foreground" : ""}>{stage.name}</span>
                </div>
              ))}
            </div>
          </div>
        );
      })()}

      {detail.guide_content && detail.guide_content.length > 0 && (
        <button
          onClick={onOpenGuide}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-md bg-primary/10 text-primary border border-primary/30 hover:bg-primary/20 transition-colors text-sm font-medium"
        >
          <BookOpen className="w-4 h-4" />
          Open walkthrough
        </button>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------
 * Guide drawer — slides in from right
 * ------------------------------------------------------------------ */
function GuideDrawer({ quest, onClose }: { quest: QuestDetail | null; onClose: () => void }) {
  // esc to close
  useEffect(() => {
    const on = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [onClose]);

  const open = !!quest;
  return (
    <>
      {/* scrim */}
      <div
        onClick={onClose}
        aria-hidden
        className={`fixed inset-0 z-40 bg-black/50 backdrop-blur-sm transition-opacity ${
          open ? "opacity-100" : "opacity-0 pointer-events-none"
        }`}
      />
      {/* panel */}
      <aside
        role="dialog" aria-modal="true" aria-label="Quest walkthrough"
        className={`fixed right-0 top-0 bottom-0 z-50 w-full max-w-lg bg-card/95 backdrop-blur-xl border-l border-border shadow-2xl transition-transform duration-300 ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {quest && (
          <div className="h-full flex flex-col">
            <header className="flex items-start justify-between gap-4 p-5 border-b border-border">
              <div className="min-w-0">
                <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-muted-foreground mb-1">
                  <BookOpen className="w-3 h-3" /> Walkthrough
                </div>
                <h2 className="text-lg font-semibold truncate" style={{ fontFamily: "'Orbitron', sans-serif" }}>{quest.name}</h2>
                {quest.location && <div className="text-xs text-muted-foreground mt-1 flex items-center gap-1"><MapPin className="w-3 h-3" />{quest.location}</div>}
              </div>
              <button onClick={onClose} className="shrink-0 p-1.5 rounded-md hover:bg-accent transition-colors" aria-label="Close">
                <X className="w-4 h-4" />
              </button>
            </header>
            <div className="flex-1 overflow-y-auto p-5">
              <div className="text-sm whitespace-pre-wrap leading-relaxed text-foreground/90">
                {quest.guide_content}
              </div>
            </div>
            <footer className="p-4 border-t border-border text-xs text-muted-foreground">
              Press <kbd className="px-1.5 py-0.5 rounded border border-border bg-muted/50">Esc</kbd> to close
            </footer>
          </div>
        )}
      </aside>
    </>
  );
}
