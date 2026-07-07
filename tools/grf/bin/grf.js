#!/usr/bin/env node
import { Command } from 'commander';
import { mkdirSync, writeFileSync } from 'fs';
import { join, basename } from 'path';
import { loadConfig } from '../lib/config.js';
import { GrfStack } from '../lib/grfStack.js';
import { buildAssets } from '../lib/buildAssets.js';
import { parseItemInfo } from '../lib/itemInfo.js';

let globalConfigPath;

const program = new Command();

program
  .name('grf')
  .description('OzRo GRF explorer and asset pipeline')
  .option('-c, --config <path>', 'Path to grf.config.json')
  .hook('preAction', (thisCommand) => {
    globalConfigPath = thisCommand.opts().config;
  });

async function getStack() {
  const config = loadConfig(globalConfigPath);
  const stack = await GrfStack.open(config.clientPath, config.dataIni);
  return { config, stack };
}

program
  .command('list')
  .description('List files in GRF stack')
  .option('-f, --filter <substring>', 'Filter paths containing substring')
  .option('--limit <n>', 'Max results', parseInt)
  .action(async (cmdOpts) => {
    const { stack } = await getStack();
    let files = stack.listFiles(cmdOpts.filter);
    if (cmdOpts.limit) files = files.slice(0, cmdOpts.limit);
    for (const { path, grf } of files) {
      console.log(`${grf}\t${path}`);
    }
    console.error(`\n${files.length} file(s)`);
  });

program
  .command('info <path>')
  .description('Show file metadata in GRF stack')
  .action(async (filePath) => {
    const { stack } = await getStack();
    const resolved = stack.resolve(filePath);
    if (resolved.found) {
      console.log(JSON.stringify(resolved, null, 2));
    } else {
      console.log(JSON.stringify({ found: false, path: filePath }));
      process.exitCode = 1;
    }
  });

program
  .command('extract <pattern>')
  .description('Extract file(s) matching pattern (* and ? supported)')
  .option('-o, --output <dir>', 'Output directory', '.')
  .action(async (pattern, cmdOpts) => {
    const { stack } = await getStack();
    const matches = stack.findPattern(pattern);
    if (!matches.length) {
      console.error(`No files match: ${pattern}`);
      process.exitCode = 1;
      return;
    }
    mkdirSync(cmdOpts.output, { recursive: true });
    for (const { path, grf } of matches) {
      const { data, error } = await stack.getFile(path);
      if (!data) {
        console.error(`Failed: ${path} (${error})`);
        continue;
      }
      const outName = basename(path);
      const outPath = join(cmdOpts.output, outName);
      writeFileSync(outPath, data);
      console.log(`${grf} → ${outPath}`);
    }
    console.error(`\nExtracted ${matches.length} file(s)`);
  });

program
  .command('items')
  .description('List parsed itemInfo entries')
  .option('--limit <n>', 'Max items', parseInt)
  .action(async (cmdOpts) => {
    const config = loadConfig(globalConfigPath);
    const items = parseItemInfo(join(config.clientPath, config.itemInfo));
    let entries = [...items.values()];
    if (cmdOpts.limit) entries = entries.slice(0, cmdOpts.limit);
    for (const item of entries) {
      console.log(`${item.id}\t${item.displayName}\t${item.resourceName}`);
    }
    console.error(`\n${entries.length} item(s)`);
  });

program
  .command('build-assets')
  .description('Build web asset atlases from GRF')
  .option('--icons-only', 'Skip mob sprites')
  .option('--limit <n>', 'Process only first N items/mobs', parseInt)
  .action(async (cmdOpts) => {
    const { config, stack } = await getStack();
    await buildAssets(stack, config, {
      iconsOnly: cmdOpts.iconsOnly,
      limit: cmdOpts.limit
    });
  });

program.parse();
