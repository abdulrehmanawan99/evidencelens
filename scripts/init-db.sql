-- Known development-only credentials. Published port is loopback-only.
CREATE ROLE evidencelens LOGIN PASSWORD 'evidencelens_local';
CREATE DATABASE evidencelens OWNER evidencelens;
CREATE DATABASE evidencelens_test_local OWNER evidencelens;
\connect evidencelens
CREATE EXTENSION IF NOT EXISTS vector;
\connect evidencelens_test_local
CREATE EXTENSION IF NOT EXISTS vector;
