import { readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { layout, parseFlow, render, STYLE } from '@linemap/core';

STYLE.linePitch = 17;

const here = dirname(fileURLToPath(import.meta.url));
const siteRoot = resolve(here, '../../ozro-site');
const dataPath = resolve(siteRoot, 'assets/world/transport.json');
const outputPath = resolve(siteRoot, 'assets/world/transport-map.svg');
const layoutPath = resolve(siteRoot, 'assets/world/transport-layout.json');
const VIEW_BOX = { x: 280, y: 20, width: 1060, height: 960 };

const positions = {
  einbroch: [360, 100],
  yuno: [550, 200],
  lighthalzen: [740, 100],
  hugel: [930, 100],
  rachel: [1120, 200],
  aldebaran: [360, 400],
  geffen: [636, 300],
  prontera: [749, 500],
  payon: [930, 500],
  cmd_fild07: [360, 800],
  izlude: [1120, 800],
  alberta: [930, 900],
  morocc: [550, 700],
  comodo: [550, 900],
  umbala: [360, 900],
};

const lines = [
  ['K', 'Kafra', '#2f7d5b'],
  ['KO', 'Kafra unidireccional', '#b3651f'],
  ['AD', 'Airship doméstico', '#2f6fae'],
  ['AI', 'Airship internacional', '#7b5fb0'],
];

function dotQuote(value) {
  return `"${String(value).replaceAll('\\', '\\\\').replaceAll('"', '\\"')}"`;
}

function buildDot(graph) {
  const out = ['digraph transport {'];

  out.push('  subgraph lines {');
  for (const [id, label, color] of lines) {
    out.push(`    ${id} [label=${dotQuote(label)}, color=${dotQuote(color)}]`);
  }
  out.push('  }');
  out.push('  node [width=0.75, height=0.75]');

  for (const node of graph.nodes) {
    const point = positions[node.id];
    if (!point) continue;
    out.push(
      `  ${node.id} [label="", pos=${dotQuote(`${point[0]},${point[1]}`)}]`,
    );
  }

  for (const line of graph.lines) {
    if (line.type === 'kafra' && line.from && line.to) {
      const id = line.bidirectional === false ? 'KO' : 'K';
      out.push(`  ${line.from} -> ${line.to} [lines=${id}]`);
      continue;
    }

    if (line.type === 'airship' && line.stops) {
      const id = line.group === 'airship-domestic' ? 'AD' : 'AI';
      const stops = line.stops.map((stop) => stop.station);
      for (let index = 0; index < stops.length - 1; index += 1) {
        const from = stops[index];
        const to = stops[index + 1];
        out.push(`  ${from} -> ${to} [lines=${id}]`);
      }
      if (line.loop && stops.length > 1) {
        out.push(`  ${stops[stops.length - 1]} -> ${stops[0]} [lines=${id}]`);
      }
    }
  }

  out.push('}');
  return out.join('\n');
}

const GRID_X = [360, 455, 550, 645, 740, 835, 930, 1025, 1120];
const GRID_Y = [100, 200, 300, 400, 500, 600, 700, 800, 900];
const GRID_COLS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I'];
const H_LANES = [1, 2, 1, 3, 3, 2, 3, 3, 1];
const V_LANES = [3, 1, 3, 3, 3, 2, 3, 2, 3];
const LANE_NAMES = ['u', 'v', 'w'];
const LANE_PITCH = 18;
const LANE_OFFSETS = { E: [-9, 9, 27], D: [-27, -9, 9] };

function laneOffsets(count, key) {
  if (key && LANE_OFFSETS[key]) return LANE_OFFSETS[key].slice(0, count);
  if (count === 1) return [0];
  if (count === 2) return [-LANE_PITCH / 2, LANE_PITCH / 2];
  return [-LANE_PITCH, 0, LANE_PITCH];
}

function vLaneX(column, lane) {
  const index = GRID_COLS.indexOf(column);
  const offsets = laneOffsets(V_LANES[index], column);
  return GRID_X[index] + offsets[LANE_NAMES.indexOf(lane)];
}

function hLaneY(row, lane) {
  const index = row - 1;
  const offsets = laneOffsets(H_LANES[index]);
  return GRID_Y[index] + offsets[LANE_NAMES.indexOf(lane)];
}

function roundedPath(points, radius = 12) {
  const parts = [`M ${points[0][0]} ${points[0][1]}`];
  for (let index = 1; index < points.length - 1; index += 1) {
    const [px, py] = points[index - 1];
    const [cx, cy] = points[index];
    const [nx, ny] = points[index + 1];
    const inLength = Math.hypot(cx - px, cy - py) || 1;
    const outLength = Math.hypot(nx - cx, ny - cy) || 1;
    const r = Math.min(radius, inLength / 2, outLength / 2);
    const inX = cx - ((cx - px) / inLength) * r;
    const inY = cy - ((cy - py) / inLength) * r;
    const outX = cx + ((nx - cx) / outLength) * r;
    const outY = cy + ((ny - cy) / outLength) * r;
    parts.push(`L ${inX} ${inY}`);
    parts.push(`Q ${cx} ${cy} ${outX} ${outY}`);
  }
  const [lastX, lastY] = points[points.length - 1];
  parts.push(`L ${lastX} ${lastY}`);
  return parts.join(' ');
}

const AIRSHIP_ROUTES = [
  {
    id: 'AD',
    color: '#2f6fae',
    label: 'Airship doméstico',
    paths: [
      [[360, 100], [740, 100]],
      [[360, 100], [vLaneX('A', 'v'), hLaneY(2, 'u')], [550, hLaneY(2, 'u')], [550, 200]],
      [[550, 200], [550, hLaneY(2, 'u')], [vLaneX('G', 'v'), hLaneY(2, 'u')], [vLaneX('G', 'v'), 100], [930, 100]],
    ],
  },
  {
    id: 'AI',
    color: '#7b5fb0',
    label: 'Airship internacional',
    paths: [
      [[550, 200], [550, hLaneY(2, 'v')], [1120, hLaneY(2, 'v')], [1120, 200]],
      [[1120, 200], [vLaneX('I', 'w'), 200], [vLaneX('I', 'w'), 800], [1120, 800]],
    ],
  },
];

function airshipSvg() {
  return AIRSHIP_ROUTES.map((line) => {
    const pieces = line.paths.flatMap((points) => {
      const d = roundedPath(points);
      return [
        `<path d="${d}" class="lm-casing" stroke-width="14"/>`,
        `<path d="${d}" class="lm-strand" stroke="${line.color}" stroke-width="9" data-line="${line.id}"><title>${line.label}</title></path>`,
      ];
    }).join('');
    return `<g class="edge custom-airship" data-lines="${line.id}">${pieces}</g>`;
  }).join('\n');
}

const KAFRA_ROUTES = [
  { from: 'aldebaran', to: 'geffen', paths: [[[360, 400], [360, hLaneY(4, 'u')], [vLaneX('D', 'u'), hLaneY(4, 'u')], [vLaneX('D', 'u'), 300], [636, 300]]] },
  {
    from: 'aldebaran',
    to: 'yuno',
    paths: [[[360, 400], [360, hLaneY(2, 'v')], [550, hLaneY(2, 'v')], [550, 200]]],
  },
  {
    from: 'aldebaran',
    to: 'izlude',
    paths: [[[360, 400], [vLaneX('I', 'u'), hLaneY(4, 'v')], [vLaneX('I', 'u'), 800], [1120, 800]]],
  },
  {
    from: 'morocc',
    to: 'prontera',
    paths: [[[550, 700], [550, hLaneY(7, 'u')], [vLaneX('E', 'u'), hLaneY(7, 'u')], [vLaneX('E', 'u'), 500], [749, 500]]],
  },
  {
    from: 'morocc',
    to: 'comodo',
    paths: [[[550, 700], [550, 900]]],
  },
  { from: 'morocc', to: 'cmd_fild07', paths: [[[360, 800], [360, hLaneY(8, 'u')], [vLaneX('C', 'u'), hLaneY(8, 'u')], [vLaneX('C', 'u'), 700], [550, 700]]] },
  { from: 'cmd_fild07', to: 'comodo', paths: [[[360, 800], [360, hLaneY(8, 'v')], [vLaneX('C', 'u'), hLaneY(8, 'v')], [vLaneX('C', 'u'), 900], [550, 900]]] },
  { from: 'comodo', to: 'umbala', paths: [[[550, 900], [360, 900]]] },
  {
    from: 'morocc',
    to: 'payon',
    paths: [[[550, 700], [550, hLaneY(7, 'v')], [vLaneX('G', 'u'), hLaneY(7, 'v')], [vLaneX('G', 'u'), 500], [930, 500]]],
  },
  {
    from: 'morocc',
    to: 'alberta',
    paths: [[[550, 700], [550, hLaneY(7, 'w')], [vLaneX('G', 'u'), hLaneY(7, 'w')], [vLaneX('G', 'u'), 900], [930, 900]]],
  },
  {
    from: 'morocc',
    to: 'izlude',
    line: 'KO',
    paths: [[[550, 700], [vLaneX('C', 'w'), 700], [vLaneX('C', 'w'), hLaneY(8, 'w')], [1120, hLaneY(8, 'w')], [1120, 800]]],
  },
  {
    from: 'geffen',
    to: 'prontera',
    paths: [[[636, 300], [vLaneX('D', 'v'), 300], [vLaneX('D', 'v'), hLaneY(5, 'u')], [749, hLaneY(5, 'u')], [749, 500]]],
  },
  {
    from: 'payon',
    to: 'izlude',
    line: 'KO',
    paths: [[[930, 500], [vLaneX('G', 'w'), 500], [vLaneX('G', 'w'), hLaneY(8, 'u')], [1120, hLaneY(8, 'u')], [1120, 800]]],
  },
  {
    from: 'geffen',
    to: 'izlude',
    line: 'KO',
    paths: [[[636, 300], [vLaneX('D', 'w'), 300], [vLaneX('D', 'w'), hLaneY(4, 'u')], [vLaneX('I', 'v'), hLaneY(4, 'u')], [vLaneX('I', 'v'), 800], [1120, 800]]],
  },
  {
    from: 'payon',
    to: 'alberta',
    paths: [[[930, 500], [930, 900]]],
  },
  {
    from: 'prontera',
    to: 'alberta',
    paths: [[[749, 500], [vLaneX('E', 'v'), 500], [vLaneX('E', 'v'), hLaneY(9, 'u')], [930, hLaneY(9, 'u')], [930, 900]]],
  },
  {
    from: 'prontera',
    to: 'payon',
    paths: [[[749, 500], [930, 500]]],
  },
  {
    from: 'prontera',
    to: 'izlude',
    line: 'KO',
    paths: [[[749, 500], [vLaneX('E', 'w'), 500], [vLaneX('E', 'w'), hLaneY(8, 'v')], [1120, hLaneY(8, 'v')], [1120, 800]]],
  },
];

const CUSTOM_KAFRA_PAIRS = new Set(
  KAFRA_ROUTES.map((route) => [route.from, route.to].sort().join('|')),
);

function pointAt(points, distance) {
  let remaining = distance;
  for (let index = 1; index < points.length; index += 1) {
    const [x1, y1] = points[index - 1];
    const [x2, y2] = points[index];
    const dx = x2 - x1;
    const dy = y2 - y1;
    const length = Math.hypot(dx, dy);
    if (remaining <= length || index === points.length - 1) {
      const ratio = length === 0 ? 0 : Math.min(1, Math.max(0, remaining / length));
      return {
        x: x1 + dx * ratio,
        y: y1 + dy * ratio,
        ux: dx / (length || 1),
        uy: dy / (length || 1),
      };
    }
    remaining -= length;
  }
  const [x, y] = points[points.length - 1];
  return { x, y, ux: 1, uy: 0 };
}

function triangleAt(points, distance, size = 8) {
  const { x, y, ux, uy } = pointAt(points, distance);
  const px = -uy;
  const py = ux;
  const tipX = x + ux * size;
  const tipY = y + uy * size;
  const baseX = x - ux * size * 0.6;
  const baseY = y - uy * size * 0.6;
  const width = size * 0.6;
  return `<polygon points="${tipX},${tipY} ${baseX + px * width},${baseY + py * width} ${baseX - px * width},${baseY - py * width}" fill="#2f7d5b" stroke="#ffffff" stroke-width="1.5" stroke-linejoin="round"/>`;
}

function trianglesAlong(points, spacing = 58, size = 8) {
  let total = 0;
  for (let index = 1; index < points.length; index += 1) {
    total += Math.hypot(
      points[index][0] - points[index - 1][0],
      points[index][1] - points[index - 1][1],
    );
  }
  const margin = 40;
  if (total <= margin * 2) return triangleAt(points, total / 2, size);
  const triangles = [];
  for (let distance = margin; distance <= total - margin; distance += spacing) {
    triangles.push(triangleAt(points, distance, size));
  }
  return triangles.join('');
}

function kafraSvg() {
  return ['K', 'KO']
    .map((line) => {
      const routes = KAFRA_ROUTES.filter((route) => (route.line ?? 'K') === line);
      if (routes.length === 0) return '';
      const pieces = routes.flatMap((route) =>
        route.paths.flatMap((points) => {
          const d = roundedPath(points);
          return [
            `<path d="${d}" class="lm-casing" stroke-width="14"/>`,
            `<path d="${d}" class="lm-strand" stroke="#2f7d5b" stroke-width="9" data-line="${line}"><title>Kafra</title></path>`,
          ].filter(Boolean);
        }),
      ).join('');
      return `<g class="edge custom-kafra" data-lines="${line}">${pieces}</g>`;
    })
    .join('\n');
}

function kafraArrowsSvg() {
  const arrows = KAFRA_ROUTES.filter((route) => route.line === 'KO')
    .flatMap((route) => route.paths.map((points) => trianglesAlong(points)))
    .join('');
  return `<g class="transport-arrows" pointer-events="none">${arrows}</g>`;
}

function escapeXml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}

