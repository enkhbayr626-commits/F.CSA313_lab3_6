import scenario, { options as normalOptions } from './slo-test.js';

export const options = {
  ...normalOptions,
  thresholds: {
    ...normalOptions.thresholds,
    'http_req_duration{name:report}': ['p(95)<100'],
  },
};

export default scenario;
