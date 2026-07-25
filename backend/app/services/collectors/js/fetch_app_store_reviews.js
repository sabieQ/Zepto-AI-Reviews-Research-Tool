/**
 * App Store reviews helper for Phase 7b collectors.
 * Requires: npm install in this directory (app-store-scraper).
 */
const store = require("app-store-scraper");

function arg(name, fallback) {
  const idx = process.argv.indexOf(`--${name}`);
  if (idx >= 0 && process.argv[idx + 1]) return process.argv[idx + 1];
  return fallback;
}

async function main() {
  const appId = String(arg("app-id", "1575323645"));
  const countryArg = String(arg("country", "in"));
  const limit = Math.min(100, Math.max(1, Number(arg("limit", "50"))));
  const countries = [...new Set([countryArg, "in", "us", "gb", "ae"])];

  let all = [];
  let usedCountry = countryArg;

  for (const country of countries) {
    for (const sort of [store.sort.RECENT, store.sort.HELPFUL]) {
      try {
        const batch = await store.reviews({
          id: appId,
          country,
          page: 1,
          sort,
        });
        if (batch && batch.length > 0) {
          all = batch;
          usedCountry = country;
          break;
        }
      } catch (err) {
        process.stderr.write(`warn country=${country}: ${err.message}\n`);
      }
    }
    if (all.length) break;
  }

  if (all.length) {
    const pages = Math.min(10, Math.ceil(limit / 50));
    for (let page = 2; page <= pages && all.length < limit; page += 1) {
      const batch = await store.reviews({
        id: appId,
        country: usedCountry,
        page,
        sort: store.sort.RECENT,
      });
      if (!batch || batch.length === 0) break;
      all.push(...batch);
    }
  }

  const trimmed = all.slice(0, limit).map((r) => ({
    id: r.id,
    userName: r.userName,
    score: r.score,
    title: r.title,
    text: r.text,
    url: r.url,
    updated: r.updated,
    version: r.version,
    country: usedCountry,
  }));

  process.stdout.write(
    JSON.stringify({ count: trimmed.length, country: usedCountry, reviews: trimmed }),
  );
}

main().catch((err) => {
  process.stderr.write(String(err && err.stack ? err.stack : err));
  process.exit(1);
});
