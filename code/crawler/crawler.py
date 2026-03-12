# -*- coding: utf-8 -*-
"""
Crawler Module
Crawls skill data from skills.rest and skillsmp platforms
"""

import logging
import requests
import json
import re
import time
import os
import random
import string
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Optional

from utils.config_loader import Config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BaseCrawler(ABC):
    """Base class for skill platform crawlers"""

    def __init__(self, platform_name: str, config: Config):
        """
        Initialize the crawler

        Args:
            platform_name: Name of the skill platform
            config: Configuration object
        """
        self.platform_name = platform_name
        self.config = config

        # Setup paths
        self.data_dir = config.paths.data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.save_path = self.data_dir / f'{platform_name}_full_data.json'

        self.all_data: List[Dict[str, Any]] = []
        self.exist_ids = self._load_existing_data()

    def _load_existing_data(self) -> set:
        """Load existing data and return set of existing IDs"""
        ids = set()
        if self.save_path.exists():
            try:
                with open(self.save_path, 'r', encoding='utf-8') as f:
                    self.all_data = json.load(f)
                    for item in self.all_data:
                        if 'id' in item:
                            ids.add(item['id'])
                logger.info(f"[{self.platform_name}] Loaded {len(ids)} existing IDs")
            except Exception as e:
                logger.error(f"Failed to load existing data: {e}")
        return ids

    def save_incrementally(self, new_items: List[Dict[str, Any]]):
        """Save new items incrementally"""
        if not new_items:
            return

        self.all_data.extend(new_items)

        with open(self.save_path, 'w', encoding='utf-8') as f:
            json.dump(self.all_data, f, ensure_ascii=False, indent=2)

        logger.info(f"[{self.platform_name}] Saved {len(new_items)} new items, total: {len(self.exist_ids)}")

    def random_sleep(self, min_s: float = 1.5, max_s: float = 4.5):
        """Sleep for random duration"""
        time.sleep(random.uniform(min_s, max_s))

    @abstractmethod
    def run(self) -> int:
        """Run the crawler"""
        pass


