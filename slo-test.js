import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 20,
  duration: __ENV.DURATION || '1m',
  thresholds: {
    'http_req_duration{name:cart}': ['p(95)<20'],
    'http_req_failed{name:pay}': ['rate<0.08'],
    checks: ['rate>=0.90'],
    'http_req_duration{name:report}': ['p(95)<450'],
  },
};

export default function () {
  const base = 'http://127.0.0.1:3000';
  const cart = http.post(`${base}/cart/add`, null, { tags: { name: 'cart' } });
  const report = http.get(`${base}/report`, { tags: { name: 'report' } });
  const pay = http.post(`${base}/pay`, null, { tags: { name: 'pay' } });
  check(cart, { 'cart 200': response => response.status === 200 });
  check(report, { 'report 200': response => response.status === 200 });
  check(pay, { 'pay 200': response => response.status === 200 });
  sleep(1);
}
