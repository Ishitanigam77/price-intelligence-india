# docker/

Dockerfiles live next to the services they build (`backend/Dockerfile`, `frontend/Dockerfile`, `ml/Dockerfile`). This directory holds the **local development** Compose file.

```bash
cp ../../.env.example ../../.env   # then edit; never commit
docker compose -f docker-compose.yml up --build
```

| Service | Image |
|---|---|
| postgres | `postgres:16-alpine` |
| redis | `redis:7-alpine` |
| backend | `backend/Dockerfile` `--target api` |
| worker | `backend/Dockerfile` `--target worker` (`RUN_DB_MIGRATIONS=false`) |
| frontend | `frontend/Dockerfile` |
| ml | `ml/Dockerfile` (liveness on port 8080; override command to train) |

Production hosting is Azure Container Apps (`../terraform/`), not this Compose file.
