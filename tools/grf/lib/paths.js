/** RO GRF paths use backslashes; normalize for comparison. */
export function normalizeGrfPath(p) {
  return p.replace(/\//g, '\\').replace(/^\\+/, '');
}

export function toGrfPath(p) {
  return normalizeGrfPath(p);
}

/** UI folder name in Korean (User Interface). */
export const UI_TEXTURE = 'data\\texture\\유저인터페이스';

export function itemIconPath(resourceName) {
  return `${UI_TEXTURE}\\item\\${resourceName}.bmp`;
}

export function itemIllustrationPath(resourceName) {
  return `${UI_TEXTURE}\\collection\\${resourceName}.bmp`;
}

export function mobSpritePath(aegisName) {
  const name = aegisName.toLowerCase();
  return `data\\sprite\\몬스터\\${name}.spr`;
}

const MOB_SPRITE_DIR = 'data\\sprite\\몬스터';

export function mobSpriteCandidates(aegisName, spriteName) {
  const base = aegisName.toLowerCase();
  const candidates = [];
  // Preferred: name resolved from the client's jobname.lub table.
  if (spriteName) {
    candidates.push(`${MOB_SPRITE_DIR}\\${spriteName}.spr`);
  }
  // Fallbacks based on the AegisName (works for many custom/english sprites).
  candidates.push(
    `${MOB_SPRITE_DIR}\\${base}.spr`,
    `${MOB_SPRITE_DIR}\\${aegisName}.spr`,
    `${MOB_SPRITE_DIR}\\${base}_1.spr`,
    `${MOB_SPRITE_DIR}\\1_${base}.spr`
  );
  return [...new Set(candidates)];
}
