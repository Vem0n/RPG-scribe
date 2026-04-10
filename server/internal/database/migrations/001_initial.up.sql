CREATE TABLE users (
    id          SERIAL PRIMARY KEY,
    username    TEXT NOT NULL UNIQUE,
    password    TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE games (
    id          SERIAL PRIMARY KEY,
    slug        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE quests (
    id              SERIAL PRIMARY KEY,
    game_id         INT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    quest_key       TEXT NOT NULL,
    name            TEXT NOT NULL,
    description     TEXT,
    category        TEXT,
    sort_order      INT NOT NULL DEFAULT 0,
    guide_content   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (game_id, quest_key)
);

CREATE INDEX idx_quests_game_id ON quests(game_id);

CREATE TABLE quest_stages (
    id          SERIAL PRIMARY KEY,
    quest_id    INT NOT NULL REFERENCES quests(id) ON DELETE CASCADE,
    stage_key   TEXT NOT NULL,
    name        TEXT NOT NULL,
    sort_order  INT NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (quest_id, stage_key)
);

CREATE INDEX idx_quest_stages_quest_id ON quest_stages(quest_id);

CREATE TABLE playthroughs (
    id              SERIAL PRIMARY KEY,
    user_id         INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    game_id         INT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    external_id     TEXT,
    last_synced_at  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, game_id, external_id)
);

CREATE INDEX idx_playthroughs_user_game ON playthroughs(user_id, game_id);

CREATE TABLE playthrough_quests (
    id              SERIAL PRIMARY KEY,
    playthrough_id  INT NOT NULL REFERENCES playthroughs(id) ON DELETE CASCADE,
    quest_id        INT NOT NULL REFERENCES quests(id) ON DELETE CASCADE,
    status          TEXT NOT NULL DEFAULT 'unstarted'
                    CHECK (status IN ('unstarted', 'started', 'finished', 'failed')),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (playthrough_id, quest_id)
);

CREATE INDEX idx_pq_playthrough ON playthrough_quests(playthrough_id);

CREATE TABLE playthrough_stages (
    id              SERIAL PRIMARY KEY,
    playthrough_id  INT NOT NULL REFERENCES playthroughs(id) ON DELETE CASCADE,
    stage_id        INT NOT NULL REFERENCES quest_stages(id) ON DELETE CASCADE,
    completed       BOOLEAN NOT NULL DEFAULT false,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (playthrough_id, stage_id)
);

CREATE INDEX idx_ps_playthrough ON playthrough_stages(playthrough_id);
