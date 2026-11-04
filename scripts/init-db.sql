-- Known development-only credentials. Published port is loopback-only.
CREATE ROLE evidencelens LOGIN PASSWORD 'evidencelens_local';
CREATE DATABASE evidencelens OWNER evidencelens;
CREATE DATABASE evidencelens_test_local OWNER evidencelens;
