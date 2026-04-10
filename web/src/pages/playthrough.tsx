import { useEffect, useState, useCallback } from "react";
import { Link, useParams } from "react-router-dom";
import { getPlaythrough, getQuestDetail } from "@/lib/api";
import type { Playthrough, Game, QuestWithStatus, QuestDetail } from "@/lib/types";
import { useSyncRefresh } from "@/lib/useQuestEvents";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Search, ChevronDown, CheckCircle2, Circle, XCircle, MapPin, Layers, Filter } from "lucide-react";

const STATUS_CONFIG: Record<
  string,
  {
    label: string;
    variant: "default" | "secondary" | "outline" | "destructive";
    dot: string;
  }
> = {
  finished: { label: "Finished", variant: "secondary", dot: "bg-green-400" },
  started: { label: "In Progress", variant: "outline", dot: "bg-yellow-400" },
  failed: { label: "Failed", variant: "destructive", dot: "bg-red-400" },
  unstarted: {
    label: "Not Started",
    variant: "secondary",
    dot: "bg-muted-foreground/30",
  },
};

const CATEGORY_LABELS: Record<string, Record<string, string>> = {
  default: {
    main: "Main Quests",
    prologue: "Prologue",
    side: "Side Quests",
    companion: "Companion Quests",
    board: "Board Quests",
    dlc: "DLC",
  },
  cyberpunk2077: {
    main: "Main Quests",
    side_job: "Side Jobs",
    gig: "Gigs",
    phantom_liberty: "Phantom Liberty",
  },
  fallout_new_vegas: {
    main: "Main Story",
    side: "Side Quests",
    companion: "Companion Quests",
    fo3_main: "Fallout 3 — Main",
    fo3_side: "Fallout 3 — Side",
    dlc_nv: "New Vegas DLC",
    dlc_fo3: "Fallout 3 DLC",
  },
};

const CATEGORY_ORDER: Record<string, string[]> = {
  default: ["main", "prologue", "side", "companion", "board", "dlc", "other"],
  cyberpunk2077: ["main", "side_job", "gig", "phantom_liberty"],
  fallout_new_vegas: [
    "main",
    "side",
    "companion",
    "fo3_main",
    "fo3_side",
    "dlc_nv",
    "dlc_fo3",
    "other",
  ],
};

/** Identify Phantom Liberty quests by location or quest_key pattern. */
function isPhantomLiberty(q: QuestWithStatus): boolean {
  if (q.location === "Dogtown") return true;
  const k = q.quest_key;
  if (k.startsWith("q30") || k.startsWith("q31")) return true;
  if (k.startsWith("mq30")) return true;
  if (k.includes("ep1")) return true;
  return false;
}

/** Get the display category for a quest, applying game-specific overrides. */
function getDisplayCategory(q: QuestWithStatus, gameSlug?: string): string {
  if (gameSlug === "cyberpunk2077" && isPhantomLiberty(q)) {
    return "phantom_liberty";
  }
  return q.category || "other";
}

