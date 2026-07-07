import iconv from 'iconv-lite';

const NPC_IDENTITY = 'data\\luafiles514\\lua files\\datainfo\\npcidentity.lub';
const JOB_NAME = 'data\\luafiles514\\lua files\\datainfo\\jobname.lub';

/**
 * Resolves a mob class ID to its client sprite name using the client's
 * npcidentity.lub (id -> JT_* constant) and jobname.lub (constant -> sprite string).
 * This is how the RO client actually maps a monster view id to its .spr file,
 * which the AegisName alone cannot do reliably.
 */
export async function loadJobNameResolver(stack) {
  const npcRaw = await stack.getFile(NPC_IDENTITY);
  const jobRaw = await stack.getFile(JOB_NAME);

  const idToConst = new Map();
  const constToSprite = new Map();

  if (npcRaw.data) {
    const text = iconv.decode(Buffer.from(npcRaw.data), 'cp949');
    const re = /(JT_\w+)\s*=\s*(\d+)/g;
    let m;
    while ((m = re.exec(text))) {
      idToConst.set(Number(m[2]), m[1]);
    }
  }

  if (jobRaw.data) {
    const text = iconv.decode(Buffer.from(jobRaw.data), 'cp949');
    const re = /\[jobtbl\.(JT_\w+)\]\s*=\s*"([^"]*)"/g;
    let m;
    while ((m = re.exec(text))) {
      constToSprite.set(m[1], m[2]);
    }
  }

  return {
    idToConst,
    constToSprite,
    spriteNameForId(id) {
      const c = idToConst.get(Number(id));
      if (!c) return null;
      return constToSprite.get(c) || null;
    }
  };
}
