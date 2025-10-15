// scripts/verify_and_fix_stats.js
// 사용법:
//   node scripts/verify_and_fix_stats.js          # 점검만
//   node scripts/verify_and_fix_stats.js --fix    # 발견한 대체파일을 slug.json으로 자동 복구(복사/이름변경)

const fs = require('fs');
const fsp = require('fs/promises');
const path = require('path');

const ROOT = process.cwd();
const DATA_BASES = [path.join(ROOT, 'public', 'data'), path.join(ROOT, 'data')];
const FIX = process.argv.includes('--fix');

function slugify(s) {
  return String(s || '')
    .normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
    .replace(/['’]/g, '').trim().toLowerCase()
    .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
}
function exists(p) { try { fs.accessSync(p); return true; } catch { return false; } }
function readJSON(p) { return JSON.parse(fs.readFileSync(p, 'utf8')); }

function findFirstExisting(...candidates) {
  for (const p of candidates) if (p && exists(p)) return p;
  return null;
}

(async () => {
  // 1) drivers.json 찾기
  const driversJsonPath = findFirstExisting(
    path.join(DATA_BASES[0], 'drivers.json'),
    path.join(DATA_BASES[1], 'drivers.json'),
  );
  if (!driversJsonPath) {
    console.error('❌ drivers.json 을 public/data 또는 data 폴더에서 찾을 수 없습니다.');
    process.exit(1);
  }
  const drivers = readJSON(driversJsonPath);

  // 2) stats 디렉토리
  const statsDirs = [
    path.join(DATA_BASES[0], 'stats'),
    path.join(DATA_BASES[1], 'stats'),
  ];

  const ensureStatsDir = async () => {
    for (const d of statsDirs) {
      try { await fsp.mkdir(d, { recursive: true }); return d; } catch {}
    }
    const fallback = path.join(DATA_BASES[0], 'stats');
    await fsp.mkdir(fallback, { recursive: true }); return fallback;
  };
  const writableStatsDir = await ensureStatsDir();

  let missing = 0, fixed = 0, ok = 0, invalid = 0;

  console.log(`\n🔎 drivers: ${drivers.length}, stats dir: ${writableStatsDir}\n`);

  for (const d of drivers) {
    const slug = d.slug || slugify(d.full_name || d.name || '');
    const number = (d.number || '').toString().trim();
    const code = (d.code || '').toString().toLowerCase().trim();

    // 찾을 우선 후보들
    const canonical = statsDirs.map(s => path.join(s, `${slug}.json`));

    // 이미 정석 파일이 있나?
    let hit = findFirstExisting(...canonical);
    let used = 'slug';

    // 없으면 대체 후보 탐색(번호/코드/다른 변형)
    if (!hit) {
      const alternatives = [];
      if (number) alternatives.push(...statsDirs.map(s => path.join(s, `${number}.json`)));
      if (code)   alternatives.push(...statsDirs.map(s => path.join(s, `${code}.json`)));

      // 흔한 변형: full_name 기반 슬러그(보강)
      if (!d.slug && d.full_name) {
        const altSlug = slugify(d.full_name);
        alternatives.push(...statsDirs.map(s => path.join(s, `${altSlug}.json`)));
      }
      hit = findFirstExisting(...alternatives);
      if (hit) used = 'alt';
    }

    if (!hit) {
      console.log(`❗ MISSING: ${slug}  (code:${code||'-'}, no:${number||'-'})  → stats/<slug>.json 없음`);
      missing++;
      continue;
    }

    // JSON 구조 검증
    let j = null;
    try { j = readJSON(hit); } catch { /* invalid json */ }
    const valid = j && j.season && j.career;

    if (!valid) {
      console.log(`⚠️  INVALID JSON: ${path.basename(hit)} (slug=${slug}) season/career 키가 없습니다`);
      invalid++;
      continue;
    }

    // alt에서 찾았고 --fix면 slug.json으로 복사
    const target = path.join(writableStatsDir, `${slug}.json`);
    if (used === 'alt' && hit !== target) {
      if (FIX) {
        try {
          await fsp.copyFile(hit, target);
          console.log(`🛠️  FIXED: ${path.basename(hit)} → ${path.relative(ROOT, target)}`);
          fixed++;
        } catch (e) {
          console.log(`❌ COPY FAIL: ${e.message}`);
        }
      } else {
        console.log(`👉 FOUND ALT: ${path.basename(hit)} (slug=${slug})  --fix 옵션으로 slug.json으로 복사 가능`);
      }
    } else {
      ok++;
    }
  }

  console.log(`\n=== 결과 요약 ===
✅ OK: ${ok}
🛠️ FIXED(copied): ${fixed}
❗ MISSING(stats/<slug>.json 없음): ${missing}
⚠️ INVALID(JSON 구조 오류): ${invalid}\n`);

  if (!FIX) console.log('ℹ️  자동 복구하려면 --fix 옵션을 붙여 다시 실행하세요.');
})();
