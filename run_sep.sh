#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
CONTAINER_ENV=sep bash bin/start_server.sh
