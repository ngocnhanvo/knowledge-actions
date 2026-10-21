import { chromium } from 'playwright';
import { createHash } from 'node:crypto';

const siteUrl = process.env.SITE_URL;
const expectedHost = process.env.EXPECTED_HOST;
const suite = process.env.TEST_SUITE ?? 'smoke';
const disallowedDatabase = process.env.DISALLOWED_DB_NAME ?? '';
const expectedHash = process.env.EXPECTED_DB_SHA256 ?? '';
const disallowedHash = process.env.DISALLOWED_DB_SHA256 ?? '';

function assert(ok, message) {
  if (!ok) throw new Error(message);
}
function originForTarget() {
  assert(siteUrl && expectedHost, 'SITE_URL and EXPECTED_HOST are required');
  const parsed = new URL(siteUrl);
  assert(parsed.protocol === 'https:', 'Only HTTPS websites can be tested');
  assert(parsed.username === '' && parsed.password === '', 'URL credentials are forbidden');
  assert(parsed.hostname.toLowerCase() === expectedHost.toLowerCase(), 'Target host mismatch');
  assert(parsed.port === '', 'Custom ports are not permitted');
  assert(['smoke', 'wordpress-site-health'].includes(suite), 'Unknown test suite');
  return parsed.origin;
}
function assertSameOrigin(page, origin) {
  assert(new URL(page.url()).origin === origin, 'Browser navigated outside the approved origin');
}
async function smoke(browser, origin) {
  const page = await browser.newPage();
  try {
    const response = await page.goto(origin + '/', {
      waitUntil: 'domcontentloaded', timeout: 45000,
    });
    assert(response && response.status() >= 200 && response.status() < 400,
      'Home page HTTP response failed');
    assertSameOrigin(page, origin);
    await page.locator('body').waitFor({ state: 'visible', timeout: 15000 });
    assert((await page.locator('body').innerText()).trim().length > 20,
      'Home page has no visible content');
    console.log('DESKTOP_SMOKE=PASS');
    await page.setViewportSize({ width: 390, height: 844 });
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 45000 });
    assertSameOrigin(page, origin);
    await page.locator('body').waitFor({ state: 'visible', timeout: 15000 });
    console.log('MOBILE_SMOKE=PASS');
  } finally {
    await page.close();
  }
}

async function wordpressSiteHealth(browser, origin) {
  const username = process.env.WP_ADMIN_USERNAME;
  const password = process.env.WP_ADMIN_PASSWORD;
  assert(username && password, 'WordPress admin secrets are not configured for this caller');
  const page = await browser.newPage();
  try {
    await page.goto(origin + '/wp-login.php', {
      waitUntil: 'domcontentloaded', timeout: 45000,
    });
    assertSameOrigin(page, origin);
    await page.locator('#user_login').fill(username);
    await page.locator('#user_pass').fill(password);
    await page.locator('#wp-submit').click();
    assertSameOrigin(page, origin);
    await page.goto(origin + '/wp-admin/site-health.php?tab=debug', {
      waitUntil: 'domcontentloaded', timeout: 45000,
    });
    assertSameOrigin(page, origin);
    assert(new URL(page.url()).pathname === '/wp-admin/site-health.php',
      'WordPress login unsuccessful, lacking Site Health permission, or MFA required');
    const databaseBlock = page.locator('#health-check-accordion-block-wp-database');
    await databaseBlock.waitFor({ state: 'attached', timeout: 12000 });
    const headingButton = databaseBlock.locator('button').first();
    if (await headingButton.count()) {
      const expanded = await headingButton.getAttribute('aria-expanded');
      if (expanded === 'false') await headingButton.click();
    }
    await page.waitForTimeout(900);
    const rows = await databaseBlock.locator('tr').evaluateAll(trs => trs.map(tr =>
      [...tr.querySelectorAll('th, td')].map(cell => (cell.textContent ?? '').trim())
    ));
    const row = rows.find(cells => cells.length >= 2 &&
      /database name|tên cơ sở dữ liệu|tên database/i.test(cells[0]));
    if (!row) {
      // Structural diagnostics only: do NOT log real field labels or field values.
      const schema = await databaseBlock.evaluate(el => ({
        rows: el.querySelectorAll('tr').length,
        tables: el.querySelectorAll('table').length,
        headings: el.querySelectorAll('th').length,
        cells: el.querySelectorAll('td').length,
        hasDatabaseNameLabel: /database name|tên cơ sở dữ liệu|tên database/i.test(el.textContent ?? ''),
      }));
      console.log('SITE_HEALTH_SCHEMA=' + JSON.stringify(schema));
      // Header cells are public WordPress field titles, not database field values.
      const labels = rows.map(cells => (cells[0] ?? '').slice(0, 90));
      console.log('SITE_HEALTH_FIELD_TITLES=' + JSON.stringify(labels));
    }
    assert(row && row[1] && row[1].length <= 128, 'Database name was not available in Site Health');
    const actualDatabase = row[1].trim();
    // Never print the actual DB name, WordPress session, passwords, cookies, or HTML.
    console.log('WORDPRESS_SITE_HEALTH_DATABASE_NAME=FOUND');
    if (disallowedDatabase) {
      assert(actualDatabase !== disallowedDatabase, 'DATABASE_NAME_ISOLATION=FAIL (same as comparison name)');
      console.log('DATABASE_NAME_ISOLATION=PASS (different from supplied comparison name)');
    }
    if (expectedHash || disallowedHash) {
      assert([expectedHash, disallowedHash].every(h => !h || /^[a-f0-9]{64}$/.test(h)),
        'Invalid SHA-256 database comparison input');
      const actualHash = createHash('sha256').update(actualDatabase, 'utf8').digest('hex');
      if (expectedHash) {
        assert(actualHash === expectedHash, 'DATABASE_REFERENCE_MATCH=FAIL');
        console.log('DATABASE_REFERENCE_MATCH=PASS');
      }
      if (disallowedHash) {
        assert(actualHash !== disallowedHash, 'DATABASE_DIFFERENCE=FAIL');
        console.log('DATABASE_DIFFERENCE=PASS');
      }
    }
    console.log('WORDPRESS_SITE_HEALTH=PASS');
  } finally {
    await page.close();
  }
}

const origin = originForTarget();
const started = Date.now();
const browser = await chromium.launch({ headless: true });
try {
  if (suite === 'smoke') await smoke(browser, origin);
  else await wordpressSiteHealth(browser, origin);
  console.log('BROWSER_SUITE=PASS name=' + suite + ' elapsed_ms=' + (Date.now() - started));
} finally {
  await browser.close();
}
