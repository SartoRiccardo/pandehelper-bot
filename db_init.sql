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

ALTER TABLE claims ADD CONSTRAINT fk_teams_1
    FOREIGN KEY (channel) REFERENCES teams(channel) ON DELETE CASCADE;