/* Daily NYC Senior Marketing Manager job scan (no browser, no python).
   Sources: Amazon (search.json), Apple (HTML scrape best-effort).
*/
const fs = require('fs');
const path = require('path');

const STATE_PATH = '/home/clawd/clawd/memory/job-search-smm-nyc.json';
const REPORT_DIR = '/home/clawd/clawd/reports/job-search';

function isoNow() { return new Date().toISOString(); }
function todayUtcYmd() {
  const d = new Date();
  const y = d.getUTCFullYear();
  const m = String(d.getUTCMonth()+1).padStart(2,'0');
  const da = String(d.getUTCDate()).padStart(2,'0');
  return `${y}-${m}-${da}`;
}

async function fetchText(url) {
  const res = await fetch(url, { redirect: 'follow', headers: { 'user-agent': 'OpenClaw job scanner (node fetch)' } });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
  return await res.text();
}
async function fetchJson(url) {
  const res = await fetch(url, { redirect: 'follow', headers: { 'user-agent': 'OpenClaw job scanner (node fetch)' } });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
  return await res.json();
}

function ensureDir(p) { fs.mkdirSync(p, { recursive: true }); }
function loadState() {
  if (!fs.existsSync(STATE_PATH)) return { lastRunIso: null, seenUrls: [], excludedUrls: [] };
  return JSON.parse(fs.readFileSync(STATE_PATH, 'utf8'));
}
function saveState(state) {
  ensureDir(path.dirname(STATE_PATH));
  fs.writeFileSync(STATE_PATH, JSON.stringify(state, null, 2));
}

