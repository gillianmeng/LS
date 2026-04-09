#!/usr/bin/env bash
# 一键本地预览（默认 SQLite；媒体走本机 media/，勿在 .env 里开 USE_OSS_MEDIA 除非真要连 OSS）
set -e
cd "$(dirname "$0")"
if [[ ! -f venv/bin/activate ]]; then
  echo "首次请执行:"
  echo "  python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi
source venv/bin/activate
pip install -q -r requirements.txt
python manage.py migrate --noinput
echo ""
echo ">>> 浏览器打开: http://127.0.0.1:8000/"
echo ">>> Ctrl+C 停止"
echo ""
exec python manage.py runserver
