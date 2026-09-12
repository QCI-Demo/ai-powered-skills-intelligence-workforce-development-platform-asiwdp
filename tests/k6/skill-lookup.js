/**
 * k6 load test — concurrent skill lookup (GET /skills)
 *
 * Story: Automated API Test Suites for Skills Service
 * Epic: Skills Framework & Competency Management Services
 * SLA: successful reads p95 < 50 ms
 *
 * Parameterize via environment variables (never hardcode tokens):
 *   BASE_URL      API root (default http://localhost:8080/api/v1)
 *   TENANT_TOKEN  OAuth2 Bearer JWT for the tenant under test (required)
 *   QUERY         Raw query string for GET /skills (e.g. "category=eng&limit=50")
 *   VUS           Concurrent virtual users (default 10)
 *   DURATION      Test duration (default 30s)
 *   JUNIT_OUT     JUnit XML output path (default k6-skill-lookup-junit.xml)
 */

import http from 'k6/http';
import { check, fail } from 'k6';
import { Trend } from 'k6/metrics';
import { jUnit } from './lib/junit.js';

const BASE_URL = (__ENV.BASE_URL || 'http://localhost:8080/api/v1').replace(/\/$/, '');
const TENANT_TOKEN = __ENV.TENANT_TOKEN || '';
const QUERY = (__ENV.QUERY || '').replace(/^\?/, '');
const VUS = Number(__ENV.VUS || 10);
const DURATION = __ENV.DURATION || '30s';
const JUNIT_OUT = __ENV.JUNIT_OUT || 'k6-skill-lookup-junit.xml';

const skillLookupDuration = new Trend('skill_lookup_duration', true);

export const options = {
  scenarios: {
    skill_lookup: {
      executor: 'constant-vus',
      vus: VUS,
      duration: DURATION,
      gracefulStop: '5s',
    },
  },
  thresholds: {
    // Epic SLA: successful skill reads under 50 ms at the 95th percentile
    'http_req_duration{status:200}': ['p(95)<50'],
    checks: ['rate==1'],
  },
};

export function setup() {
  if (!TENANT_TOKEN) {
    fail(
      'TENANT_TOKEN is required. Pass a short-lived tenant JWT via env; do not hardcode secrets.'
    );
  }
  return {
    url: QUERY ? `${BASE_URL}/skills?${QUERY}` : `${BASE_URL}/skills`,
  };
}

export default function (data) {
  const res = http.get(data.url, {
    headers: {
      Authorization: `Bearer ${TENANT_TOKEN}`,
      Accept: 'application/json',
    },
    tags: { name: 'GET /skills', endpoint: 'skills_lookup' },
  });

  skillLookupDuration.add(res.timings.duration);

  check(res, {
    'status is 200': (r) => r.status === 200,
    'body is present': (r) => r.body !== null && r.body !== undefined && String(r.body).length > 0,
  });
}

export function handleSummary(data) {
  const xml = jUnit(data, {
    name: 'ASIWDP Skills — skill lookup load test',
    classname: 'skills.lookup.load',
  });

  return {
    stdout: textSummaryFallback(data),
    [JUNIT_OUT]: xml,
  };
}

/** Compact console summary without pulling remote jslib. */
function textSummaryFallback(data) {
  const lines = ['', '=== k6 skill lookup summary ==='];
  const duration = data.metrics && data.metrics.http_req_duration;
  if (duration && duration.values) {
    const v = duration.values;
    lines.push(
      `http_req_duration  avg=${fmt(v.avg)}  p95=${fmt(v['p(95)'])}  max=${fmt(v.max)}`
    );
  }
  const tagged =
    data.metrics && data.metrics['http_req_duration{status:200}'];
  if (tagged && tagged.values) {
    const v = tagged.values;
    lines.push(
      `http_req_duration{status:200}  avg=${fmt(v.avg)}  p95=${fmt(v['p(95)'])}  max=${fmt(v.max)}`
    );
  }
  const thresholds = [];
  for (const [name, metric] of Object.entries(data.metrics || {})) {
    if (!metric.thresholds) continue;
    for (const [expr, result] of Object.entries(metric.thresholds)) {
      thresholds.push(`  ${result.ok ? 'PASS' : 'FAIL'}  ${name}: ${expr}`);
    }
  }
  if (thresholds.length) {
    lines.push('thresholds:');
    lines.push(...thresholds);
  }
  lines.push(`JUnit XML → ${JUNIT_OUT}`, '');
  return lines.join('\n');
}

function fmt(ms) {
  if (ms === undefined || ms === null || Number.isNaN(ms)) return 'n/a';
  return `${ms.toFixed(2)}ms`;
}
