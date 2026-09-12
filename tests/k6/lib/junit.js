/**
 * Minimal JUnit XML formatter for k6 handleSummary data.
 * Emits one testcase per threshold (CI-friendly, no external deps).
 */

function escapeXml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

/**
 * @param {object} data - k6 handleSummary payload
 * @param {{ name?: string, classname?: string }} [opts]
 * @returns {string} JUnit XML
 */
export function jUnit(data, opts = {}) {
  const suiteName = opts.name || 'ASIWDP Skills k6 thresholds';
  const classname = opts.classname || 'skills.lookup';
  const metrics = (data && data.metrics) || {};

  const cases = [];
  for (const [metricName, metric] of Object.entries(metrics)) {
    const thresholds = metric && metric.thresholds;
    if (!thresholds) {
      continue;
    }
    for (const [thresholdExpr, result] of Object.entries(thresholds)) {
      const passed = result && result.ok === true;
      const name = `${metricName}: ${thresholdExpr}`;
      let body = '';
      if (!passed) {
        body = `\n      <failure message="${escapeXml(`threshold failed: ${name}`)}" type="ThresholdFailure"/>\n    `;
      }
      cases.push(
        `    <testcase name="${escapeXml(name)}" classname="${escapeXml(classname)}">${body}</testcase>`
      );
    }
  }

  const failures = cases.filter((c) => c.includes('<failure')).length;
  const tests = cases.length;

  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    `<testsuites tests="${tests}" failures="${failures}">`,
    `  <testsuite name="${escapeXml(suiteName)}" tests="${tests}" failures="${failures}">`,
    ...cases,
    '  </testsuite>',
    '</testsuites>',
    '',
  ].join('\n');
}
