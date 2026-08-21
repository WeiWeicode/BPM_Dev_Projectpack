# -*- coding: utf-8 -*-
"""把 OpenAPI schema 匯出成 openapi.json，供前端產生 TypeScript 型別。

    python dump_openapi.py
    cd ../frontend && npm run gen:types

資料契約只有一份（app/models.py），前端型別由這裡產生，不手抄。
"""

import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app  # noqa: E402

OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'openapi.json')


def main():
    schema = app.openapi()
    with io.open(OUT_PATH, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(json.dumps(schema, ensure_ascii=False, indent=2))
    print('已寫入 %s（%d 個路徑）' % (OUT_PATH, len(schema.get('paths', {}))))


if __name__ == '__main__':
    main()
