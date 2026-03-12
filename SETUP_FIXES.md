# Setup Fixes and Known Issues

This document summarizes setup issues encountered while running the repository locally on Linux and the fixes applied to resolve them.

---

## 1. Path Helper Import Error

**Issue**

An outdated import in `utils/__init__.py` caused an import error.

**Fix**

Replace the import with the correct helper functions.

Command used:

sed -i 's/from \.path_helper import Paths/from \.path_helper import get_project_root, ensure_dir, get_relative_path, find_skill_markdown, is_skill_directory/' code/utils/__init__.py

**File modified**

code/utils/__init__.py

---

## 2. Relative Import Error in Crawler

**Issue**

The crawler module used relative imports (`..utils`) which failed depending on the execution context.

**Fix**

Convert the relative imports to absolute imports.

Commands used:

sed -i 's/from \.\.utils\./from utils./g' code/crawler/crawler.py  
sed -i 's/import \.\.utils\./import utils./g' code/crawler/crawler.py  

**File modified**

code/crawler/crawler.py

---

## 3. Docker Dependency Mirror Issue

**Issue**

The Dockerfile used the Tsinghua PyPI mirror which failed during dependency resolution.

**Fix**

Replace the mirror with the default PyPI index.

Command used:

sed -i 's|https://pypi.tuna.tsinghua.edu.cn/simple|https://pypi.org/simple|' code/Dockerfile

Then rebuild the container:

docker build --no-cache -t claude-skill-sandbox .

**File modified**

code/Dockerfile

---

## 4. Missing `skill-security-scan` Tool

**Issue**

The repository references `skill-security-scan`, but the tool was not present in the expected directory.

Example evidence:

grep -RIn "skill-security-scan\|skill_security_scan" .

References were found in:

- README.md  
- data/skills_dataset.csv  
- code/README.md  
- skills-all-time.json  

---

### Setup

Clone the scanner repository:

git clone https://github.com/huifer/skill-security-scan.git code/scanner/skill-security-scan

Install it locally:

pip install -e code/scanner/skill-security-scan

---

### Scanner Invocation Fix

The original code assumed a fixed module-based execution:

cmd = [
    sys.executable, '-m', 'skill_security_scan.src.cli',
    'scan',
    str(skill_dir),
    '--format', 'json',
    '--output', temp_output,
    '--no-color'
]

scan_tool_dir = Path(__file__).parent.parent / 'scanner' / 'skill-security-scan'

result = subprocess.run(
    cmd,
    cwd=str(scan_tool_dir),
    capture_output=True,
    text=True,
    timeout=self.timeout
)

This was replaced with a more robust fallback strategy:

scan_tool_dir = Path(__file__).parent.parent / 'scanner' / 'skill-security-scan'
scanner_python = scan_tool_dir / '.venv' / 'bin' / 'python3'
scanner_cli = scan_tool_dir / '.venv' / 'bin' / 'skill-security-scan'

if scanner_cli.exists():
    cmd = [
        str(scanner_cli),
        'scan',
        str(skill_dir),
        '--format', 'json',
        '--output', temp_output,
        '--no-color'
    ]
elif scanner_python.exists():
    cmd = [
        str(scanner_python),
        str(scan_tool_dir / 'standalone_cli.py'),
        'scan',
        str(skill_dir),
        '--format', 'json',
        '--output', temp_output,
        '--no-color'
    ]
else:
    cmd = [
        'skill-security-scan',
        'scan',
        str(skill_dir),
        '--format', 'json',
        '--output', temp_output,
        '--no-color'
    ]

result = subprocess.run(
    cmd,
    cwd=str(scan_tool_dir),
    capture_output=True,
    text=True,
    timeout=self.timeout
)

**File modified**

code/scanner/scanner.py

---

## Notes

These fixes were required to successfully run the repository locally and make the setup process reproducible.
