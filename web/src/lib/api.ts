import type {
  User,
  PlaythroughWithGame,
  Playthrough,
  QuestWithStatus,
  QuestDetail,
  Game,
} from "./types";

const API_BASE = "/api/v1";

async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function getUsers(): Promise<User[]> {
  const data = await fetchJSON<{ users: User[] }>("/users");
  return data.users;
}

export async function getGames(): Promise<Game[]> {
  const data = await fetchJSON<{ games: Game[] }>("/games");
  return data.games;
}

export async function getUserPlaythroughs(
  username: string
): Promise<PlaythroughWithGame[]> {
  const data = await fetchJSON<{ playthroughs: PlaythroughWithGame[] }>(
    `/users/${encodeURIComponent(username)}/playthroughs`
  );
  return data.playthroughs;
}

export async function getPlaythrough(
  id: number
): Promise<{ playthrough: Playthrough; game: Game; quests: QuestWithStatus[] }> {
  return fetchJSON(`/playthroughs/${id}`);
}

export async function getQuestDetail(
  playthroughId: number,
  questId: number
): Promise<QuestDetail> {
  const data = await fetchJSON<{ quest: QuestDetail }>(
    `/playthroughs/${playthroughId}/quests/${questId}`
  );
  return data.quest;
}
