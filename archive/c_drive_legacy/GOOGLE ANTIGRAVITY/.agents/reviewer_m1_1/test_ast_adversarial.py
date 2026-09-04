import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cron"))

from safety_guardrails import scan_code_for_safety

test_cases = {
    "from_shutil_import": "from shutil import rmtree\nrmtree('/tmp/foo')",
    "from_os_import": "from os import remove\nremove('file.txt')",
    "pathlib_unlink": "from pathlib import Path\nPath('file.txt').unlink()",
    "subprocess_kwargs": "import subprocess\nsubprocess.run(args=['taskkill', '/F'])",
    "getattr_remove": "import os\ngetattr(os, 'remove')('file.txt')",
    "multiline_drop": "import sqlite3\nconn = sqlite3.connect(':memory:')\nconn.execute('''DROP\nTABLE anomalies;''')",
    "comment_drop": "import sqlite3\nconn = sqlite3.connect(':memory:')\nconn.execute('/* comment */ DROP TABLE anomalies;')",
    "truncate_table": "import sqlite3\nconn = sqlite3.connect(':memory:')\nconn.execute('TRUNCATE TABLE anomalies;')",
    "f_string_cmd": "import subprocess\npid = 1234\nsubprocess.run(f'taskkill /PID {pid}')",
    "aliased_shutil": "import shutil as s\ns.rmtree('/tmp/foo')",
    "aliased_os": "import os as my_os\nmy_os.remove('file.txt')",
    "os_system_del": "import os\nos.system('del /f /q C:\\\\test.txt')",
    "os_system_rmdir": "import os\nos.system('rmdir /s /q C:\\\\test')",
    "os_system_kill": "import os\nos.system('kill -9 1234')",
}

for name, code in test_cases.items():
    v = scan_code_for_safety(code, filename=name)
    status = "DETECTED" if len(v) > 0 else "MISSED"
    print(f"[{status}] {name}: {v}")
