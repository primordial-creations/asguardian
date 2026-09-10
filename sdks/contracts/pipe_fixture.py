"""Protocol fixture: parent exits while its child briefly holds stdout/stderr."""
import json
import subprocess
import sys
request = json.load(sys.stdin)
subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(0.5)'], stdin=subprocess.DEVNULL)
print(json.dumps(dict(protocol_version=1, engine_version=sys.argv[1], scan_id='pipe-fixture',
    correlation_id=request['correlation_id'], state='ready', complete=True, truncated=False,
    findings=[], errors=[], capabilities=dict(profiles=['quality.file-length'], transport='single-request-stdio'))))