function removeLegend(svg) {
  const start = svg.indexOf('<g class="legend">');
  if (start === -1) return svg;
  let depth = 0;
  let index = start;
  while (index < svg.length) {
    const open = svg.indexOf('<g', index);
    const close = svg.indexOf('</g>', index);
    if (close === -1) return svg;
    if (open !== -1 && open < close) {
      depth += 1;
      index = open + 2;
    } else {
      depth -= 1;
      index = close + 4;
      if (depth === 0) return `${svg.slice(0, start)}${svg.slice(index)}`;
    }
  }
  return svg;
}

function setViewBox(svg) {
  return svg.replace(/<svg([^>]*)>/, (match, attrs) => {
    const updated = attrs
      .replace(
        /viewBox="[^"]*"/,
        `viewBox="${VIEW_BOX.x} ${VIEW_BOX.y} ${VIEW_BOX.width} ${VIEW_BOX.height}"`,
      )
      .replace(/width="[^"]*"/, `width="${VIEW_BOX.width}"`)
      .replace(/height="[^"]*"/, `height="${VIEW_BOX.height}"`);
    return `<svg${updated}>`;
  });
}

function nodeNamesSvg(graph) {
  const labels = graph.nodes
    .map((node) => {
      const point = positions[node.id];
      if (!point) return '';
      const x = point[0] + (node.id === 'alberta' ? 44 : 24);
      const y = point[1] - 14;
      return `<text x="${x}" y="${y}" text-anchor="start" transform="rotate(-32 ${x} ${y})">${escapeXml(node.name)}</text>`;
    })
    .join('');
  return `<g class="transport-names" pointer-events="none">${labels}</g>`;
}

