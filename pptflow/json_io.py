from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def read_json(path: Path | str) -> Any:
    json_path = Path(path).expanduser()
    if not json_path.exists():
        raise FileNotFoundError(json_path)
    if json_path.is_dir():
        raise IsADirectoryError(json_path)
    with json_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def dump_json(data: Any, *, indent: int = 2, sort_keys: bool = False) -> str:
    return json.dumps(data, ensure_ascii=False, indent=indent, sort_keys=sort_keys)


def write_json(
    path: Path | str,
    data: Any,
    *,
    indent: int = 2,
    sort_keys: bool = False,
) -> Path:
    json_path = Path(path).expanduser()
    json_path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{json_path.name}.",
        suffix=".tmp",
        dir=str(json_path.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=indent, sort_keys=sort_keys)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, json_path)
        return json_path
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise

