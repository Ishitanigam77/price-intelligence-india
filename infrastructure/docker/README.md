# docker/

Dockerfiles and compose configuration for containerizing the frontend, backend, workers, and ML
services. Introduced per-service as each service is actually built, not speculatively.

**Status**: `docker-compose.yml` implemented as part of the backend's FastAPI application
foundation — a **local development** stack (backend + PostgreSQL + Redis, with a persistent
PostgreSQL volume and service health checks). The backend's own `Dockerfile` lives at
`../../backend/Dockerfile` (colocated with the service it builds), with
`docker-compose.yml`'s `build.context` pointing at it. No frontend/worker/ML Dockerfiles and no
production Azure/Kubernetes deployment exist yet — see `../../ROADMAP.md`.

```bash
cp ../../.env.example ../../.env   # then edit with your own local values
docker compose -f docker-compose.yml up --build
```