export default function PlaythroughPage() {
  const { username, playthroughId } = useParams<{
    username: string;
    playthroughId: string;
  }>();
  const [playthrough, setPlaythrough] = useState<Playthrough | null>(null);
  const [game, setGame] = useState<Game | null>(null);
  const [quests, setQuests] = useState<QuestWithStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");
  const [search, setSearch] = useState("");
  const [groupBy, setGroupBy] = useState<"category" | "location">("category");
  const [locationFilter, setLocationFilter] = useState<string>("all");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [detailCache, setDetailCache] = useState<Record<number, QuestDetail>>(
    {}
  );
  const [detailLoading, setDetailLoading] = useState<number | null>(null);

  const fetchData = useCallback(() => {
    if (!playthroughId) return;
    getPlaythrough(Number(playthroughId))
      .then((data) => {
        setPlaythrough(data.playthrough);
        setGame(data.game);
        setQuests(data.quests);
        // Clear detail cache so expanded quests re-fetch fresh data
        setDetailCache({});
      })
      .finally(() => setLoading(false));
  }, [playthroughId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Auto-refresh when a sync completes for this playthrough
  useSyncRefresh(fetchData, { playthroughId: playthroughId ? Number(playthroughId) : undefined });

  const toggleExpand = useCallback(
    (questId: number) => {
      if (expandedId === questId) {
        setExpandedId(null);
        return;
      }
      setExpandedId(questId);
      if (!detailCache[questId] && playthroughId) {
        setDetailLoading(questId);
        getQuestDetail(Number(playthroughId), questId)
          .then((detail) => {
            setDetailCache((prev) => ({ ...prev, [questId]: detail }));
          })
          .finally(() => setDetailLoading(null));
      }
    },
    [expandedId, detailCache, playthroughId]
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  if (!playthrough) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-muted-foreground">Playthrough not found</div>
      </div>
    );
  }

  const gameSlug = game?.slug;
  const allLocations = [...new Set(quests.map((q) => q.location || "Unknown"))].sort();
  const catLabels = CATEGORY_LABELS[gameSlug || ""] || CATEGORY_LABELS.default;
  const catOrder = CATEGORY_ORDER[gameSlug || ""] || CATEGORY_ORDER.default;

  // Collect all display categories present in the quest data
  const allCategories = [...new Set(quests.map((q) => getDisplayCategory(q, gameSlug)))];
  allCategories.sort((a, b) => catOrder.indexOf(a) - catOrder.indexOf(b));

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

  const hasLocations = quests.some((q) => q.location);

  const sortedGroups = [...groups.keys()].sort((a, b) => {
    if (groupBy === "category") {
      return catOrder.indexOf(a) - catOrder.indexOf(b);
    }
    return a.localeCompare(b);
  });

  const statusCounts = {
    all: quests.length,
    finished: quests.filter((q) => q.status === "finished").length,
    started: quests.filter((q) => q.status === "started").length,
    failed: quests.filter((q) => q.status === "failed").length,
    unstarted: quests.filter((q) => q.status === "unstarted").length,
  };

  return (
    <>
      {gameSlug && (
        <>
          <div
            className="fixed inset-0 z-0 bg-cover bg-center bg-no-repeat pointer-events-none"
            style={{ backgroundImage: `url(/backgrounds/${gameSlug}.jpg)` }}
          />
          <div className="fixed inset-0 z-0 bg-background/80 pointer-events-none" />
        </>
      )}
      <div className="relative z-10">
      <nav className="flex items-center gap-2 text-sm text-muted-foreground mb-6">
        <Link to="/" className="hover:text-foreground transition-colors">
          Home
        </Link>
        <span>/</span>
        <Link
          to={`/${username}`}
          className="hover:text-foreground transition-colors"
        >
          {username}
        </Link>
        <span>/</span>
        <span className="text-foreground">{playthrough.name}</span>
      </nav>

      <div className="flex items-baseline justify-between mb-6">
        <h1 className="text-2xl font-semibold">{playthrough.name}</h1>
        {playthrough.last_synced_at && (
          <span className="text-sm text-muted-foreground">
            Synced {new Date(playthrough.last_synced_at).toLocaleString()}
          </span>
        )}
      </div>

      {/* Search bar */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <input
          type="text"
          placeholder="Search quests..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-10 pr-4 py-2 rounded-lg border border-border bg-card text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </div>

      {/* Status filter pills */}
      <div className="flex gap-2 mb-6 flex-wrap">
        {(["all", "started", "finished", "failed", "unstarted"] as const).map(
          (s) => (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                filter === s
                  ? "bg-primary text-primary-foreground"
                  : "bg-secondary text-secondary-foreground hover:bg-secondary/80"
              }`}
            >
              {s === "all" ? "All" : STATUS_CONFIG[s].label} ({statusCounts[s]})
            </button>
          )
        )}
      </div>

      {/* Category filter pills */}
      {allCategories.length > 1 && (
        <div className="flex items-center gap-2 mb-4 flex-wrap">
          <Filter className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
          <button
            onClick={() => setCategoryFilter("all")}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              categoryFilter === "all"
                ? "bg-primary text-primary-foreground"
                : "bg-secondary text-secondary-foreground hover:bg-secondary/80"
            }`}
          >
            All
          </button>
          {allCategories.map((cat) => {
            const count = quests.filter((q) => getDisplayCategory(q, gameSlug) === cat).length;
            return (
              <button
                key={cat}
                onClick={() => setCategoryFilter(cat)}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  categoryFilter === cat
                    ? "bg-primary text-primary-foreground"
                    : "bg-secondary text-secondary-foreground hover:bg-secondary/80"
                }`}
              >
                {catLabels[cat] || cat} ({count})
              </button>
            );
          })}
        </div>
      )}

      {/* Group-by toggle */}
      {hasLocations && (
        <div className="flex items-center gap-2 mb-6">
          <span className="text-sm text-muted-foreground mr-1">Group by:</span>
          <button
            onClick={() => { setGroupBy("category"); setLocationFilter("all"); }}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              groupBy === "category"
                ? "bg-primary text-primary-foreground"
                : "bg-secondary text-secondary-foreground hover:bg-secondary/80"
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            Category
          </button>
          <button
            onClick={() => setGroupBy("location")}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              groupBy === "location"
                ? "bg-primary text-primary-foreground"
                : "bg-secondary text-secondary-foreground hover:bg-secondary/80"
            }`}
          >
            <MapPin className="w-3.5 h-3.5" />
            Location
          </button>
        </div>
      )}

      {/* Location filter pills */}
      {groupBy === "location" && hasLocations && (
        <div className="flex gap-2 mb-6 flex-wrap">
          <button
            onClick={() => setLocationFilter("all")}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              locationFilter === "all"
                ? "bg-primary text-primary-foreground"
                : "bg-secondary text-secondary-foreground hover:bg-secondary/80"
            }`}
          >
            All Locations
          </button>
          {allLocations.map((loc) => (
            <button
              key={loc}
              onClick={() => setLocationFilter(loc)}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                locationFilter === loc
                  ? "bg-primary text-primary-foreground"
                  : "bg-secondary text-secondary-foreground hover:bg-secondary/80"
              }`}
            >
              <MapPin className="w-3 h-3" />
              {loc}
            </button>
          ))}
        </div>
      )}

      <Separator className="mb-6" />

      {filtered.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          {search
            ? `No quests matching "${search}"`
            : "No quests matching this filter"}
        </div>
      ) : (
        <div className="space-y-8">
          {sortedGroups.map((groupKey) => {
            const groupQuests = groups.get(groupKey)!;
            const label = groupBy === "category"
              ? (catLabels[groupKey] || groupKey)
              : groupKey;
            return (
              <section key={groupKey}>
                <div className="flex items-baseline gap-3 mb-3">
                  {groupBy === "location" && <MapPin className="w-4 h-4 text-muted-foreground mt-0.5" />}
                  <h2 className="text-lg font-medium">{label}</h2>
                  <span className="text-sm text-muted-foreground">
                    {groupQuests.length}
                  </span>
                </div>
                <div className="rounded-lg border border-border overflow-hidden divide-y divide-border">
                  {groupQuests.map((quest) => {
                    const cfg =
                      STATUS_CONFIG[quest.status] || STATUS_CONFIG.unstarted;
                    const isExpanded = expandedId === quest.quest_id;
                    const detail = detailCache[quest.quest_id];
                    const isLoading = detailLoading === quest.quest_id;

                    return (
                      <div key={quest.quest_id} className="bg-card">
                        <button
                          onClick={() => toggleExpand(quest.quest_id)}
                          className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-accent/50 transition-colors"
                        >
                          <div className="flex items-center gap-3 min-w-0">
                            <div
                              className={`w-2 h-2 rounded-full shrink-0 ${cfg.dot}`}
                            />
                            <span className="font-medium truncate">
                              {quest.name}
                            </span>
                          </div>
                          <div className="flex items-center gap-3 shrink-0 ml-4">
                            {quest.stages_total > 0 && (
                              <span className="text-sm text-muted-foreground">
                                {quest.stages_completed}/{quest.stages_total}
                              </span>
                            )}
                            <Badge variant={cfg.variant}>{cfg.label}</Badge>
                            <ChevronDown
                              className={`w-4 h-4 text-muted-foreground transition-transform ${
                                isExpanded ? "rotate-180" : ""
                              }`}
                            />
                          </div>
                        </button>

                        {isExpanded && (
                          <div className="border-t border-border bg-background px-4 py-4">
                            {isLoading ? (
                              <div className="text-sm text-muted-foreground py-2">
                                Loading...
                              </div>
                            ) : detail ? (
                              <QuestDrawer detail={detail} questStatus={quest.status} />
                            ) : (
                              <div className="text-sm text-muted-foreground py-2">
                                Failed to load quest details.
                              </div>
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
    </>
  );
}

function QuestDrawer({ detail, questStatus }: { detail: QuestDetail; questStatus: string }) {
  const [showGuide, setShowGuide] = useState(false);

  return (
    <div className="space-y-4">
      {detail.description && (
        <p className="text-sm text-muted-foreground">{detail.description}</p>
      )}

      {detail.stages.length > 0 && (() => {
        const described = detail.stages.filter(
          (s) => !/^Stage \d+$/.test(s.name)
        );
        if (described.length === 0) return null;
        return (
          <div>
            <h3 className="text-sm font-medium mb-2">
              Stages ({described.filter((s) => s.completed).length}/
              {described.length})
            </h3>
            <div className="space-y-1.5">
              {described.map((stage) => (
                <div
                  key={stage.stage_key}
                  className="flex items-center gap-2 text-sm"
                >
                  {stage.completed ? (
                    <CheckCircle2 className="w-4 h-4 text-green-400 shrink-0" />
                  ) : questStatus === "finished" || questStatus === "failed" ? (
                    <XCircle className="w-4 h-4 text-red-400/60 shrink-0" />
                  ) : (
                    <Circle className="w-4 h-4 text-muted-foreground/40 shrink-0" />
                  )}
                  <span
                    className={
                      stage.completed
                        ? "line-through text-muted-foreground"
                        : ""
                    }
                  >
                    {stage.name}
                  </span>
                </div>
              ))}
            </div>
          </div>
        );
      })()}

      {detail.guide_content && detail.guide_content.length > 0 && (
        <div>
          <button
            onClick={() => setShowGuide(!showGuide)}
            className="text-sm font-medium text-primary hover:underline"
          >
            {showGuide ? "Hide Guide" : "Show Guide"}
          </button>
          {showGuide && (
            <div className="mt-2 text-sm whitespace-pre-wrap rounded-md bg-muted/50 p-3">
              {detail.guide_content}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
