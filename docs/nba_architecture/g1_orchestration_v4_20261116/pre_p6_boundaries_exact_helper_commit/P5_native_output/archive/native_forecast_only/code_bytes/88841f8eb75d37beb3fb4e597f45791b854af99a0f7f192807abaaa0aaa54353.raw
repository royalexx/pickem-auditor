"""Exact source loader for the separately versioned latest-owner consumer.

The registry binds executable bytes. It does not authenticate historical sources.
Real admission is deliberately absent; callers cannot provide another registry.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import types

from v2.nba_architecture.v2_contracts import req

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'research/nba_p4_latest/fixtures_v2'
REGISTRY = ROOT / 'research/nba_p4_latest/upstream_registry.json'


def raw_sha(raw):
    return hashlib.sha256(raw).hexdigest()


def registry():
    return json.loads(REGISTRY.read_bytes())


def prepare(destination=None):
    """Materialize exact Git bytes; an existing divergent file is an error."""
    target = Path(destination) if destination else ROOT / 'work/latest_upstream' / raw_sha(REGISTRY.read_bytes())[:16]
    for owner, pin in registry()['owners'].items():
        for path, expected in {**pin.get('inventory_files',{}),**pin['files']}.items():
            raw = subprocess.check_output(['git', 'show', f"{pin['commit']}:{path}"], cwd=ROOT)
            req(raw_sha(raw) == expected, 'J2_REGISTRY_GIT_BYTES_' + owner)
            dest = target / owner / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                req(dest.read_bytes() == raw, 'J2_EXISTING_SOURCE_DRIFT_' + owner)
            else:
                dest.write_bytes(raw)
    return target


def _module(name, path, expected):
    if name in sys.modules:
        module = sys.modules[name]
        req(raw_sha(Path(module.__file__).read_bytes()) == expected,
            'J2_LOADED_MODULE_DRIFT')
        return module
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[name]
        raise
    return module


def load_upstream(root):
    """Validate every dependency before loading either owner implementation."""
    pins = registry()['owners']
    for path, expected in {**registry()['inherited_g0_files'],
                           **registry()['reused_owner_files']}.items():
        current = ROOT / path
        req(current.is_file() and raw_sha(current.read_bytes()) == expected,
            'J2_INHERITED_G0_BYTES')
    for owner, pin in pins.items():
        for inventory in (pin['files'],pin.get('inventory_files',{})):
            for path, expected in inventory.items():
                source = Path(root) / owner / path
                req(source.is_file() and raw_sha(source.read_bytes()) == expected,
                    'J2_UPSTREAM_CODE_PIN_' + owner)
    key = raw_sha(REGISTRY.read_bytes())[:16]
    package = '_nba_p4_latest_' + key
    if package not in sys.modules:
        module = types.ModuleType(package)
        module.__path__ = [str(Path(root) / 'P2/v2/nba_s_family')]
        sys.modules[package] = module
    model_path = 'v2/nba_s_family/model.py'
    p2 = _module(package + '.model', Path(root) / 'P2' / model_path,
                 pins['P2']['files'][model_path])
    bridge = 'v2/nba_o_bridge.py'
    _module('v2.nba_o_bridge', Path(root) / 'P3' / bridge,
            pins['P3']['files'][bridge])
    p3path = 'v2/nba_o_family.py'
    p3 = _module('_nba_p4_latest_O_' + key, Path(root) / 'P3' / p3path,
                 pins['P3']['files'][p3path])
    return p2, p3
