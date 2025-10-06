To start a session
```
export SESSION_ID=$(date +%Y%m%d-%H%M%S)-$RANDOM
export COMPOSE_PROJECT_NAME=tailscale-$SESSION_ID
docker compose \
    --env-file ./docker/.env.base \
    --env-file ./docker/.env.tailscale \
    --env-file ./docker/.env.webrtc \
    -f ./docker/docker-compose.yaml \
    -f ./docker/docker-compose-tailscale.yaml \
    --profile webrtc \
    up \
    --detach
```

To end a session
```
docker compose -p lab-$SESSION_ID down -v
```