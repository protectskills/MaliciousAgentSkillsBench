# -*- coding: utf-8 -*-
"""
Repository Security Scanner Module
==================================

FILE SUMMARY
------------
Stage(s) in pipeline:
  - (3) Download → `RepoDownloader` fetches GitHub repositories as ZIP files.
  - (4) Static scan → `RepoSecurityScanner` inspects code for security risks.
"""

import os
import sys
import json
import logging
import subprocess
import shutil
import zipfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional, Tuple

from utils.config_loader import Config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RepoDownloader:
    def __init__(self, config: Config):
        self.config = config
        self.paths = config.paths

        self.zip_dir = self.paths.zip_dir
        self.repo_dir = self.paths.repo_dir

        self.zip_dir.mkdir(parents=True, exist_ok=True)
        self.repo_dir.mkdir(parents=True, exist_ok=True)

        self.github_token = config.get_with_env_fallback(
            'download.github_token_env',
            'GITHUB_TOKEN',
            ''
        )

        self.max_workers = config.get('download.concurrent_downloads', 15)
        self.timeout = config.get('download.timeout', 300)
        self.branch_fallback = config.get('download.branch_fallback', True)

    def download_repo(self, repo_info: Dict[str, Any]) -> Tuple[bool, str, str]:
        repo_id = repo_info['repo_id']
        repo = repo_info['repo']
        primary_branch = repo_info.get('branch', 'main')

        zip_filename = f"{repo_info.get('id_prefix', '')}{repo_id}.zip"
        zip_path = self.zip_dir / zip_filename

        if zip_path.exists() and zip_path.stat().st_size > 0:
            return True, repo_id, f"Already exists ({zip_path.stat().st_size / 1024 / 1024:.2f} MB)"

        download_url = repo_info.get('download_url')
        attempts = 2 if self.branch_fallback else 1

        for attempt in range(attempts):
            if attempt == 0:
                branch_display = primary_branch
            else:
                logger.warning(f"[{repo_id}] Trying fallback branch")
                fallback_branch = 'master' if primary_branch == 'main' else 'main'
                download_url = f"https://github.com/{repo}/archive/refs/heads/{fallback_branch}.zip"
                branch_display = f"{fallback_branch} (fallback)"

            try:
                success = self._download_with_curl(
                    str(download_url),
                    str(zip_path),
                    repo_id
                )

                if success:
                    file_size = zip_path.stat().st_size
                    logger.info(f"[{repo_id}] Downloaded ({file_size / 1024 / 1024:.2f} MB) [{branch_display}]")
                    return True, repo_id, f"Downloaded ({file_size / 1024 / 1024:.2f} MB) [{branch_display}]"
                else:
                    if zip_path.exists():
                        zip_path.unlink()
                    if attempt + 1 < attempts:
                        continue
                    return False, repo_id, f"Download failed (branch: {branch_display})"

            except Exception as e:
                logger.error(f"[{repo_id}] Exception: {e}")
                if zip_path.exists():
                    zip_path.unlink()
                if attempt + 1 < attempts:
                    continue

        return False, repo_id, "Download failed"

    def _download_with_curl(self, url: str, output_path: str, repo_id: str) -> bool:
        cmd = [
            'curl',
            '-L',
            '-sS',
            '--fail',
            '--max-time', str(self.timeout),
            '-o', output_path,
            url
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=self.timeout + 10
        )

        if result.returncode != 0:
            stderr = result.stderr.decode(errors='ignore').strip()
            logger.error(f"[{repo_id}] curl failed for {url}: {stderr}")
            return False

        path = Path(output_path)
        if not path.exists() or path.stat().st_size == 0:
            logger.error(f"[{repo_id}] empty download for {url}")
            return False

        try:
            with open(path, 'rb') as f:
                sig = f.read(2)
        except Exception as e:
            logger.error(f"[{repo_id}] failed to inspect downloaded file: {e}")
            path.unlink(missing_ok=True)
            return False

        if sig != b'PK':
            try:
                preview = path.read_text(encoding='utf-8', errors='ignore')[:200]
            except Exception:
                preview = "<non-text content>"
            logger.error(f"[{repo_id}] downloaded file is not a ZIP. Preview: {preview}")
            path.unlink(missing_ok=True)
            return False

        return True

    def download_all(self, repo_mapping: List[Dict], limit: Optional[int] = None) -> Dict[str, Any]:
        if limit:
            repo_mapping = repo_mapping[:limit]

        total = len(repo_mapping)
        logger.info(f"Starting download: {total} repos, workers: {self.max_workers}")

        success_count = 0
        failed_count = 0
        skipped_count = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self.download_repo, repo): repo for repo in repo_mapping}

            for future in as_completed(futures):
                try:
                    success, repo_id, msg = future.result()

                    if success:
                        if "Already exists" in msg:
                            skipped_count += 1
                        else:
                            success_count += 1
                    else:
                        failed_count += 1

                except Exception as e:
                    logger.error(f"Download error: {e}")
                    failed_count += 1

        logger.info(f"Download complete: success={success_count}, failed={failed_count}, skipped={skipped_count}")

        return {
            'total': total,
            'success': success_count,
            'failed': failed_count,
            'skipped': skipped_count
        }


