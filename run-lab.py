import argparse
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request


def ready():
    try:
        request = urllib.request.Request('http://127.0.0.1:3000/cart/add', method='POST')
        with urllib.request.urlopen(request, timeout=0.5) as response:
            return response.status == 200
    except OSError:
        return False


def wait_ready(server):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError('API ассангүй. results/server.log файлыг шалга.')
        if ready():
            return
        time.sleep(0.05)
    raise RuntimeError('API 10 секундэд ассангүй')


parser = argparse.ArgumentParser()
parser.add_argument('mode', choices=['pass', 'fail', 'chaos'])
args = parser.parse_args()
os.chdir(Path(__file__).resolve().parent)
Path('results').mkdir(exist_ok=True)
if ready():
    raise SystemExit('3000 портод сервер ажиллаж байна. Эхлээд зогсооно уу.')

server = None
test = None
recovery = None
with open('results/server.log', 'a') as server_log, open(f'results/{args.mode}.txt', 'w') as output:
    try:
        server = subprocess.Popen(['node', 'server.js'], stdout=server_log, stderr=subprocess.STDOUT)
        wait_ready(server)
        script = 'slo-test-fail.js' if args.mode == 'fail' else 'slo-test.js'
        env = dict(os.environ, K6_NO_COLOR='true', DURATION='2m' if args.mode == 'chaos' else '1m')
        command = ['k6', 'run', '--summary-export', f'results/{args.mode}.json', script]
        output.write('command: ' + ' '.join(command) + '\n')
        output.write('DURATION=' + env['DURATION'] + '\n')
        output.flush()
        test = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT, env=env)
        print(f'{args.mode}: k6 эхэллээ', flush=True)
        if args.mode == 'chaos':
            time.sleep(30)
            if test.poll() is not None:
                raise RuntimeError('Chaos эхлэхээс өмнө k6 дууссан')
            crash_at = time.monotonic()
            server.kill()
            server.wait()
            print('chaos: API зогслоо, 10 секунд хүлээнэ', flush=True)
            time.sleep(10)
            server = subprocess.Popen(['node', 'server.js'], stdout=server_log, stderr=subprocess.STDOUT)
            wait_ready(server)
            recovery = time.monotonic() - crash_at
            print(f'chaos: API сэргэлээ ({recovery:.3f}с)', flush=True)
        exit_code = test.wait()
        metrics = json.loads(Path(f'results/{args.mode}.json').read_text())['metrics']
        total = int(metrics['http_reqs']['count'])
        succeeded = int(metrics['checks']['passes'])
        failed = total - succeeded
        budget = total * 0.10
        output.write(f'\nexit={exit_code}\n')
        output.write(f'total_requests={total}\nsuccessful_requests={succeeded}\nfailed_requests={failed}\n')
        output.write(f'availability={succeeded / total * 100:.4f}%\n')
        output.write(f'pay_error_rate={metrics["http_req_failed{name:pay}"]["value"] * 100:.4f}%\n')
        output.write(f'cart_p95_ms={metrics["http_req_duration{name:cart}"]["p(95)"]:.4f}\n')
        output.write(f'report_p95_ms={metrics["http_req_duration{name:report}"]["p(95)"]:.4f}\n')
        output.write(f'request_error_budget={budget:.1f}\nbudget_excess={max(0, failed - budget):.1f}\n')
        if recovery is not None:
            output.write(f'time_error_budget_seconds=12\nrecovery_seconds={recovery:.3f}\n')
            output.write(f'recovery_slo_pass={recovery <= 12}\n')
        print(f'{args.mode}: exit={exit_code}; availability={succeeded / total * 100:.4f}%', flush=True)
    finally:
        if test is not None and test.poll() is None:
            test.terminate()
            test.wait()
        if server is not None and server.poll() is None:
            server.terminate()
            server.wait()

raise SystemExit(exit_code if recovery is None or recovery <= 12 else 1)
