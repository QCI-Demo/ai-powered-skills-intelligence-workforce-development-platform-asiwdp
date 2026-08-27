/**
 * k6 Load Test for ASIWDP Skills Service - Skill Lookup Performance
 * 
 * Task ID: 9f510d12-c94f-4ba6-bf66-46114a86e637
 * 
 * This script validates that GET /skills requests meet the <50ms (95th percentile)
 * latency SLA defined in the Epic requirements.
 * 
 * Usage:
 *   k6 run --out json=results.json skills-load-test.js
 *   k6 run -e API_BASE_URL=http://localhost:8080 -e TENANT_TOKEN=<token> skills-load-test.js
 * 
 * Environment Variables:
 *   API_BASE_URL  - Base URL for the Skills API (default: http://localhost:8080)
 *   TENANT_ID     - Tenant identifier for scoped requests
 *   TENANT_TOKEN  - OAuth2 Bearer token with skills:read scope
 *   VUS           - Number of virtual users (default: 50)
 *   DURATION      - Test duration (default: 60s)
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';
import { htmlReport } from "https://raw.githubusercontent.com/benc-uk/k6-reporter/main/dist/bundle.js";
import { jUnit } from 'https://jslib.k6.io/k6-summary/0.0.2/index.js';

// Custom metrics for detailed analysis
const skillLookupDuration = new Trend('skill_lookup_duration', true);
const skillListDuration = new Trend('skill_list_duration', true);
const errorRate = new Rate('errors');
const successfulRequests = new Counter('successful_requests');
const failedRequests = new Counter('failed_requests');

// Configuration from environment variables
const API_BASE_URL = __ENV.API_BASE_URL || 'http://localhost:8080';
const API_VERSION = __ENV.API_VERSION || 'v1';
const TENANT_ID = __ENV.TENANT_ID || 'tenant-test-00000000-0000-0000-0000-000000000001';
const TENANT_TOKEN = __ENV.TENANT_TOKEN || 'test-bearer-token';

// Test thresholds - SLA requirements
export const options = {
    // Workload stages for ramp-up, steady state, and ramp-down
    stages: [
        { duration: '10s', target: 10 },   // Ramp up to 10 VUs
        { duration: '30s', target: 50 },   // Ramp up to 50 VUs
        { duration: '60s', target: 50 },   // Stay at 50 VUs for steady state
        { duration: '30s', target: 100 },  // Spike to 100 VUs
        { duration: '30s', target: 100 },  // Maintain spike
        { duration: '20s', target: 0 },    // Ramp down
    ],
    
    // SLA thresholds
    thresholds: {
        // Primary SLA: 95th percentile latency < 50ms for successful requests
        'http_req_duration{status:200}': ['p(95)<50'],
        
        // Secondary thresholds
        'http_req_duration': ['p(99)<100', 'avg<30'],  // 99th < 100ms, avg < 30ms
        'skill_lookup_duration': ['p(95)<50', 'p(99)<100'],
        'skill_list_duration': ['p(95)<50', 'p(99)<100'],
        
        // Error rate should be below 1%
        'errors': ['rate<0.01'],
        
        // At least 95% of requests should succeed
        'http_req_failed': ['rate<0.05'],
    },
    
    // Tags for filtering in reports
    tags: {
        service: 'skills-framework',
        test_type: 'load',
    },
    
    // Summary output configuration
    summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)'],
};

// Common headers for all requests
function getHeaders() {
    return {
        'Authorization': `Bearer ${TENANT_TOKEN}`,
        'X-Tenant-ID': TENANT_ID,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    };
}

// Setup function - runs once before the test
export function setup() {
    console.log(`Starting load test against ${API_BASE_URL}/api/${API_VERSION}`);
    console.log(`Tenant ID: ${TENANT_ID}`);
    
    // Verify service is reachable
    const healthCheck = http.get(`${API_BASE_URL}/api/${API_VERSION}/health`);
    
    if (healthCheck.status !== 200) {
        console.error(`Health check failed with status ${healthCheck.status}`);
        throw new Error('Service is not healthy');
    }
    
    // Create test data if needed
    const testSkillIds = [];
    
    // Create a few skills for lookup tests
    for (let i = 0; i < 5; i++) {
        const createRes = http.post(
            `${API_BASE_URL}/api/${API_VERSION}/skills`,
            JSON.stringify({
                name: `Load Test Skill ${i} - ${Date.now()}`,
                description: 'Skill created for load testing',
                category: 'Technical',
                proficiency_levels: [
                    { level: 1, name: 'Beginner' },
                    { level: 2, name: 'Intermediate' },
                    { level: 3, name: 'Advanced' },
                ],
            }),
            { headers: getHeaders() }
        );
        
        if (createRes.status === 201) {
            testSkillIds.push(createRes.json().id);
        }
    }
    
    return {
        baseUrl: `${API_BASE_URL}/api/${API_VERSION}`,
        skillIds: testSkillIds,
        startTime: new Date().toISOString(),
    };
}

// Main test function - runs for each VU iteration
export default function(data) {
    const headers = getHeaders();
    
    group('Skills List Endpoint', function() {
        // Test listing all skills
        const listStartTime = Date.now();
        const listResponse = http.get(`${data.baseUrl}/skills`, { headers, tags: { name: 'list_skills' } });
        const listDuration = Date.now() - listStartTime;
        
        skillListDuration.add(listDuration);
        
        const listSuccess = check(listResponse, {
            'list skills status is 200': (r) => r.status === 200,
            'list skills response is array': (r) => {
                try {
                    const body = r.json();
                    return Array.isArray(body.data || body);
                } catch {
                    return false;
                }
            },
            'list skills latency < 50ms': (r) => r.timings.duration < 50,
        });
        
        if (listSuccess) {
            successfulRequests.add(1);
        } else {
            failedRequests.add(1);
            errorRate.add(1);
        }
    });
    
    group('Skills Lookup by ID', function() {
        // Test individual skill lookups
        if (data.skillIds && data.skillIds.length > 0) {
            // Pick a random skill ID from our test data
            const skillId = data.skillIds[Math.floor(Math.random() * data.skillIds.length)];
            
            const lookupStartTime = Date.now();
            const lookupResponse = http.get(
                `${data.baseUrl}/skills/${skillId}`,
                { headers, tags: { name: 'get_skill_by_id' } }
            );
            const lookupDuration = Date.now() - lookupStartTime;
            
            skillLookupDuration.add(lookupDuration);
            
            const lookupSuccess = check(lookupResponse, {
                'skill lookup status is 200': (r) => r.status === 200,
                'skill lookup has id': (r) => {
                    try {
                        return r.json().id === skillId;
                    } catch {
                        return false;
                    }
                },
                'skill lookup latency < 50ms': (r) => r.timings.duration < 50,
            });
            
            if (lookupSuccess) {
                successfulRequests.add(1);
            } else {
                failedRequests.add(1);
                errorRate.add(1);
            }
        }
    });
    
    group('Skills Search with Query', function() {
        // Test search/filter functionality
        const searchQueries = ['Python', 'Technical', 'Beginner', 'test'];
        const query = searchQueries[Math.floor(Math.random() * searchQueries.length)];
        
        const searchResponse = http.get(
            `${data.baseUrl}/skills?search=${encodeURIComponent(query)}`,
            { headers, tags: { name: 'search_skills' } }
        );
        
        const searchSuccess = check(searchResponse, {
            'search status is 200': (r) => r.status === 200,
            'search latency < 50ms': (r) => r.timings.duration < 50,
        });
        
        if (searchSuccess) {
            successfulRequests.add(1);
        } else {
            failedRequests.add(1);
            errorRate.add(1);
        }
    });
    
    group('Skills with Pagination', function() {
        // Test paginated requests
        const pageResponse = http.get(
            `${data.baseUrl}/skills?page=1&limit=20`,
            { headers, tags: { name: 'list_skills_paginated' } }
        );
        
        const pageSuccess = check(pageResponse, {
            'paginated list status is 200': (r) => r.status === 200,
            'paginated list latency < 50ms': (r) => r.timings.duration < 50,
        });
        
        if (pageSuccess) {
            successfulRequests.add(1);
        } else {
            failedRequests.add(1);
            errorRate.add(1);
        }
    });
    
    group('Skills with Version Filter', function() {
        // Test version-specific queries
        const versionResponse = http.get(
            `${data.baseUrl}/skills?version=latest`,
            { headers, tags: { name: 'list_skills_versioned' } }
        );
        
        check(versionResponse, {
            'versioned query status is 200 or 400': (r) => r.status === 200 || r.status === 400,
            'versioned query latency < 50ms': (r) => r.timings.duration < 50,
        });
    });
    
    // Small sleep to simulate realistic user behavior
    sleep(Math.random() * 0.5 + 0.1);  // 100-600ms between requests
}

// Teardown function - runs once after the test
export function teardown(data) {
    console.log(`Load test completed. Started at: ${data.startTime}`);
    
    // Cleanup test data
    if (data.skillIds && data.skillIds.length > 0) {
        const headers = getHeaders();
        
        for (const skillId of data.skillIds) {
            http.del(`${data.baseUrl}/skills/${skillId}`, null, { headers });
        }
        console.log(`Cleaned up ${data.skillIds.length} test skills`);
    }
}

// Custom summary handler for JUnit XML output (CI integration)
export function handleSummary(data) {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    
    return {
        // JUnit XML for CI pipeline integration
        [`results/junit-${timestamp}.xml`]: jUnit(data, {
            name: 'ASIWDP Skills API Load Test',
        }),
        
        // HTML report for human review
        [`results/report-${timestamp}.html`]: htmlReport(data, {
            title: 'ASIWDP Skills API Load Test Report',
        }),
        
        // JSON results for further processing
        [`results/results-${timestamp}.json`]: JSON.stringify(data, null, 2),
        
        // Console output
        stdout: textSummary(data, { indent: '  ', enableColors: true }),
    };
}

// Text summary for console output
function textSummary(data, options) {
    const { metrics, root_group } = data;
    
    let output = '\n';
    output += '═'.repeat(70) + '\n';
    output += '  ASIWDP Skills API Load Test Summary\n';
    output += '═'.repeat(70) + '\n\n';
    
    // Key metrics
    if (metrics.http_req_duration) {
        output += '  HTTP Request Duration:\n';
        output += `    Average: ${metrics.http_req_duration.values.avg.toFixed(2)}ms\n`;
        output += `    p(95):   ${metrics.http_req_duration.values['p(95)'].toFixed(2)}ms\n`;
        output += `    p(99):   ${metrics.http_req_duration.values['p(99)'].toFixed(2)}ms\n`;
        output += `    Max:     ${metrics.http_req_duration.values.max.toFixed(2)}ms\n\n`;
    }
    
    if (metrics.skill_lookup_duration) {
        output += '  Skill Lookup Duration:\n';
        output += `    p(95): ${metrics.skill_lookup_duration.values['p(95)'].toFixed(2)}ms\n`;
        output += `    SLA:   50ms\n`;
        output += `    Status: ${metrics.skill_lookup_duration.values['p(95)'] < 50 ? '✓ PASS' : '✗ FAIL'}\n\n`;
    }
    
    // Error metrics
    if (metrics.errors) {
        const errorPct = (metrics.errors.values.rate * 100).toFixed(2);
        output += `  Error Rate: ${errorPct}% (threshold: <1%)\n`;
        output += `  Status: ${metrics.errors.values.rate < 0.01 ? '✓ PASS' : '✗ FAIL'}\n\n`;
    }
    
    // Request counts
    if (metrics.successful_requests) {
        output += `  Successful Requests: ${metrics.successful_requests.values.count}\n`;
    }
    if (metrics.failed_requests) {
        output += `  Failed Requests: ${metrics.failed_requests.values.count}\n`;
    }
    
    output += '\n' + '═'.repeat(70) + '\n';
    
    return output;
}