class SkillsRestCrawler(BaseCrawler):
    """Crawler for skills.rest platform"""

    def __init__(self, config: Config):
        super().__init__('skills_rest', config)

        self.base_url = config.get('crawler.skills_rest.api_url', 'https://skills.rest/api/skills')
        self.limit = config.get('crawler.skills_rest.limit', 60)
        self.max_limit = config.get('crawler.skills_rest.max_limit', 300000)

        self.headers = {
            'accept': 'application/json',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    def run(self) -> int:
        """Run the crawler

        Returns:
            Number of new items crawled
        """
        offset = 0
        consecutive_empty = 0
        total_new = 0

        logger.info(f"[Rest] Starting crawl, max_limit={self.max_limit}")

        while offset < self.max_limit:
            logger.info(f"[Rest] Fetching offset: {offset}")

            params = {'limit': self.limit, 'offset': offset}

            try:
                response = requests.get(
                    self.base_url,
                    headers=self.headers,
                    params=params,
                    timeout=20
                )

                if response.status_code == 200:
                    skills = response.json()
                    if not skills:
                        logger.info("No more data available")
                        break

                    new_items = [s for s in skills if s.get('id') and s.get('id') not in self.exist_ids]
                    for s in new_items:
                        self.exist_ids.add(s.get('id'))

                    if new_items:
                        self.save_incrementally(new_items)
                        consecutive_empty = 0
                        total_new += len(new_items)
                    else:
                        logger.info("No new items this page")
                        consecutive_empty += 1

                    if consecutive_empty > 50:
                        logger.info("50 consecutive empty pages, stopping")
                        break

                    offset += self.limit

                else:
                    logger.warning(f"HTTP {response.status_code}, retrying...")
                    time.sleep(5)

            except Exception as e:
                logger.error(f"Exception during fetch: {e}")
                time.sleep(5)

        logger.info(f"[Rest] Crawl complete, new items: {total_new}")
        return total_new


class SkillsmpCrawler(BaseCrawler):
    """Crawler for skillsmp.com platform"""

    def __init__(self, config: Config):
        super().__init__('skillsmp', config)

        self.search_url = config.get('crawler.skillsmp.api_url', 'https://skillsmp.com/api/v1/skills/search')
        self.api_key = config.get_env('SKILLSMP_API_KEY', '')

        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'accept': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        self.search_chars = list(string.ascii_lowercase) + list(string.digits)

    def run(self) -> int:
        """Run the crawler

        Returns:
            Number of new items crawled
        """
        if not self.api_key:
            logger.error("SkillsMP API key not configured")
            return 0

        logger.info("Starting SkillsMP crawler")

        total_new = 0

        for char in self.search_chars:
            current_page = 1
            limit = 100
            logger.info(f"Searching with character: '{char}'")

            while True:
                params = {
                    'q': char,
                    'page': current_page,
                    'limit': limit,
                    'sortBy': 'recent'
                }

                try:
                    response = requests.get(
                        self.search_url,
                        headers=self.headers,
                        params=params,
                        timeout=20
                    )

                    if response.status_code == 200:
                        res_json = response.json()

                        if not res_json.get('success'):
                            logger.error(f"API error: {res_json.get('error')}")
                            break

                        data_node = res_json.get('data', {})
                        skills = data_node.get('skills', [])
                        pagination = data_node.get('pagination', {})

                        if current_page == 1:
                            total_items = pagination.get('total', 0)
                            total_pages = pagination.get('totalPages', 0)
                            logger.info(f"Total items: {total_items}, pages: {total_pages}")

                        if not skills:
                            break

                        new_items = []
                        for s in skills:
                            s_id = s.get('id')
                            if s_id and s_id not in self.exist_ids:
                                self.exist_ids.add(s_id)
                                new_items.append(s)

                        if new_items:
                            self.save_incrementally(new_items)
                            total_new += len(new_items)
                            logger.info(f"Page {current_page}: {len(new_items)} new items")

                        if not pagination.get('hasNext') or current_page >= total_pages:
                            break

                        current_page += 1

                    elif response.status_code == 401:
                        logger.error("Unauthorized: Invalid API key")
                        return total_new
                    elif response.status_code == 429:
                        logger.warning("Rate limited, sleeping 60s")
                        time.sleep(60)
                    else:
                        logger.warning(f"HTTP {response.status_code}")
                        break

                except Exception as e:
                    logger.error(f"Exception: {e}")
                    time.sleep(5)
                    break

        logger.info(f"[SkillsMP] Crawl complete, new items: {total_new}")
        return total_new


class DataMerger:
    """Merge data from both platforms"""

    def __init__(self, config: Config):
        self.config = config
        self.data_dir = config.paths.data_dir

        self.rest_path = self.data_dir / 'skills_rest_full_data.json'
        self.mp_path = self.data_dir / 'skillsmp_full_data.json'
        self.output_path = self.data_dir / 'all_skills_data.json'

    def _get_url_info(self, url: str) -> tuple:
        """Extract full path and repo name from URL"""
        if not url or not isinstance(url, str):
            return None, None

        url = url.lower().strip().split('#')[0]
        if url.endswith('.git'):
            url = url[:-4]

        full_path = url.rstrip('/')

        # Extract repo name
        from urllib.parse import urlparse
        parsed = urlparse(url)
        path_parts = [p for p in parsed.path.split('/') if p]

        repo_name = ""
        if len(path_parts) >= 2:
            repo_name = f"{parsed.netloc}/{path_parts[0]}/{path_parts[1]}"

        return full_path, repo_name

    def merge(self) -> Dict[str, Any]:
        """Merge data from both platforms"""
        logger.info("Starting data merge")

        rest_list = []
        mp_list = []

        if self.rest_path.exists():
            with open(self.rest_path, 'r', encoding='utf-8') as f:
                rest_list = json.load(f)

        if self.mp_path.exists():
            with open(self.mp_path, 'r', encoding='utf-8') as f:
                mp_list = json.load(f)

        # Build merged results
        merged_results = {}
        full_url_map = {}
        repo_url_map = {}

        for item in rest_list:
            item['data_source'] = "skills.rest"
            s_id = str(item.get('id'))
            item['id'] = s_id

            full_path, repo_name = self._get_url_info(item.get('source_url', ''))

            merged_results[s_id] = item

            if full_path:
                full_url_map[full_path] = s_id
            if repo_name:
                if repo_name not in repo_url_map:
                    repo_url_map[repo_name] = []
                repo_url_map[repo_name].append(s_id)

        logger.info(f"Loaded {len(merged_results)} items from skills.rest")

        new_count = 0
        match_count = 0

        for mp_item in mp_list:
            mp_full, mp_repo = self._get_url_info(mp_item.get('githubUrl', ''))

            matched = False

            # Try full path match
            if mp_full and mp_full in full_url_map:
                target_id = full_url_map[mp_full]
                self._update_item(merged_results[target_id], mp_item)
                matched = True

            # Try repo name match
            elif mp_repo and mp_repo in repo_url_map:
                for target_id in repo_url_map[mp_repo]:
                    self._update_item(merged_results[target_id], mp_item)
                matched = True

            # No match, add as new
            if not matched:
                new_key = f"smp_{mp_item.get('id')}"
                new_mp_item = self._format_mp_item(mp_item)
                merged_results[new_key] = new_mp_item
                new_count += 1
            else:
                match_count += 1

        final_list = list(merged_results.values())
        final_list.sort(key=lambda x: str(x.get('id', '')))

        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(final_list, f, ensure_ascii=False, indent=2)

        logger.info(f"Merge complete: {len(final_list)} total, {match_count} matched, {new_count} new")

        return {
            'total': len(final_list),
            'matched': match_count,
            'new': new_count
        }

    def _update_item(self, base_item: Dict, mp_item: Dict):
        """Update base item with MP data"""
        base_item['smp_stars'] = mp_item.get('stars', 0)
        base_item['smp_id'] = mp_item.get('id')

        if base_item.get('stars') is None or base_item.get('stars') == 0:
            base_item['stars'] = mp_item.get('stars', 0)

    def _format_mp_item(self, mp_item: Dict) -> Dict:
        """Format MP item to match rest format"""
        return {
            "id": mp_item.get('id'),
            "slug": mp_item.get('skillUrl', '').split('/')[-1],
            "name": mp_item.get('name', ''),
            "tagline": "",
            "description": mp_item.get('description', ''),
            "source_url": mp_item.get('githubUrl', ''),
            "r2_zip_key": "",
            "author_name": mp_item.get('author', ''),
            "author_type": "",
            "version": "",
            "complexity": "",
            "dependencies": "",
            "components": "",
            "downloads": 0,
            "card_clicks": 0,
            "weekly_downloads": 0,
            "weekly_card_clicks": 0,
            "rating": 0,
            "ratings_count": 0,
            "hotness_score": 0,
            "status": "",
            "created_at": "",
            "updated_at": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mp_item.get('updatedAt', 0))),
            "keywords": [],
            "category_slug": "",
            "data_source": "skillsmp.com",
            "stars": mp_item.get('stars', 0)
        }
