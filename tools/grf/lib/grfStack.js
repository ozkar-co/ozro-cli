import { openSync, existsSync } from 'fs';
import { join } from 'path';
import { GrfNode } from '@chicowall/grf-loader';
import { GrfNative, detectGrfMagic } from './grfNative.js';
import { parseDataIni } from './dataIni.js';
import { normalizeGrfPath } from './paths.js';

const GRF_OPTIONS = { filenameEncoding: 'auto' };

function normKey(p) {
  return p.toLowerCase().replace(/\//g, '\\');
}

export class GrfStack {
  #clientPath;
  #grfFiles;
  #grfs = [];
  #loaded = false;

  constructor(clientPath, grfFiles) {
    this.#clientPath = clientPath;
    this.#grfFiles = grfFiles;
  }

  static async open(clientPath, dataIni = 'data.ini') {
    const grfFiles = parseDataIni(clientPath, dataIni);
    const stack = new GrfStack(clientPath, grfFiles);
    await stack.load();
    return stack;
  }

  async load() {
    if (this.#loaded) return;
    for (const file of this.#grfFiles) {
      const fullPath = join(this.#clientPath, file);
      if (!existsSync(fullPath)) {
        console.warn(`GRF not found, skipping: ${file}`);
        continue;
      }
      try {
        const magic = detectGrfMagic(fullPath);
        if (magic === 'Event Horizon') {
          const grf = GrfNative.open(fullPath);
          this.#grfs.push({ name: file, grf, type: 'native' });
        } else {
          const fd = openSync(fullPath, 'r');
          const grf = new GrfNode(fd, GRF_OPTIONS);
          await grf.load();
          this.#grfs.push({ name: file, grf, type: 'node', fd });
        }
        console.error(`Loaded ${file} (${magic || 'Master of Magic'})`);
      } catch (e) {
        console.warn(`Failed to load ${file}: ${e.message}`);
      }
    }
    this.#loaded = true;
  }

  get grfNames() {
    return this.#grfs.map((g) => g.name);
  }

  resolve(path) {
    const query = normalizeGrfPath(path);
    for (const { name, grf } of this.#grfs) {
      const result = grf.resolvePath(query);
      if (result.status === 'found' && result.matchedPath) {
        const entry = grf.getEntry(result.matchedPath);
        return {
          found: true,
          path: result.matchedPath,
          grf: name,
          size: entry?.realSize ?? 0,
          compressedSize: entry?.compressedSize ?? 0
        };
      }
    }
    return { found: false, path: query };
  }

  async getFile(path) {
    const query = normalizeGrfPath(path);
    for (const { name, grf } of this.#grfs) {
      const result = grf.resolvePath(query);
      if (result.status === 'found' && result.matchedPath) {
        const { data, error } = await grf.getFile(result.matchedPath);
        if (error) return { data: null, error, grf: name };
        return { data, grf: name, path: result.matchedPath };
      }
    }
    return { data: null, error: 'not_found' };
  }

  listFiles(filter) {
    const seen = new Map();
    for (const { name, grf } of this.#grfs) {
      const files = filter
        ? grf.find({ contains: filter.replace(/\//g, '\\') })
        : grf.listFiles();
      for (const f of files) {
        const key = normKey(f);
        if (!seen.has(key)) {
          seen.set(key, { path: f, grf: name });
        }
      }
    }
    return [...seen.values()].sort((a, b) => a.path.localeCompare(b.path));
  }

  findPattern(pattern) {
    const regex = new RegExp(
      '^' + normalizeGrfPath(pattern).replace(/[.+^${}()|[\]\\]/g, '\\$&')
        .replace(/\*/g, '.*')
        .replace(/\?/g, '.') + '$',
      'i'
    );
    return this.listFiles().filter((e) => regex.test(e.path));
  }
}
