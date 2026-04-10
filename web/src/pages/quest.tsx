import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getQuestDetail } from "@/lib/api";
import type { QuestDetail } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

export default function QuestPage() {
  const { username, playthroughId, questId } = useParams<{
    username: string;
    playthroughId: string;
    questId: string;
  }>();
  const [quest, setQuest] = useState<QuestDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [showGuide, setShowGuide] = useState(false);

  useEffect(() => {
    if (playthroughId && questId) {
      getQuestDetail(Number(playthroughId), Number(questId))
        .then(setQuest)
        .finally(() => setLoading(false));
    }
  }, [playthroughId, questId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  if (!quest) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-muted-foreground">Quest not found</div>
      </div>
    );
  }

  const statusBadge: Record<
    string,
    {
      label: string;
      variant: "default" | "secondary" | "outline" | "destructive";
    }
  > = {
    finished: { label: "Finished", variant: "secondary" },
    started: { label: "In Progress", variant: "outline" },
    failed: { label: "Failed", variant: "destructive" },
    unstarted: { label: "Not Started", variant: "secondary" },
  };

  const cfg = statusBadge[quest.status] || statusBadge.unstarted;
  const completedStages = quest.stages.filter((s) => s.completed).length;

  return (
    <div>
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
        <Link
          to={`/${username}/${playthroughId}`}
          className="hover:text-foreground transition-colors"
        >
          Playthrough
        </Link>
        <span>/</span>
        <span className="text-foreground">{quest.name}</span>
      </nav>

      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold">{quest.name}</h1>
          {quest.description && (
            <p className="text-muted-foreground mt-1">{quest.description}</p>
          )}
        </div>
        <Badge variant={cfg.variant} className="text-base px-3 py-1">
          {cfg.label}
        </Badge>
      </div>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-lg">
            Stages ({completedStages}/{quest.stages.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {(() => {
            const described = quest.stages.filter(
              (s) => !/^Stage \d+$/.test(s.name)
            );
            return described.length === 0;
          })() ? (
            <p className="text-muted-foreground">
              No stage data available for this quest.
            </p>
          ) : (
            <div className="space-y-3">
              {quest.stages.filter((s) => !/^Stage \d+$/.test(s.name)).map((stage, i) => (
                <div key={stage.stage_key} className="flex items-start gap-3">
                  <div className="mt-0.5">
                    {stage.completed ? (
                      <svg
                        className="w-5 h-5 text-green-400"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={2}
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                        />
                      </svg>
                    ) : (
                      <svg
                        className="w-5 h-5 text-muted-foreground/40"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={2}
                      >
                        <circle cx="12" cy="12" r="9" />
                      </svg>
                    )}
                  </div>
                  <span
                    className={
                      stage.completed
                        ? "line-through text-muted-foreground"
                        : ""
                    }
                  >
                    {i + 1}. {stage.name}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {quest.guide_content && quest.guide_content.length > 0 && (
        <>
          <button
            onClick={() => setShowGuide(!showGuide)}
            className="px-4 py-2 rounded-md bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-colors mb-4"
          >
            {showGuide ? "Hide Guide" : "Show Guide"}
          </button>
          {showGuide && (
            <>
              <Separator className="my-4" />
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Quest Guide</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="max-w-none whitespace-pre-wrap">
                    {quest.guide_content}
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </>
      )}
    </div>
  );
}
