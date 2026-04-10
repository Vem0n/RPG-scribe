export interface User {
  id: number;
  username: string;
  created_at: string;
  updated_at: string;
  last_game_slug?: string;
  last_game_name?: string;
}

export interface Game {
  id: number;
  slug: string;
  name: string;
  created_at: string;
}

export interface QuestSummary {
  total: number;
  finished: number;
  started: number;
  failed: number;
  unstarted: number;
}

export interface PlaythroughWithGame {
  id: number;
  user_id: number;
  game_id: number;
  name: string;
  external_id?: string;
  last_synced_at?: string;
  created_at: string;
  updated_at: string;
  game: Game;
  quest_summary: QuestSummary;
}

export interface Playthrough {
  id: number;
  user_id: number;
  game_id: number;
  name: string;
  external_id?: string;
  last_synced_at?: string;
  created_at: string;
  updated_at: string;
}

export interface QuestWithStatus {
  quest_id: number;
  quest_key: string;
  name: string;
  category?: string;
  location?: string;
  status: "unstarted" | "started" | "finished" | "failed";
  stages_completed: number;
  stages_total: number;
}

export interface StageDetail {
  stage_key: string;
  name: string;
  completed: boolean;
  sort_order: number;
}

export interface QuestDetail {
  id: number;
  quest_key: string;
  name: string;
  description?: string;
  category?: string;
  location?: string;
  status: string;
  guide_content?: string;
  stages: StageDetail[];
}
