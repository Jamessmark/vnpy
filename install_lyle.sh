#!/bin/bash
cd /Users/lishengkun/MyDocuments/Duke/stock/vnpy

# 1. 重建 .venv
~/.local/bin/uv venv .venv --python 3.10 --seed --allow-existing

# 2. 从缓存装 vnpy_ctp（无需编译）
ARCHIVE="$HOME/.cache/uv/archive-v0/5CaaYgWzuNQLcW1lHhTlb"
SITE=".venv/lib/python3.10/site-packages"
[ -d "$ARCHIVE/vnpy_ctp" ] && cp -r "$ARCHIVE/vnpy_ctp" "$SITE/" && \
    cp -r "$ARCHIVE/vnpy_ctp-6.6.9.1.dist-info" "$SITE/" && echo "vnpy_ctp: OK"

# 3. 装其余插件
.venv/bin/pip install vnpy_datarecorder vnpy_sqlite vnpy_spreadtrading \
    --index-url https://pypi.vnpy.com

# 4. 验证
.venv/bin/python -c "
import vnpy_ctp, vnpy, vnpy_datarecorder, vnpy_sqlite, vnpy_spreadtrading
print('所有依赖验证通过')
"