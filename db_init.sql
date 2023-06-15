CREATE TABLE IF NOT EXISTS claims (
    userid BIGINT NOT NULL,
    tile VARCHAR(3) NOT NULL,
    channel BIGINT NOT NULL,
    message BIGINT NOT NULL,
    claimed_at TIMESTAMP NOT NULL,
    PRIMARY KEY (message)
);

CREATE TABLE IF NOT EXISTS teams (
    channel BIGINT NOT NULL,
    PRIMARY KEY(channel)
);

CREATE TABLE IF NOT EXISTS lbchannels (
    guild BIGINT NOT NULL,
    channel BIGINT NOT NULL,
    PRIMARY KEY(guild, channel)
);

CREATE TABLE IF NOT EXISTS btd6players (
    userid BIGINT NOT NULL,
    oak VARCHAR(40) NOT NULL,
    is_main BOOLEAN DEFAULT FALSE,
    PRIMARY KEY(userid, oak)
);

CREATE TABLE IF NOT EXISTS planners (
    planner_channel BIGINT NOT NULL,
    claims_channel BIGINT,
    ping_role BIGINT,
    ping_channel BIGINT,
    clear_time TIMESTAMP,
    is_active BOOL DEFAULT TRUE,
    PRIMARY KEY(planner_channel)
);

-- Reserve a tile to claim for the Planner
CREATE TABLE IF NOT EXISTS plannertileclaims (
    user_id BIGINT NOT NULL,
    planner_channel BIGINT NOT NULL,
    tile VARCHAR(3),
    PRIMARY KEY(user_id, planner_channel, tile)
);

ALTER TABLE claims ADD CONSTRAINT fk_teams_1
    FOREIGN KEY (channel) REFERENCES teams(channel) ON DELETE CASCADE;

ALTER TABLE planners ADD CONSTRAINT fk_teams_1
    FOREIGN KEY (claims_channel) REFERENCES teams(channel) ON DELETE NO ACTION;

ALTER TABLE plannertileclaims ADD CONSTRAINT fk_planners_1
    FOREIGN KEY (planner_channel) REFERENCES planners(planner_channel) ON DELETE CASCADE;