function decorate(graph, svg) {
  let next = svg;

  next = next.replace(
    /<rect ([^>]*class="lm-shape"[^>]*)>/g,
    (match, attrs) => {
      const width = attrs.match(/width="([\d.]+)"/)?.[1];
      if (!width) return match;
      const round = attrs.replace(/rx="[^"]*"/, `rx="${Number(width) / 2}"`);
      return `<rect ${round}>`;
    },
  );

  next = next.replace(
    /(<g class="node" id="alberta"[^>]*>)([\s\S]*?)(<\/g>)/,
    (match, open, body, close) => {
      const updated = body.replace(
        /<rect ([^>]*class="lm-shape"[^>]*)>/,
        (rectMatch, attrs) => {
          const width = Number(attrs.match(/width="([\d.]+)"/)?.[1] ?? 54);
          const height = width * 1.9;
          const [cx, cy] = positions.alberta;
          return `<rect x="${cx - width / 2}" y="${cy - height / 2}" width="${width}" height="${height}" rx="${width / 2}" class="lm-shape"/>`;
        },
      );
      return `${open}${updated}${close}`;
    },
  );

  next = next.replace(/<rect[^>]*class="lm-bg"[^>]*\/>/, '');
  next = next.replace(/<g class="lm-marks"[^>]*>[\s\S]*?<\/g>/g, '');
  next = next.replace(/<g class="edge"[^>]*data-lines="(?:AD|AI)"[^>]*>[\s\S]*?<\/g>/g, '');
  next = next.replace(/<g class="edge"([^>]*)>[\s\S]*?<\/g>/g, (match, attrs) => {
    const from = attrs.match(/data-from="([^"]+)"/)?.[1];
    const to = attrs.match(/data-to="([^"]+)"/)?.[1];
    if (from && to && CUSTOM_KAFRA_PAIRS.has([from, to].sort().join('|'))) return '';
    return match;
  });

  const firstNode = next.indexOf('<g class="node"');
  if (firstNode >= 0) {
    next = `${next.slice(0, firstNode)}${kafraSvg()}\n${airshipSvg()}\n${kafraArrowsSvg()}\n${next.slice(firstNode)}`;
  }

  next = removeLegend(next);

  next = next.replace(
    '</svg>',
    `${nodeNamesSvg(graph)}
    <style>
      .node .lm-shape { fill: #ffffff; stroke: #374151; stroke-width: 2; }
      .node .lm-sheen { display: none; }
      .node .lm-label { font-weight: 700; }
      .transport-names text {
        fill: #1d2530;
        font-size: 12px;
        font-weight: 600;
        paint-order: stroke;
        stroke: #ffffff;
        stroke-width: 4;
        stroke-linejoin: round;
      }
    </style>
</svg>`,
  );

  return setViewBox(next);
}

