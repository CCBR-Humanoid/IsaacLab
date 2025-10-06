#!/bin/sh
set -e
# start tailscaled + log in like the stock image does
/usr/local/bin/containerboot &
pid=$!
# ensure we tell control plane we're done
trap 'tailscale logout --force || true; kill -TERM "$pid"; wait "$pid"' INT TERM EXIT
wait "$pid"