#!/usr/bin/env python3
"""Compare `spec/inventory.json` with a saved copy of the upstream OpenAPI document.

    curl -H 'User-Agent: (example.com, you@example.com)' https://api.weather.gov/openapi.json -o openapi.json
    python3 scripts/check_inventory.py openapi.json

The upstream set is every method/path pair under `paths`, whatever the method. The script
prints `inventory matches upstream` and exits 0 only when the inventory lists exactly that
set, each pair once; otherwise it names every missing, extra and duplicated pair and exits 1.
It reads only the two files, never the network.
"""

import json
import sys
from collections import Counter
from pathlib import Path

INVENTORY = Path(__file__).resolve().parents[1] / 'spec' / 'inventory.json'
METHODS = ('get', 'put', 'post', 'delete', 'options', 'head', 'patch', 'trace')


def _no_duplicate_keys(pairs):
  keys = Counter(key for key, _ in pairs)
  repeated = sorted(key for key, count in keys.items() if count > 1)
  if repeated:
    raise ValueError(f'duplicate keys: {", ".join(repeated)}')
  return dict(pairs)


def upstream_operations(openapi_path):
  document = json.loads(Path(openapi_path).read_text(), object_pairs_hook=_no_duplicate_keys)
  return Counter(
    (method.upper(), path)
    for path, item in document['paths'].items()
    for method in item
    if method in METHODS
  )


def inventory_operations(inventory_path):
  document = json.loads(Path(inventory_path).read_text())
  return Counter((entry['method'].upper(), entry['path']) for entry in document['endpoints'])


def main(argv):
  if len(argv) != 2:
    print(f'usage: {argv[0]} <saved-openapi.json>', file=sys.stderr)
    return 2
  upstream = upstream_operations(argv[1])
  listed = inventory_operations(INVENTORY)
  problems = [
    *(f'missing from inventory: {m} {p}' for m, p in sorted(upstream.keys() - listed.keys())),
    *(f'not upstream: {m} {p}' for m, p in sorted(listed.keys() - upstream.keys())),
    *(f'listed {n} times: {m} {p}' for (m, p), n in sorted(listed.items()) if n > 1),
  ]
  print(f'upstream: {sum(upstream.values())} operations; inventory: {sum(listed.values())} entries')
  if problems:
    print('\n'.join(problems))
    return 1
  print('inventory matches upstream')
  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv))