class RepoSecurityScanner:
    RISK_PRIORITY = {
        'CRITICAL': 5,
        'HIGH': 4,
        'MEDIUM': 3,
        'LOW': 2,
        'SAFE': 1,
        'UNKNOWN': 0
    }

    def __init__(self, config: Config):
        self.config = config
        self.paths = config.paths

        self.zip_dir = self.paths.zip_dir
        self.repo_dir = self.paths.repo_dir

        self.risk_dirs = {
            'CRITICAL': self.paths.get_risk_dir('critical'),
            'HIGH': self.paths.get_risk_dir('high'),
            'MEDIUM': self.paths.get_risk_dir('medium'),
            'LOW': self.paths.get_risk_dir('low'),
            'SAFE': self.paths.get_risk_dir('safe')
        }

        for risk_dir in self.risk_dirs.values():
            risk_dir.mkdir(parents=True, exist_ok=True)

        self.max_workers = config.get('scanner.max_workers', 5)
        self.timeout = config.get('scanner.timeout', 60)

        self.thresholds = {
            'critical': config.get('scanner.thresholds.critical', 8),
            'high': config.get('scanner.thresholds.high', 6),
            'medium': config.get('scanner.thresholds.medium', 4),
            'low': config.get('scanner.thresholds.low', 2),
        }

        self.scan_stats = {
            'total': 0,
            'scanned': 0,
            'failed': 0,
            'skipped': 0,
            'by_risk': {risk: 0 for risk in self.RISK_PRIORITY.keys()}
        }

    def extract_repo(self, zip_path: Path) -> Optional[Path]:
        repo_id = zip_path.stem
        target_path = self.repo_dir / repo_id

        if target_path.exists() and any(target_path.iterdir()):
            return target_path

        temp_dir = self.paths.workspace_dir / f"temp_extract_{repo_id}"

        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            extracted_items = list(temp_dir.iterdir())
            if not extracted_items:
                raise Exception("Empty archive")

            if len(extracted_items) == 1:
                source_dir = extracted_items[0]
            else:
                source_dir = temp_dir

            shutil.move(str(source_dir), str(target_path))
            shutil.rmtree(temp_dir, ignore_errors=True)

            self.scan_stats['scanned'] += 1
            return target_path

        except Exception as e:
            logger.error(f"Extract failed {zip_path}: {e}")
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
            return None

    def find_skill_dirs(self, repo_path: Path) -> List[Path]:
        skill_dirs = []

        for item in repo_path.rglob('*'):
            if item.is_dir() and self._is_skill_dir(item):
                skill_dirs.append(item)

        return skill_dirs

    def _is_skill_dir(self, path: Path) -> bool:
        indicators = ['SKILL.md', 'skill.json', 'api.json', 'tool.json']
        return any((path / f).exists() for f in indicators)

    def scan_skill(self, skill_dir: Path, repo_id: str) -> Optional[Dict[str, Any]]:
        """
        Scan a single skill directory using the external skill-security-scan tool.
        """
        try:
            import tempfile

            temp_output = tempfile.mktemp(suffix='.json')
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
            elif scanner_python.exists() and (scan_tool_dir / 'standalone_cli.py').exists():
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

            if result.returncode != 0:
                logger.warning(f"Scan failed {skill_dir}: {result.stderr}")
                return None

            if Path(temp_output).exists():
                with open(temp_output, 'r', encoding='utf-8') as f:
                    report = json.load(f)

                os.remove(temp_output)
                return report

        except subprocess.TimeoutExpired:
            logger.error(f"Scan timeout {skill_dir}")
        except Exception as e:
            logger.error(f"Scan error {skill_dir}: {e}")

        return None

    def calculate_repo_risk(self, skill_reports: List[Dict]) -> Tuple[str, Dict]:
        if not skill_reports:
            return 'UNKNOWN', {'reason': 'No skills scanned'}

        risk_counts = {risk: 0 for risk in self.RISK_PRIORITY.keys()}
        total_issues = 0

        for report in skill_reports:
            if not report:
                continue

            risk_score = report.get('risk_score', 0)

            if risk_score >= self.thresholds['critical']:
                risk = 'CRITICAL'
            elif risk_score >= self.thresholds['high']:
                risk = 'HIGH'
            elif risk_score >= self.thresholds['medium']:
                risk = 'MEDIUM'
            elif risk_score >= self.thresholds['low']:
                risk = 'LOW'
            else:
                risk = 'SAFE'

            risk_counts[risk] += 1
            findings = report.get('findings', [])
            total_issues += len(findings)

        max_priority = 0
        repo_risk = 'UNKNOWN'

        for risk, count in risk_counts.items():
            if count > 0:
                priority = self.RISK_PRIORITY.get(risk, 0)
                if priority > max_priority:
                    max_priority = priority
                    repo_risk = risk

        summary = {
            'risk_counts': risk_counts,
            'total_skills': len(skill_reports),
            'total_issues': total_issues
        }

        return repo_risk, summary

    def scan_repo(self, zip_path: Path) -> Tuple[str, str, int]:
        repo_id = zip_path.stem

        for risk_dir in self.risk_dirs.values():
            report_path = risk_dir / f"{repo_id}_report.json"
            if report_path.exists():
                try:
                    with open(report_path, 'r') as f:
                        existing_report = json.load(f)
                        existing_risk = existing_report.get('risk_level', 'UNKNOWN')
                except Exception:
                    existing_risk = 'UNKNOWN'
                return 'skipped', existing_risk, 0

        repo_path = self.extract_repo(zip_path)
        if not repo_path:
            return 'failed', 'UNKNOWN', 0

        skill_dirs = self.find_skill_dirs(repo_path)

        if not skill_dirs:
            logger.warning(f"[{repo_id}] No skills found")
            shutil.rmtree(repo_path, ignore_errors=True)
            return 'skipped', 'UNKNOWN', 0

        logger.info(f"[{repo_id}] Found {len(skill_dirs)} skills")

        skill_reports = []
        for skill_dir in skill_dirs:
            report = self.scan_skill(skill_dir, repo_id)
            if report:
                skill_reports.append(report)

        repo_risk, risk_summary = self.calculate_repo_risk(skill_reports)
        report = self._generate_report(repo_id, repo_path, repo_risk, risk_summary, skill_reports)

        target_dir = self.risk_dirs.get(repo_risk, self.risk_dirs['LOW'])
        report_path = target_dir / f"{repo_id}_report.json"

        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"[{repo_id}] Scan complete: {repo_risk}, skills: {len(skill_dirs)}")
        return 'scanned', repo_risk, len(skill_dirs)

    def _generate_report(self, repo_id: str, repo_path: Path, risk_level: str,
                         risk_summary: Dict, skill_reports: List[Dict]) -> Dict:
        from datetime import datetime

        all_issues = []
        total_files = 0

        for skill_report in skill_reports:
            if not skill_report:
                continue

            issues = skill_report.get('findings', [])
            all_issues.extend(issues)
            total_files += skill_report.get('total_files', 0)

        return {
            'repo_id': repo_id,
            'repo_name': repo_id,
            'repo_path': str(repo_path),
            'scan_timestamp': datetime.now().isoformat(),
            'risk_level': risk_level,
            'total_skills': len(skill_reports),
            'scanned_skills': len(skill_reports),
            'failed_skills': 0,
            'total_files_scanned': total_files,
            'risk_summary': risk_summary,
            'skills_reports': skill_reports,
            'all_issues': all_issues
        }

    def scan_all(self, limit: Optional[int] = None, start_from: int = 0) -> Dict:
        zip_files = list(self.zip_dir.glob('*.zip'))
        zip_files.sort(key=lambda x: self._extract_number(x.name))

        zip_files = zip_files[start_from:]
        if limit:
            zip_files = zip_files[:limit]

        self.scan_stats['total'] = len(zip_files)

        logger.info(f"Starting scan: {len(zip_files)} repos, workers: {self.max_workers}")

        batch_size = 100
        processed = 0

        for i in range(0, len(zip_files), batch_size):
            batch = zip_files[i:i + batch_size]

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {executor.submit(self.scan_repo, zf): zf for zf in batch}

                for future in as_completed(futures):
                    try:
                        status, risk_level, skill_count = future.result()

                        if status == 'scanned':
                            self.scan_stats['by_risk'][risk_level] += 1
                            processed += 1
                        elif status == 'skipped':
                            if risk_level in self.RISK_PRIORITY:
                                self.scan_stats['by_risk'][risk_level] += 1
                            processed += 1
                        else:
                            self.scan_stats['failed'] += 1

                    except Exception as e:
                        logger.error(f"Scan error: {e}")
                        self.scan_stats['failed'] += 1

            logger.info(f"Progress: {processed}/{len(zip_files)}")
            self._print_summary()

        return self.scan_stats

    def _extract_number(self, filename: str) -> int:
        import re
        match = re.search(r'(\d+)', filename)
        return int(match.group(1)) if match else 0

    def _print_summary(self):
        logger.info(f"Scanned: {self.scan_stats['scanned']}, Skipped: {self.scan_stats['skipped']}, Failed: {self.scan_stats['failed']}")
        logger.info(f"Risk distribution: {self.scan_stats['by_risk']}")
