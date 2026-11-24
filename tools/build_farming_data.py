#!/usr/bin/env python3
import argparse
import json
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

import yaml

MAX_LEVEL = 275


def effective_rates(breakpoints):
    rates = [None] * (MAX_LEVEL * 2 - 1)
    for difference, rate in breakpoints.items():
        rates[difference + MAX_LEVEL - 1] = rate

    last_rate = 100
    for index in range(MAX_LEVEL - 1, len(rates)):
        if rates[index] is None:
            rates[index] = last_rate
        else:
            last_rate = rates[index]

    last_rate = 100
    for index in range(MAX_LEVEL - 1, -1, -1):
        if rates[index] is None:
            rates[index] = last_rate
        else:
            last_rate = rates[index]

    return rates


def build_level_penalty(rathena_dir, site_dir):
    breakpoints = defaultdict(dict)
    sources = [
        rathena_dir / 'db/re/level_penalty.yml',
        rathena_dir / 'db/import/level_penalty.yml',
    ]

    for source in sources:
        document = yaml.safe_load(source.read_text())
        for entry in document.get('Body') or []:
            penalty_type = entry['Type']
            for level in entry.get('LevelDifferences') or []:
                breakpoints[penalty_type][int(level['Difference'])] = int(level['Rate'])

    data = {
        'schemaVersion': 1,
        'generatedAt': datetime.now(timezone.utc).isoformat(),
        'source': [f'{rathena_dir.name}/{source.relative_to(rathena_dir)}' for source in sources],
        'maxLevel': MAX_LEVEL,
        'minDiff': -MAX_LEVEL,
        'maxDiff': MAX_LEVEL,
        'penalties': {
            'exp': {'rates': effective_rates(breakpoints.get('Exp', {}))},
            'drop': {'rates': effective_rates(breakpoints.get('Drop', {}))},
        },
    }

    out = site_dir / 'assets/farming/levelPenalty.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, separators=(',', ':')) + '\n')
    return out


def build_world_access(site_dir):
    routes = json.loads((site_dir / 'assets/world/routes.json').read_text())['routes']
    worldview = json.loads((site_dir / 'assets/world/worldview.json').read_text())
    spawn_maps = json.loads((site_dir / 'assets/spawns/maps.json').read_text())['maps']

    hubs = sorted({route['from'] for route in routes if route['kind'] == 'kafra'})
    adjacency = defaultdict(list)
    nodes = set()

    for route in routes:
        nodes.add(route['from'])
        nodes.add(route['to'])
        adjacency[route['from']].append(route)

    for world in worldview['worlds']:
        for map_entry in world.get('maps', []):
            nodes.add(map_entry['map'])

    for map_entry in spawn_maps:
        nodes.add(map_entry['map'])

    depth = {hub: 0 for hub in hubs}
    path = {hub: [] for hub in hubs}
    queue = deque(hubs)

    while queue:
        current = queue.popleft()
        for route in adjacency.get(current, []):
            target = route['to']
            if target in depth:
                continue
            depth[target] = depth[current] + 1
            path[target] = path[current] + [route]
            queue.append(target)

    def label(distance):
        if distance is None:
            return 'NPC/Quest'
        if distance == 0:
            return 'Hub'
        if distance == 1:
            return 'Acceso directo'
        if distance == 2:
            return '2 saltos'
        if distance == 3:
            return '3 saltos'
        return '4+ saltos'

    maps = {}
    for map_name in sorted(nodes):
        distance = depth.get(map_name)
        maps[map_name] = {
            'depth': distance,
            'label': label(distance),
            'path': [
                {
                    'kind': step['kind'],
                    'from': step['from'],
                    'to': step['to'],
                    'name': step.get('name', ''),
                }
                for step in path.get(map_name, [])
            ],
        }

    data = {
        'schemaVersion': 1,
        'generatedAt': datetime.now(timezone.utc).isoformat(),
        'source': [
            'ozro-site/assets/world/routes.json',
            'ozro-site/assets/world/worldview.json',
            'ozro-site/assets/spawns/maps.json',
        ],
        'hubs': hubs,
        'maps': maps,
        'counts': {
            'maps': len(maps),
            'hubs': len(hubs),
            'reachable': sum(1 for entry in maps.values() if entry['depth'] is not None),
            'unknown': sum(1 for entry in maps.values() if entry['depth'] is None),
        },
    }

    out = site_dir / 'assets/world/access.json'
    out.write_text(json.dumps(data, separators=(',', ':')) + '\n')
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rathena', default='../rathena')
    args = parser.parse_args()

    cli_root = Path(__file__).resolve().parents[1]
    site_dir = (cli_root.parent / "ozro-site").resolve()
    rathena_dir = Path(args.rathena).resolve()

    penalty = build_level_penalty(rathena_dir, site_dir)
    access = build_world_access(site_dir)
    print(f'Escrito {penalty}')
    print(f'Escrito {access}')


if __name__ == '__main__':
    main()
