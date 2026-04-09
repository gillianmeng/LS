#!/usr/bin/env bash
# 一键本地预览（默认 SQLite；媒体走本机 media/，勿在 .env 里开 USE_OSS_MEDIA 除非真要连 OSS）
set -e
cd "$(dirname "$0")"

/data/conda/envs/py312/bin/python3 manage.py migrate --noinput

echo ""
echo ">>> start Server:"
echo ""
/data/conda/envs/py312/bin/python3 manage.py runserver