const graph = JSON.parse(await readFile(dataPath, 'utf8'));
const dot = buildDot(graph);
const model = layout(parseFlow(dot));
const svg = decorate(graph, render(model, { theme: 'minimal' }));
await writeFile(outputPath, svg);

const nodeNames = new Map(graph.nodes.map((node) => [node.id, node.name]));
const normalKafra = new Map();

for (const route of KAFRA_ROUTES) {
  const fromName = nodeNames.get(route.from);
  const toName = nodeNames.get(route.to);
  if (!fromName || !toName) continue;

  const add = (id, name, map) => {
    if (!normalKafra.has(id)) normalKafra.set(id, []);
    const list = normalKafra.get(id);
    if (!list.some((destination) => destination.name === name && destination.map === map)) {
      list.push({ name, map });
    }
  };

  add(route.from, toName, route.to);
  if ((route.line ?? 'K') === 'K') add(route.to, fromName, route.from);
}

const transportLayout = {
  version: Date.now(),
  viewBox: VIEW_BOX,
  nodes: graph.nodes
    .map((node) => {
      const point = positions[node.id];
      if (!point) return null;
      const tooltips = (graph.tooltips[node.id] ?? [])
        .filter((group) => group.type !== 'kafra_tp' && group.label !== 'Doram Kafra')
        .map((group) => ({ ...group, destinations: [...group.destinations] }));
      const normal = normalKafra.get(node.id) ?? [];
      if (normal.length > 0) {
        const existing = tooltips.find((group) => group.type === 'kafra_fields');
        if (existing) {
          const seen = new Set(existing.destinations.map((destination) => `${destination.name}|${destination.map}`));
          for (const destination of normal) {
            if (!seen.has(`${destination.name}|${destination.map}`)) existing.destinations.push(destination);
          }
        } else {
          tooltips.unshift({ type: 'kafra_fields', label: 'Kafra', destinations: normal });
        }
      }
      return {
        id: node.id,
        name: node.name,
        region: node.region,
        x: point[0],
        y: point[1],
        tooltips,
      };
    })
    .filter(Boolean),
};
await writeFile(layoutPath, `${JSON.stringify(transportLayout, null, 2)}\n`);
console.log(`wrote ${outputPath}`);
