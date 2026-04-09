#!/usr/bin/env bash
# 一键本地预览（默认 SQLite；媒体走本机 media/，勿在 .env 里开 USE_OSS_MEDIA 除非真要连 OSS）
set -e
cd "$(dirname "$0")/../"

if [ "${CONTAINER_ENV}" = "sep" ];then
    cp config/env.sep .env
elif [ "${CONTAINER_ENV}" = "production" ];then
    cp config/env.prod .env
else
    echo ">>> env config: exit 1"
    exit 1
fi


#
/data/conda/envs/py312/bin/python3 manage.py migrate --noinput

echo ""
echo ">>> start Server:"
echo ""
/data/conda/envs/py312/bin/python3 manage.py runserver 0.0.0.0:8000
