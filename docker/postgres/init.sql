CREATE SCHEMA IF NOT EXISTS desk;

CREATE TABLE desk.agent_heartbeat (
    agent_id text PRIMARY KEY,
    seen_at timestamptz NOT NULL DEFAULT now(),
    status text NOT NULL
);

CREATE TABLE desk.jobs (
    id text PRIMARY KEY,
    kind text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'queued',
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz,
    error text
);