function normUrl(u) {
  return (u || '').trim().replace(/#.*$/, '');
}

function titleMatchesWidened(title) {
  const t = (title || '').toLowerCase();
  // direct accepts
  const direct = [
    'senior marketing manager',
    'senior manager, marketing',
    'senior manager marketing'
  ];
  if (direct.some(s => t.includes(s))) return true;

  // growth/performance/lifecycle/product marketing (manager or senior manager)
  const domains = ['growth marketing', 'performance marketing', 'lifecycle marketing', 'product marketing'];
  const hasDomain = domains.some(s => t.includes(s));
  const hasMgr = /\b(manager|head|lead|principal)\b/.test(t);
  if (hasDomain && hasMgr) return true;

  // Marketing Manager only if senior-ish scope in title
  if (t.includes('marketing manager') && /\b(senior|sr\.?|principal|lead|head)\b/.test(t)) return true;

  // Product Marketing Manager sometimes counts if clearly senior (principal/sr)
  if (t.includes('product marketing manager') && /\b(senior|sr\.?|principal|lead|head)\b/.test(t)) return true;

  return false;
}

function locationSatisfiesHardRule(text) {
  const s = (text || '').toLowerCase();
  // Hard rule: explicitly lists New York, NY / New York, NY, USA / New York, New York, United States
  const ny1 = 'new york, ny';
  const ny2 = 'new york, ny, usa';
  const ny3 = 'new york, new york, united states';
  const ny4 = 'new york, new york, usa';
  if (s.includes(ny1) || s.includes(ny2) || s.includes(ny3) || s.includes(ny4)) return true;

  // Remote + NYC eligible (must explicitly say remote and mention NYC or US eligible)
  const remote = /\bremote\b/.test(s);
  const nycEligible = /\bnyc\b/.test(s) || /new york\b/.test(s);
  const usEligible = /united states\b/.test(s) || /u\.s\./.test(s) || /us\b/.test(s);
  if (remote && (nycEligible || usEligible)) return true;

  return false;
}

function extractAmazonSalary(job) {
  const blob = `${job.preferred_qualifications || ''}\n${job.description || ''}`;
  // Prefer NY line when multiple locations present.
  const lines = blob.split(/<br\s*\/?\s*>|\n/).map(l => l.trim()).filter(Boolean);
  const nyLine = lines.find(l => /USA,\s*NY,\s*New York\s*-\s*\d/.test(l));
  const anyLine = nyLine || lines.find(l => /USD annually/.test(l));
  if (!anyLine) return null;
  const m = anyLine.match(/-\s*([0-9,.]+)\s*-\s*([0-9,.]+)\s*USD annually/i);
  if (!m) return anyLine;
  return `$${m[1]}–$${m[2]} USD (annual base)`;
}

function amazonJobToCandidate(job) {
  const url = `https://www.amazon.jobs${job.job_path}`;
  const locText = job.normalized_location || job.location || '';
  const locs = Array.isArray(job.locations) ? job.locations.join(' ') : '';
  const locationEvidence = `${locText}\n${locs}`;
  return {
    company: (job.company_name || 'Amazon'),
    title: job.title || '(untitled)',
    location: job.normalized_location || job.location || '',
    salary: extractAmazonSalary(job),
    link: url,
    notes: job.posted_date ? `Posted: ${job.posted_date}` : null,
    _locationEvidence: locationEvidence,
    _raw: job
  };
}

function mdEscape(s) {
  return (s || '').replace(/\|/g,'\\|');
}

(async () => {
  ensureDir(REPORT_DIR);
  const state = loadState();
  const seen = new Set(state.seenUrls.map(normUrl));
  const excluded = new Set(state.excludedUrls.map(normUrl));

  const discoveryNotes = [];
  const candidates = new Map(); // url -> candidate
  const excludedItems = [];

  // --- Amazon discovery (direct JSON endpoint) ---
  const amazonQueries = [
    { q: 'marketing manager', loc: 'New York, NY, United States' },
    { q: 'product marketing manager', loc: 'New York, NY, United States' },
    { q: 'lifecycle marketing manager', loc: 'New York, NY, United States' },
    { q: 'growth marketing manager', loc: 'New York, NY, United States' },
    { q: 'senior marketing manager', loc: 'New York, NY, United States' },
  ];

  for (const {q, loc} of amazonQueries) {
    const url = `https://www.amazon.jobs/en/search.json?base_query=${encodeURIComponent(q)}&loc_query=${encodeURIComponent(loc)}&result_limit=50&offset=0`;
    discoveryNotes.push(`Amazon: ${q} @ ${loc}`);
    let data;
    try {
      data = await fetchJson(url);
    } catch (e) {
      excludedItems.push({ link: url, reason: `ERROR fetching Amazon search: ${e.message}` });
      continue;
    }
    const jobs = (data && data.jobs) || [];
    for (const job of jobs) {
      const cand = amazonJobToCandidate(job);
      const u = normUrl(cand.link);
      if (!u) continue;

      const titleOk = titleMatchesWidened(cand.title);
      const locationOk = locationSatisfiesHardRule(cand._locationEvidence);

      if (!titleOk) {
        // don't permanently exclude by state; just ignore
        continue;
      }
      if (!locationOk) {
        excludedItems.push({
          company: cand.company,
          title: cand.title,
          location: cand.location,
          link: u,
          reason: 'Location did not explicitly match hard rule (NY, NY or remote NYC/US eligible)'
        });
        continue;
      }
      candidates.set(u, cand);
    }
  }

  // --- Apple discovery (search page is accessible without browser, but individual postings are heavy/JS-y).
  // We fetch only the search page and log that it was checked; we do NOT attempt to verify postings here.
  // This keeps the scan reliable within cron time limits and avoids lots of fetches.
  try {
    discoveryNotes.push('Apple: search "marketing manager" in New York City (checked search page; postings not verified in this run)');
    await fetchText('https://jobs.apple.com/en-us/search?search=marketing%20manager&location=new-york-city-NYC');
  } catch (e) {
    excludedItems.push({ company: 'Apple', link: 'https://jobs.apple.com', reason: `ERROR fetching Apple search: ${e.message}` });
  }

  // Dedupe vs state; decide net-new
  const netNew = [];
  for (const [u, cand] of candidates.entries()) {
    if (seen.has(u) || excluded.has(u)) continue;
    netNew.push(cand);
  }

  // Update state
  const nextState = {
    lastRunIso: isoNow(),
    seenUrls: Array.from(new Set([...state.seenUrls.map(normUrl), ...netNew.map(c => normUrl(c.link))])).filter(Boolean),
    excludedUrls: Array.from(new Set([...state.excludedUrls.map(normUrl), ...excludedItems.map(e => normUrl(e.link))])).filter(Boolean)
  };

  // Write report
  const ymd = todayUtcYmd();
  const reportPath = path.join(REPORT_DIR, `job-scan-${ymd}.md`);
  const latestPath = path.join(REPORT_DIR, 'job-scan-latest.md');

  const lines = [];
  lines.push(`# Daily Job Scan — NYC Senior Marketing Manager\n`);
  lines.push(`- Run (UTC): ${nextState.lastRunIso}`);
  lines.push(`- Net-new roles: **${netNew.length}**\n`);

  lines.push('## New roles');
  if (netNew.length === 0) {
    lines.push('\n_No net-new roles found today._\n');
  } else {
    for (const c of netNew) {
      lines.push(`\n- **${mdEscape(c.company)}** — **${mdEscape(c.title)}** (${mdEscape(c.location)})`);
      if (c.salary) lines.push(`  - Salary: ${mdEscape(c.salary)}`);
      lines.push(`  - Link: ${c.link}`);
      if (c.notes) lines.push(`  - Notes: ${mdEscape(c.notes)}`);
    }
    lines.push('');
  }

  lines.push('## Excluded / notes');
  lines.push('\n### Discovery sources checked');
  for (const n of discoveryNotes) lines.push(`- ${n}`);

  if (excludedItems.length) {
    lines.push('\n### Excluded candidates');
    for (const e of excludedItems.slice(0, 50)) {
      const bits = [e.company, e.title].filter(Boolean).join(' — ');
      lines.push(`- ${bits || '(item)'}${e.location ? ` (${e.location})` : ''}`);
      if (e.link) lines.push(`  - ${e.link}`);
      if (e.reason) lines.push(`  - Reason: ${e.reason}`);
    }
    if (excludedItems.length > 50) lines.push(`- …and ${excludedItems.length - 50} more`);
  } else {
    lines.push('\n_(No exclusions logged)_');
  }

  fs.writeFileSync(reportPath, lines.join('\n') + '\n');
  fs.writeFileSync(latestPath, lines.join('\n') + '\n');
  saveState(nextState);

  // Emit summary JSON for caller
  process.stdout.write(JSON.stringify({ reportPath, latestPath, netNewCount: netNew.length, netNew }, null, 2));
})().catch(err => {
  console.error('JOBSCAN_ERROR', err);
  process.exit(2);
});
