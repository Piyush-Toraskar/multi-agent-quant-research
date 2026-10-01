"""Content-addressed JSON snapshots. The identifier covers the entire stored payload."""
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any
import numpy as np


def sanitise(value: Any):
    if isinstance(value, dict):
        return {str(k): sanitise(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitise(v) for v in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def canonical(value):
    return json.dumps(sanitise(value), sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def save_blob(directory: Path, payload: dict) -> str:
    directory.mkdir(parents=True, exist_ok=True)
    content = canonical(payload)
    identifier = hashlib.sha256(content).hexdigest()
    target = directory / (identifier + '.json')
    if not target.exists():
        fd, temporary = tempfile.mkstemp(dir=directory, prefix='.tmp-')
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(content)
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return identifier


def load_blob(directory: Path, identifier: str) -> dict:
    if not re.fullmatch(r'[a-f0-9]{64}', identifier):
        raise ValueError('Invalid artifact identifier')
    path = directory / (identifier + '.json')
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != identifier:
        raise ValueError('Snapshot integrity check failed')
    return json.loads(content)
