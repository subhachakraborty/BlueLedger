-- Add up migration script here

CREATE TABLE IF NOT EXISTS users(
    id                      uuid PRIMARY KEY,
    fullname                TEXT NOT NULL,
    username                TEXT NOT NULL UNIQUE,
    password_hash           TEXT NOT NULL,
    wallet_address          TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(username);

CREATE TABLE IF NOT EXISTS plots (
    id                      uuid PRIMARY KEY,
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    geojson                 JSONB NOT NULL,
    area_sqm                FLOAT NOT NULL,
    location_name           TEXT,
    status                  TEXT NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active', 'disputed', 'deregistered')),
    register_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_plot_user_id ON plots(user_id);

CREATE TABLE IF NOT EXISTS claims(
    id                      UUID PRIMARY KEY,
    plot_id                 UUID NOT NULL REFERENCES plots(id) ON DELETE CASCADE,
    user_id                 UUID NOT NULL REFERENCES users(id),
    doc_hash                TEXT,
    doc_url                 TEXT,
    status                  TEXT NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'approved', 'rejected', 'disputed')),
    submitted_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at             TIMESTAMPTZ
);

CREATE INDEX idx_claims_plot_id ON claims(plot_id);
CREATE INDEX idx_claims_user_id ON claims(user_id);
CREATE INDEX idx_claims_status ON claims(status);

CREATE TABLE IF NOT EXISTS analysis_results (
    id                      UUID PRIMARY KEY,
    claim_id                UUID NOT NULL REFERENCES claims(id),
    ndvi_before             FLOAT,
    ndvi_after              FLOAT,
    ndvi_delta              FLOAT,
    ndwi_before             FLOAT,
    ndwi_after              FLOAT,
    carbon_kg               FLOAT,
    confidence_score        FLOAT,
    reject_reason           TEXT,
    raw_metadata            JSONB,
    analyzed_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS token_grants (
    id                      UUID PRIMARY KEY,
    claims_id               UUID NOT NULL UNIQUE REFERENCES claims(id),
    user_id                 UUID NOT NULL REFERENCES users(id),
    solana_mint_tx          TEXT,
    total_tokens            INTEGER NOT NULL,
    token_released          INTEGER NOT NULL DEFAULT 0,
    current_epoch           INTEGER NOT NULL DEFAULT 0,
    total_epochs            INTEGER NOT NULL DEFAULT 12,
    vesting_start           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_release_at         TIMESTAMPTZ
);

CREATE INDEX idx_token_grants_user_id ON token_grants(user_id);
