# -*- coding: utf-8 -*-
"""
Repository Security Scanner Module
Scans downloaded repositories for security risks
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

try:
    from ..utils.config_loader import Config
except ImportError:
    from utils.config_loader import Config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RepoDownloader:
    """Download repositories from GitHub"""

    def __init__(self, config: Config):
        self.config = config
        self.paths = config.paths

        self.zip_dir = self.paths.zip_dir
        self.repo_dir = self.paths.repo_dir

        self.zip_dir.mkdir(parents=True, exist_ok=True)
        self.repo_dir.mkdir(parents=True, exist_ok=True)

        github_token_env = config.get('download.github_token_env', 'GITHUB_TOKEN')
        self.github_token = os.environ.get(github_token_env, '')

        self.max_workers = config.get('download.concurrent_downloads', 15)
        self.timeout = config.get('download.timeout', 300)
        self.branch_fallback = config.get('download.branch_fallback', True)

    def download_repo(self, repo_info: Dict[str, Any]) -> Tuple[bool, str, str]:
        """
        Download a single repository

        Args:
            repo_info: Repository information dict

        Returns:
            Tuple of (success, repo_id, message)
        """
        repo_id = repo_info['repo_id']
        repo = repo_info['repo']
        primary_branch = repo_info.get('branch', 'main')

        zip_filename = f"{repo_info.get('id_prefix', '')}{repo_id}.zip"
        zip_path = self.zip_dir / zip_filename

        # Check if already downloaded
        if zip_path.exists() and zip_path.stat().st_size > 0:
            if zipfile.is_zipfile(zip_path):
                return True, repo_id, f"Already exists ({zip_path.stat().st_size / 1024 / 1024:.2f} MB)"
            logger.warning(f"[{repo_id}] Existing file is not a valid ZIP; redownloading")
            zip_path.unlink()

        # Try download with branch fallback
        download_url = repo_info.get('download_url')

        for attempt in range(2):
            if attempt == 0:
                branch_display = primary_branch
            else:
                logger.warning(f"[{repo_id}] Trying fallback branch")
                fallback_branch = 'master' if primary_branch == 'main' else 'main'
                download_url = f"https://github.com/{repo}/archive/{fallback_branch}.zip"
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
                    if attempt == 0:
                        # Remove failed file
                        if zip_path.exists():
                            zip_path.unlink()
                        continue
                    else:
                        return False, repo_id, f"Download failed (branch: {branch_display})"

            except Exception as e:
                logger.error(f"[{repo_id}] Exception: {e}")
                if attempt == 0 and zip_path.exists():
                    zip_path.unlink()
                continue

        return False, repo_id, "Download failed"

    def _download_with_curl(self, url: str, output_path: str, repo_id: str) -> bool:
        """Download using curl with optional authentication"""
        import tempfile

        # Create netrc file for authentication (chmod 0600 to keep the token
        # private on multi-user hosts; default umask would leave it world-readable).
        netrc_file = None
        if self.github_token:
            netrc_file = tempfile.NamedTemporaryFile(mode='w', delete=False)
            netrc_file.write(f"machine github.com\nlogin {self.github_token}\npassword x-oauth-basic\n")
            netrc_file.close()
            os.chmod(netrc_file.name, 0o600)

        try:
            cmd = ['curl', '-f', '-L', '-o', output_path, '-s', '--max-time', str(self.timeout)]

            if netrc_file:
                cmd.extend(['--netrc-file', netrc_file.name])

            cmd.append(url)

            result = subprocess.run(cmd, capture_output=True, timeout=self.timeout + 10)

            output = Path(output_path)
            if result.returncode != 0 or not output.exists() or output.stat().st_size == 0:
                return False

            return zipfile.is_zipfile(output)

        finally:
            if netrc_file:
                import os
                os.unlink(netrc_file.name)

    def download_all(self, repo_mapping: List[Dict], limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Download all repositories

        Args:
            repo_mapping: List of repository info dicts
            limit: Optional limit on number of downloads

        Returns:
            Statistics dictionary
        """
        deduped_mapping = []
        seen_repos = set()
        duplicate_count = 0
        for repo_info in repo_mapping:
            repo = repo_info.get('repo')
            if repo in seen_repos:
                duplicate_count += 1
                continue
            seen_repos.add(repo)
            deduped_mapping.append(repo_info)

        if duplicate_count:
            logger.info(f"Deduplicated {duplicate_count} repeated repo entries before download")

        repo_mapping = deduped_mapping

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
    """Security scanner for repositories"""

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

        # Risk directories
        self.risk_dirs = {
            'CRITICAL': self.paths.get_risk_dir('critical'),
            'HIGH': self.paths.get_risk_dir('high'),
            'MEDIUM': self.paths.get_risk_dir('medium'),
            'LOW': self.paths.get_risk_dir('low'),
            'SAFE': self.paths.get_risk_dir('safe')
        }

        for risk_dir in self.risk_dirs.values():
            risk_dir.mkdir(parents=True, exist_ok=True)

        # Scanner settings
        self.max_workers = config.get('scanner.max_workers', 5)
        self.timeout = config.get('scanner.timeout', 60)

        # Thresholds
        self.thresholds = {
            'critical': config.get('scanner.thresholds.critical', 8),
            'high': config.get('scanner.thresholds.high', 6),
            'medium': config.get('scanner.thresholds.medium', 4),
            'low': config.get('scanner.thresholds.low', 2),
        }

        # Statistics
        self.scan_stats = {
            'total': 0,
            'scanned': 0,
            'failed': 0,
            'skipped': 0,
            'by_risk': {risk: 0 for risk in self.RISK_PRIORITY.keys()}
        }

    def extract_repo(self, zip_path: Path) -> Optional[Path]:
        """Extract repository ZIP file"""
        repo_id = zip_path.stem
        target_path = self.repo_dir / repo_id

        if target_path.exists() and any(target_path.iterdir()):
            return target_path

        temp_dir = self.paths.workspace_dir / f"temp_extract_{repo_id}"

        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Zip-slip defense: refuse any member whose resolved path
                # escapes temp_dir (e.g. absolute paths or '..' traversal).
                temp_resolved = temp_dir.resolve()
                for member in zip_ref.namelist():
                    target = (temp_dir / member).resolve()
                    try:
                        target.relative_to(temp_resolved)
                    except ValueError:
                        raise Exception(f"Unsafe zip member path rejected: {member}")
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

            return target_path

        except Exception as e:
            logger.error(f"Extract failed {zip_path}: {e}")
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
            return None

    def find_skill_dirs(self, repo_path: Path) -> List[Path]:
        """Find all skill directories in repository"""
        skill_dirs = []

        for item in repo_path.rglob('*'):
            if item.is_dir() and self._is_skill_dir(item):
                skill_dirs.append(item)

        return skill_dirs

    def _is_skill_dir(self, path: Path) -> bool:
        """Check if directory is a skill directory"""
        indicators = ['SKILL.md', 'skill.md', 'skill.json', 'api.json', 'tool.json']
        return any((path / f).exists() for f in indicators)

    def scan_skill(self, skill_dir: Path, repo_id: str) -> Optional[Dict[str, Any]]:
        """Scan a single skill directory"""
        import tempfile
        # Atomic create: avoid mktemp() TOCTOU and ensure cleanup on error paths.
        temp_fd, temp_output = tempfile.mkstemp(suffix='.json')
        os.close(temp_fd)
        try:
            cmd = [
                sys.executable, '-m', 'skill_security_scan.src.cli',
                'scan',
                str(skill_dir),
                '--format', 'json',
                '--output', temp_output,
                '--no-color'
            ]

            # Get scan tool directory
            scan_tool_dir = Path(__file__).parent.parent / 'scanner' / 'skill-security-scan'
            cmd[2] = 'src.cli'

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

            if Path(temp_output).exists() and Path(temp_output).stat().st_size > 0:
                with open(temp_output, 'r', encoding='utf-8') as f:
                    return json.load(f)

        except subprocess.TimeoutExpired:
            logger.error(f"Scan timeout {skill_dir}")
        except Exception as e:
            logger.error(f"Scan error {skill_dir}: {e}")
        finally:
            try:
                os.remove(temp_output)
            except OSError:
                pass

        return None

    def calculate_repo_risk(self, skill_reports: List[Dict]) -> Tuple[str, Dict]:
        """Calculate repository risk from skill reports"""
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

        # Find highest priority risk
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
        """
        Scan a single repository

        Returns:
            Tuple of (status, risk_level, skill_count)
            status: 'scanned', 'skipped', 'failed'
        """
        repo_id = zip_path.stem

        # Check if already scanned
        for risk_dir in self.risk_dirs.values():
            report_path = risk_dir / f"{repo_id}_report.json"
            if report_path.exists():
                try:
                    with open(report_path, 'r') as f:
                        existing_report = json.load(f)
                        existing_risk = existing_report.get('risk_level', 'UNKNOWN')
                    return 'skipped', existing_risk, 0
                except (OSError, json.JSONDecodeError) as exc:
                    corrupt_path = report_path.with_suffix(report_path.suffix + '.corrupt')
                    logger.warning(f"[{repo_id}] Existing report is unreadable; moving to {corrupt_path.name} and rescanning: {exc}")
                    try:
                        report_path.replace(corrupt_path)
                    except OSError:
                        report_path.unlink(missing_ok=True)

        # Extract repository
        repo_path = self.extract_repo(zip_path)
        if not repo_path:
            return 'failed', 'UNKNOWN', 0

        # Find skill directories
        skill_dirs = self.find_skill_dirs(repo_path)

        if not skill_dirs:
            logger.warning(f"[{repo_id}] No skills found")
            shutil.rmtree(repo_path, ignore_errors=True)
            return 'skipped', 'UNKNOWN', 0

        logger.info(f"[{repo_id}] Found {len(skill_dirs)} skills")

        # Scan all skills
        skill_reports = []
        for skill_dir in skill_dirs:
            report = self.scan_skill(skill_dir, repo_id)
            if report:
                skill_reports.append(report)

        # Calculate risk
        repo_risk, risk_summary = self.calculate_repo_risk(skill_reports)

        # Generate report
        report = self._generate_report(repo_id, repo_path, repo_risk, risk_summary, skill_reports)

        # Save report
        target_dir = self.risk_dirs.get(repo_risk, self.risk_dirs['LOW'])
        report_path = target_dir / f"{repo_id}_report.json"

        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"[{repo_id}] Scan complete: {repo_risk}, skills: {len(skill_dirs)}")

        return 'scanned', repo_risk, len(skill_dirs)

    def _generate_report(self, repo_id: str, repo_path: Path, risk_level: str,
                         risk_summary: Dict, skill_reports: List[Dict]) -> Dict:
        """Generate repository scan report"""
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
        """Scan all repositories"""
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
                            self.scan_stats['scanned'] += 1
                            self.scan_stats['by_risk'][risk_level] += 1
                            processed += 1
                        elif status == 'skipped':
                            self.scan_stats['skipped'] += 1
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
        """Extract number ID from filename"""
        import re
        match = re.search(r'(\d+)', filename)
        return int(match.group(1)) if match else 0

    def _print_summary(self):
        """Print scan summary"""
        logger.info(f"Scanned: {self.scan_stats['scanned']}, Skipped: {self.scan_stats['skipped']}, Failed: {self.scan_stats['failed']}")
        logger.info(f"Risk distribution: {self.scan_stats['by_risk']}")
