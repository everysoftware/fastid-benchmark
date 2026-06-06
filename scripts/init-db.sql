-- authentik
SELECT 'CREATE DATABASE authentik'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'authentik')\gexec
GRANT ALL PRIVILEGES ON DATABASE authentik TO postgres;

-- keycloak
SELECT 'CREATE DATABASE keycloak'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'keycloak')\gexec
GRANT ALL PRIVILEGES ON DATABASE keycloak TO postgres;

-- fastid
SELECT 'CREATE DATABASE fastid'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'fastid')\gexec
GRANT ALL PRIVILEGES ON DATABASE fastid TO postgres;
