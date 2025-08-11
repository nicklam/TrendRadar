# coding=utf-8

import json
import os
import random
import re
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union

import pytz
import requests
import yaml


VERSION = "2.0.3"


# === 配置管理 ===
def load_config():
    """加載配置文件"""
    config_path = os.environ.get("CONFIG_PATH", "config/config.yaml")

    if not Path(config_path).exists():
        raise FileNotFoundError(f"配置文件 {config_path} 不存在")

    with open(config_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f)

    print(f"配置文件加載成功: {config_path}")

    # 構建配置
    config = {
        "VERSION_CHECK_URL": config_data["app"]["version_check_url"],
        "SHOW_VERSION_UPDATE": config_data["app"]["show_version_update"],
        "REQUEST_INTERVAL": config_data["crawler"]["request_interval"],
        "REPORT_MODE": config_data["report"]["mode"],
        "RANK_THRESHOLD": config_data["report"]["rank_threshold"],
        "USE_PROXY": config_data["crawler"]["use_proxy"],
        "DEFAULT_PROXY": config_data["crawler"]["default_proxy"],
        "ENABLE_CRAWLER": config_data["crawler"]["enable_crawler"],
        "ENABLE_NOTIFICATION": config_data["notification"]["enable_notification"],
        "MESSAGE_BATCH_SIZE": config_data["notification"]["message_batch_size"],
        "BATCH_SEND_INTERVAL": config_data["notification"]["batch_send_interval"],
        "FEISHU_MESSAGE_SEPARATOR": config_data["notification"][
            "feishu_message_separator"
        ],
        "WEIGHT_CONFIG": {
            "RANK_WEIGHT": config_data["weight"]["rank_weight"],
            "FREQUENCY_WEIGHT": config_data["weight"]["frequency_weight"],
            "HOTNESS_WEIGHT": config_data["weight"]["hotness_weight"],
        },
        "PLATFORMS": config_data["platforms"],
    }

    # Webhook配置（環境變量優先）
    notification = config_data.get("notification", {})
    webhooks = notification.get("webhooks", {})

    config["FEISHU_WEBHOOK_URL"] = os.environ.get(
        "FEISHU_WEBHOOK_URL", ""
    ).strip() or webhooks.get("feishu_url", "")
    config["DINGTALK_WEBHOOK_URL"] = os.environ.get(
        "DINGTALK_WEBHOOK_URL", ""
    ).strip() or webhooks.get("dingtalk_url", "")
    config["WEWORK_WEBHOOK_URL"] = os.environ.get(
        "WEWORK_WEBHOOK_URL", ""
    ).strip() or webhooks.get("wework_url", "")
    config["TELEGRAM_BOT_TOKEN"] = os.environ.get(
        "TELEGRAM_BOT_TOKEN", ""
    ).strip() or webhooks.get("telegram_bot_token", "")
    config["TELEGRAM_CHAT_ID"] = os.environ.get(
        "TELEGRAM_CHAT_ID", ""
    ).strip() or webhooks.get("telegram_chat_id", "")

    # 輸出配置來源信息
    webhook_sources = []
    if config["FEISHU_WEBHOOK_URL"]:
        source = "環境變量" if os.environ.get("FEISHU_WEBHOOK_URL") else "配置文件"
        webhook_sources.append(f"飛書({source})")
    if config["DINGTALK_WEBHOOK_URL"]:
        source = "環境變量" if os.environ.get("DINGTALK_WEBHOOK_URL") else "配置文件"
        webhook_sources.append(f"釘釘({source})")
    if config["WEWORK_WEBHOOK_URL"]:
        source = "環境變量" if os.environ.get("WEWORK_WEBHOOK_URL") else "配置文件"
        webhook_sources.append(f"企業微信({source})")
    if config["TELEGRAM_BOT_TOKEN"] and config["TELEGRAM_CHAT_ID"]:
        token_source = (
            "環境變量" if os.environ.get("TELEGRAM_BOT_TOKEN") else "配置文件"
        )
        chat_source = "環境變量" if os.environ.get("TELEGRAM_CHAT_ID") else "配置文件"
        webhook_sources.append(f"Telegram({token_source}/{chat_source})")

    if webhook_sources:
        print(f"Webhook 配置來源: {', '.join(webhook_sources)}")
    else:
        print("未配置任何 Webhook")

    return config


print("正在加載配置...")
CONFIG = load_config()
print(f"TrendRadar v{VERSION} 配置加載完成")
print(f"監控平台數量: {len(CONFIG['PLATFORMS'])}")


# === 工具函數 ===
def get_beijing_time():
    """獲取北京時間"""
    return datetime.now(pytz.timezone("Asia/Shanghai"))


def format_date_folder():
    """格式化日期文件夾"""
    return get_beijing_time().strftime("%Y年%m月%d日")


def format_time_filename():
    """格式化時間文件名"""
    return get_beijing_time().strftime("%H時%M分")


def clean_title(title: str) -> str:
    """清理標題中的特殊字符"""
    if not isinstance(title, str):
        title = str(title)
    cleaned_title = title.replace("\n", " ").replace("\r", " ")
    cleaned_title = re.sub(r"\s+", " ", cleaned_title)
    cleaned_title = cleaned_title.strip()
    return cleaned_title


def ensure_directory_exists(directory: str):
    """確保目錄存在"""
    Path(directory).mkdir(parents=True, exist_ok=True)


def get_output_path(subfolder: str, filename: str) -> str:
    """獲取輸出路徑"""
    date_folder = format_date_folder()
    output_dir = Path("output") / date_folder / subfolder
    ensure_directory_exists(str(output_dir))
    return str(output_dir / filename)


def check_version_update(
    current_version: str, version_url: str, proxy_url: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """檢查版本更新"""
    try:
        proxies = None
        if proxy_url:
            proxies = {"http": proxy_url, "https": proxy_url}

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/plain, */*",
            "Cache-Control": "no-cache",
        }

        response = requests.get(
            version_url, proxies=proxies, headers=headers, timeout=10
        )
        response.raise_for_status()

        remote_version = response.text.strip()
        print(f"當前版本: {current_version}, 遠程版本: {remote_version}")

        # 比較版本
        def parse_version(version_str):
            try:
                parts = version_str.strip().split(".")
                if len(parts) != 3:
                    raise ValueError("版本號格式不正確")
                return int(parts[0]), int(parts[1]), int(parts[2])
            except:
                return 0, 0, 0

        current_tuple = parse_version(current_version)
        remote_tuple = parse_version(remote_version)

        need_update = current_tuple < remote_tuple
        return need_update, remote_version if need_update else None

    except Exception as e:
        print(f"版本檢查失敗: {e}")
        return False, None


def is_first_crawl_today() -> bool:
    """檢測是否是當天第一次爬取"""
    date_folder = format_date_folder()
    txt_dir = Path("output") / date_folder / "txt"

    if not txt_dir.exists():
        return True

    files = sorted([f for f in txt_dir.iterdir() if f.suffix == ".txt"])
    return len(files) <= 1


def html_escape(text: str) -> str:
    """HTML轉義"""
    if not isinstance(text, str):
        text = str(text)

    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


# === 數據獲取 ===
class DataFetcher:
    """數據獲取器"""

    def __init__(self, proxy_url: Optional[str] = None):
        self.proxy_url = proxy_url

    def fetch_data(
        self,
        id_info: Union[str, Tuple[str, str]],
        max_retries: int = 2,
        min_retry_wait: int = 3,
        max_retry_wait: int = 5,
    ) -> Tuple[Optional[str], str, str]:
        """獲取指定ID數據，支持重試"""
        if isinstance(id_info, tuple):
            id_value, alias = id_info
        else:
            id_value = id_info
            alias = id_value

        url = f"https://newsnow.busiyi.world/api/s?id={id_value}&latest"

        proxies = None
        if self.proxy_url:
            proxies = {"http": self.proxy_url, "https": self.proxy_url}

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
        }

        retries = 0
        while retries <= max_retries:
            try:
                response = requests.get(
                    url, proxies=proxies, headers=headers, timeout=10
                )
                response.raise_for_status()

                data_text = response.text
                data_json = json.loads(data_text)

                status = data_json.get("status", "未知")
                if status not in ["success", "cache"]:
                    raise ValueError(f"響應狀態異常: {status}")

                status_info = "最新數據" if status == "success" else "緩存數據"
                print(f"獲取 {id_value} 成功（{status_info}）")
                return data_text, id_value, alias

            except Exception as e:
                retries += 1
                if retries <= max_retries:
                    base_wait = random.uniform(min_retry_wait, max_retry_wait)
                    additional_wait = (retries - 1) * random.uniform(1, 2)
                    wait_time = base_wait + additional_wait
                    print(f"請求 {id_value} 失敗: {e}. {wait_time:.2f}秒後重試...")
                    time.sleep(wait_time)
                else:
                    print(f"請求 {id_value} 失敗: {e}")
                    return None, id_value, alias
        return None, id_value, alias

    def crawl_websites(
        self,
        ids_list: List[Union[str, Tuple[str, str]]],
        request_interval: int = CONFIG["REQUEST_INTERVAL"],
    ) -> Tuple[Dict, Dict, List]:
        """爬取多個網站數據"""
        results = {}
        id_to_name = {}
        failed_ids = []

        for i, id_info in enumerate(ids_list):
            if isinstance(id_info, tuple):
                id_value, name = id_info
            else:
                id_value = id_info
                name = id_value

            id_to_name[id_value] = name
            response, _, _ = self.fetch_data(id_info)

            if response:
                try:
                    data = json.loads(response)
                    results[id_value] = {}
                    for index, item in enumerate(data.get("items", []), 1):
                        title = item["title"]
                        url = item.get("url", "")
                        mobile_url = item.get("mobileUrl", "")

                        if title in results[id_value]:
                            results[id_value][title]["ranks"].append(index)
                        else:
                            results[id_value][title] = {
                                "ranks": [index],
                                "url": url,
                                "mobileUrl": mobile_url,
                            }
                except json.JSONDecodeError:
                    print(f"解析 {id_value} 響應失敗")
                    failed_ids.append(id_value)
                except Exception as e:
                    print(f"處理 {id_value} 數據出錯: {e}")
                    failed_ids.append(id_value)
            else:
                failed_ids.append(id_value)

            if i < len(ids_list) - 1:
                actual_interval = request_interval + random.randint(-10, 20)
                actual_interval = max(50, actual_interval)
                time.sleep(actual_interval / 1000)

        print(f"成功: {list(results.keys())}, 失敗: {failed_ids}")
        return results, id_to_name, failed_ids


# === 數據處理 ===
def save_titles_to_file(results: Dict, id_to_name: Dict, failed_ids: List) -> str:
    """保存標題到文件"""
    file_path = get_output_path("txt", f"{format_time_filename()}.txt")

    with open(file_path, "w", encoding="utf-8") as f:
        for id_value, title_data in results.items():
            # id | name 或 id
            name = id_to_name.get(id_value)
            if name and name != id_value:
                f.write(f"{id_value} | {name}\n")
            else:
                f.write(f"{id_value}\n")

            # 按排名排序標題
            sorted_titles = []
            for title, info in title_data.items():
                cleaned_title = clean_title(title)
                if isinstance(info, dict):
                    ranks = info.get("ranks", [])
                    url = info.get("url", "")
                    mobile_url = info.get("mobileUrl", "")
                else:
                    ranks = info if isinstance(info, list) else []
                    url = ""
                    mobile_url = ""

                rank = ranks[0] if ranks else 1
                sorted_titles.append((rank, cleaned_title, url, mobile_url))

            sorted_titles.sort(key=lambda x: x[0])

            for rank, cleaned_title, url, mobile_url in sorted_titles:
                line = f"{rank}. {cleaned_title}"

                if url:
                    line += f" [URL:{url}]"
                if mobile_url:
                    line += f" [MOBILE:{mobile_url}]"
                f.write(line + "\n")

            f.write("\n")

        if failed_ids:
            f.write("==== 以下ID請求失敗 ====\n")
            for id_value in failed_ids:
                f.write(f"{id_value}\n")

    return file_path


def load_frequency_words(
    frequency_file: Optional[str] = None,
) -> Tuple[List[Dict], List[str]]:
    """加載頻率詞配置"""
    if frequency_file is None:
        frequency_file = os.environ.get(
            "FREQUENCY_WORDS_PATH", "config/frequency_words.txt"
        )

    frequency_path = Path(frequency_file)
    if not frequency_path.exists():
        raise FileNotFoundError(f"頻率詞文件 {frequency_file} 不存在")

    with open(frequency_path, "r", encoding="utf-8") as f:
        content = f.read()

    word_groups = [group.strip() for group in content.split("\n\n") if group.strip()]

    processed_groups = []
    filter_words = []

    for group in word_groups:
        words = [word.strip() for word in group.split("\n") if word.strip()]

        group_required_words = []
        group_normal_words = []
        group_filter_words = []

        for word in words:
            if word.startswith("!"):
                filter_words.append(word[1:])
                group_filter_words.append(word[1:])
            elif word.startswith("+"):
                group_required_words.append(word[1:])
            else:
                group_normal_words.append(word)

        if group_required_words or group_normal_words:
            if group_normal_words:
                group_key = " ".join(group_normal_words)
            else:
                group_key = " ".join(group_required_words)

            processed_groups.append(
                {
                    "required": group_required_words,
                    "normal": group_normal_words,
                    "group_key": group_key,
                }
            )

    return processed_groups, filter_words


def parse_file_titles(file_path: Path) -> Tuple[Dict, Dict]:
    """解析單個txt文件的標題數據，返回(titles_by_id, id_to_name)"""
    titles_by_id = {}
    id_to_name = {}

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        sections = content.split("\n\n")

        for section in sections:
            if not section.strip() or "==== 以下ID請求失敗 ====" in section:
                continue

            lines = section.strip().split("\n")
            if len(lines) < 2:
                continue

            # id | name 或 id
            header_line = lines[0].strip()
            if " | " in header_line:
                parts = header_line.split(" | ", 1)
                source_id = parts[0].strip()
                name = parts[1].strip()
                id_to_name[source_id] = name
            else:
                source_id = header_line
                id_to_name[source_id] = source_id

            titles_by_id[source_id] = {}

            for line in lines[1:]:
                if line.strip():
                    try:
                        title_part = line.strip()
                        rank = None

                        # 提取排名
                        if ". " in title_part and title_part.split(". ")[0].isdigit():
                            rank_str, title_part = title_part.split(". ", 1)
                            rank = int(rank_str)

                        # 提取 MOBILE URL
                        mobile_url = ""
                        if " [MOBILE:" in title_part:
                            title_part, mobile_part = title_part.rsplit(" [MOBILE:", 1)
                            if mobile_part.endswith("]"):
                                mobile_url = mobile_part[:-1]

                        # 提取 URL
                        url = ""
                        if " [URL:" in title_part:
                            title_part, url_part = title_part.rsplit(" [URL:", 1)
                            if url_part.endswith("]"):
                                url = url_part[:-1]

                        title = clean_title(title_part.strip())
                        ranks = [rank] if rank is not None else [1]

                        titles_by_id[source_id][title] = {
                            "ranks": ranks,
                            "url": url,
                            "mobileUrl": mobile_url,
                        }

                    except Exception as e:
                        print(f"解析標題行出錯: {line}, 錯誤: {e}")

    return titles_by_id, id_to_name


def read_all_today_titles(
    current_platform_ids: Optional[List[str]] = None,
) -> Tuple[Dict, Dict, Dict]:
    """讀取當天所有標題文件，支持按當前監控平台過濾"""
    date_folder = format_date_folder()
    txt_dir = Path("output") / date_folder / "txt"

    if not txt_dir.exists():
        return {}, {}, {}

    all_results = {}
    final_id_to_name = {}
    title_info = {}

    files = sorted([f for f in txt_dir.iterdir() if f.suffix == ".txt"])

    for file_path in files:
        time_info = file_path.stem

        titles_by_id, file_id_to_name = parse_file_titles(file_path)

        if current_platform_ids is not None:
            filtered_titles_by_id = {}
            filtered_id_to_name = {}

            for source_id, title_data in titles_by_id.items():
                if source_id in current_platform_ids:
                    filtered_titles_by_id[source_id] = title_data
                    if source_id in file_id_to_name:
                        filtered_id_to_name[source_id] = file_id_to_name[source_id]

            titles_by_id = filtered_titles_by_id
            file_id_to_name = filtered_id_to_name

        final_id_to_name.update(file_id_to_name)

        for source_id, title_data in titles_by_id.items():
            process_source_data(
                source_id, title_data, time_info, all_results, title_info
            )

    return all_results, final_id_to_name, title_info


def process_source_data(
    source_id: str,
    title_data: Dict,
    time_info: str,
    all_results: Dict,
    title_info: Dict,
) -> None:
    """處理來源數據，合併重複標題"""
    if source_id not in all_results:
        all_results[source_id] = title_data

        if source_id not in title_info:
            title_info[source_id] = {}

        for title, data in title_data.items():
            ranks = data.get("ranks", [])
            url = data.get("url", "")
            mobile_url = data.get("mobileUrl", "")

            title_info[source_id][title] = {
                "first_time": time_info,
                "last_time": time_info,
                "count": 1,
                "ranks": ranks,
                "url": url,
                "mobileUrl": mobile_url,
            }
    else:
        for title, data in title_data.items():
            ranks = data.get("ranks", [])
            url = data.get("url", "")
            mobile_url = data.get("mobileUrl", "")

            if title not in all_results[source_id]:
                all_results[source_id][title] = {
                    "ranks": ranks,
                    "url": url,
                    "mobileUrl": mobile_url,
                }
                title_info[source_id][title] = {
                    "first_time": time_info,
                    "last_time": time_info,
                    "count": 1,
                    "ranks": ranks,
                    "url": url,
                    "mobileUrl": mobile_url,
                }
            else:
                existing_data = all_results[source_id][title]
                existing_ranks = existing_data.get("ranks", [])
                existing_url = existing_data.get("url", "")
                existing_mobile_url = existing_data.get("mobileUrl", "")

                merged_ranks = existing_ranks.copy()
                for rank in ranks:
                    if rank not in merged_ranks:
                        merged_ranks.append(rank)

                all_results[source_id][title] = {
                    "ranks": merged_ranks,
                    "url": existing_url or url,
                    "mobileUrl": existing_mobile_url or mobile_url,
                }

                title_info[source_id][title]["last_time"] = time_info
                title_info[source_id][title]["ranks"] = merged_ranks
                title_info[source_id][title]["count"] += 1
                if not title_info[source_id][title].get("url"):
                    title_info[source_id][title]["url"] = url
                if not title_info[source_id][title].get("mobileUrl"):
                    title_info[source_id][title]["mobileUrl"] = mobile_url


def detect_latest_new_titles(current_platform_ids: Optional[List[str]] = None) -> Dict:
    """檢測當日最新批次的新增標題，支持按當前監控平台過濾"""
    date_folder = format_date_folder()
    txt_dir = Path("output") / date_folder / "txt"

    if not txt_dir.exists():
        return {}

    files = sorted([f for f in txt_dir.iterdir() if f.suffix == ".txt"])
    if len(files) < 2:
        return {}

    # 解析最新文件
    latest_file = files[-1]
    latest_titles, _ = parse_file_titles(latest_file)

    # 如果指定了當前平台列表，過濾最新文件數據
    if current_platform_ids is not None:
        filtered_latest_titles = {}
        for source_id, title_data in latest_titles.items():
            if source_id in current_platform_ids:
                filtered_latest_titles[source_id] = title_data
        latest_titles = filtered_latest_titles

    # 匯總歷史標題（按平台過濾）
    historical_titles = {}
    for file_path in files[:-1]:
        historical_data, _ = parse_file_titles(file_path)

        # 過濾歷史數據
        if current_platform_ids is not None:
            filtered_historical_data = {}
            for source_id, title_data in historical_data.items():
                if source_id in current_platform_ids:
                    filtered_historical_data[source_id] = title_data
            historical_data = filtered_historical_data

        for source_id, titles_data in historical_data.items():
            if source_id not in historical_titles:
                historical_titles[source_id] = set()
            for title in titles_data.keys():
                historical_titles[source_id].add(title)

    # 找出新增標題
    new_titles = {}
    for source_id, latest_source_titles in latest_titles.items():
        historical_set = historical_titles.get(source_id, set())
        source_new_titles = {}

        for title, title_data in latest_source_titles.items():
            if title not in historical_set:
                source_new_titles[title] = title_data

        if source_new_titles:
            new_titles[source_id] = source_new_titles

    return new_titles


# === 統計和分析 ===
def calculate_news_weight(
    title_data: Dict, rank_threshold: int = CONFIG["RANK_THRESHOLD"]
) -> float:
    """計算新聞權重，用於排序"""
    ranks = title_data.get("ranks", [])
    if not ranks:
        return 0.0

    count = title_data.get("count", len(ranks))
    weight_config = CONFIG["WEIGHT_CONFIG"]

    # 排名權重：Σ(11 - min(rank, 10)) / 出現次數
    rank_scores = []
    for rank in ranks:
        score = 11 - min(rank, 10)
        rank_scores.append(score)

    rank_weight = sum(rank_scores) / len(ranks) if ranks else 0

    # 頻次權重：min(出現次數, 10) × 10
    frequency_weight = min(count, 10) * 10

    # 熱度加成：高排名次數 / 總出現次數 × 100
    high_rank_count = sum(1 for rank in ranks if rank <= rank_threshold)
    hotness_ratio = high_rank_count / len(ranks) if ranks else 0
    hotness_weight = hotness_ratio * 100

    total_weight = (
        rank_weight * weight_config["RANK_WEIGHT"]
        + frequency_weight * weight_config["FREQUENCY_WEIGHT"]
        + hotness_weight * weight_config["HOTNESS_WEIGHT"]
    )

    return total_weight


def matches_word_groups(
    title: str, word_groups: List[Dict], filter_words: List[str]
) -> bool:
    """檢查標題是否匹配詞組規則"""
    # 如果沒有配置詞組，則匹配所有標題（支持顯示全部新聞）
    if not word_groups:
        return True

    title_lower = title.lower()

    # 過濾詞檢查
    if any(filter_word.lower() in title_lower for filter_word in filter_words):
        return False

    # 詞組匹配檢查
    for group in word_groups:
        required_words = group["required"]
        normal_words = group["normal"]

        # 必須詞檢查
        if required_words:
            all_required_present = all(
                req_word.lower() in title_lower for req_word in required_words
            )
            if not all_required_present:
                continue

        # 普通詞檢查
        if normal_words:
            any_normal_present = any(
                normal_word.lower() in title_lower for normal_word in normal_words
            )
            if not any_normal_present:
                continue

        return True

    return False


def format_time_display(first_time: str, last_time: str) -> str:
    """格式化時間顯示"""
    if not first_time:
        return ""
    if first_time == last_time or not last_time:
        return first_time
    else:
        return f"[{first_time} ~ {last_time}]"


def format_rank_display(ranks: List[int], rank_threshold: int, format_type: str) -> str:
    """統一的排名格式化方法"""
    if not ranks:
        return ""

    unique_ranks = sorted(set(ranks))
    min_rank = unique_ranks[0]
    max_rank = unique_ranks[-1]

    if format_type == "html":
        highlight_start = "<font color='red'><strong>"
        highlight_end = "</strong></font>"
    elif format_type == "feishu":
        highlight_start = "<font color='red'>**"
        highlight_end = "**</font>"
    elif format_type == "dingtalk":
        highlight_start = "**"
        highlight_end = "**"
    elif format_type == "wework":
        highlight_start = "**"
        highlight_end = "**"
    elif format_type == "telegram":
        highlight_start = "<b>"
        highlight_end = "</b>"
    else:
        highlight_start = "**"
        highlight_end = "**"

    if min_rank <= rank_threshold:
        if min_rank == max_rank:
            return f"{highlight_start}[{min_rank}]{highlight_end}"
        else:
            return f"{highlight_start}[{min_rank} - {max_rank}]{highlight_end}"
    else:
        if min_rank == max_rank:
            return f"[{min_rank}]"
        else:
            return f"[{min_rank} - {max_rank}]"


def count_word_frequency(
    results: Dict,
    word_groups: List[Dict],
    filter_words: List[str],
    id_to_name: Dict,
    title_info: Optional[Dict] = None,
    rank_threshold: int = CONFIG["RANK_THRESHOLD"],
    new_titles: Optional[Dict] = None,
    mode: str = "daily",
) -> Tuple[List[Dict], int]:
    """統計詞頻，支持必須詞、頻率詞、過濾詞，並標記新增標題"""

    # 如果沒有配置詞組，創建一個包含所有新聞的虛擬詞組
    if not word_groups:
        print("頻率詞配置為空，將顯示所有新聞")
        word_groups = [{"required": [], "normal": [], "group_key": "全部新聞"}]
        filter_words = []  # 清空過濾詞，顯示所有新聞

    is_first_today = is_first_crawl_today()

    # 確定處理的數據源和新增標記邏輯
    if mode == "incremental":
        if is_first_today:
            # 增量模式 + 當天第一次：處理所有新聞，都標記為新增
            results_to_process = results
            all_news_are_new = True
        else:
            # 增量模式 + 當天非第一次：只處理新增的新聞
            results_to_process = new_titles if new_titles else {}
            all_news_are_new = True
    elif mode == "current":
        # current 模式：只處理當前時間批次的新聞，但統計信息來自全部歷史
        if title_info:
            latest_time = None
            for source_titles in title_info.values():
                for title_data in source_titles.values():
                    last_time = title_data.get("last_time", "")
                    if last_time:
                        if latest_time is None or last_time > latest_time:
                            latest_time = last_time

            # 只處理 last_time 等於最新時間的新聞
            if latest_time:
                results_to_process = {}
                for source_id, source_titles in results.items():
                    if source_id in title_info:
                        filtered_titles = {}
                        for title, title_data in source_titles.items():
                            if title in title_info[source_id]:
                                info = title_info[source_id][title]
                                if info.get("last_time") == latest_time:
                                    filtered_titles[title] = title_data
                        if filtered_titles:
                            results_to_process[source_id] = filtered_titles

                print(
                    f"當前榜單模式：最新時間 {latest_time}，篩選出 {sum(len(titles) for titles in results_to_process.values())} 條當前榜單新聞"
                )
            else:
                results_to_process = results
        else:
            results_to_process = results
        all_news_are_new = False
    else:
        # 當日匯總模式：處理所有新聞
        results_to_process = results
        all_news_are_new = False
        total_input_news = sum(len(titles) for titles in results.values())
        filter_status = (
            "全部顯示"
            if len(word_groups) == 1 and word_groups[0]["group_key"] == "全部新聞"
            else "頻率詞過濾"
        )
        print(f"當日匯總模式：處理 {total_input_news} 條新聞，模式：{filter_status}")

    word_stats = {}
    total_titles = 0
    processed_titles = {}
    matched_new_count = 0

    if title_info is None:
        title_info = {}
    if new_titles is None:
        new_titles = {}

    for group in word_groups:
        group_key = group["group_key"]
        word_stats[group_key] = {"count": 0, "titles": {}}

    for source_id, titles_data in results_to_process.items():
        total_titles += len(titles_data)

        if source_id not in processed_titles:
            processed_titles[source_id] = {}

        for title, title_data in titles_data.items():
            if title in processed_titles.get(source_id, {}):
                continue

            # 使用統一的匹配邏輯
            matches_frequency_words = matches_word_groups(
                title, word_groups, filter_words
            )

            if not matches_frequency_words:
                continue

            # 如果是增量模式或 current 模式第一次，統計匹配的新增新聞數量
            if (mode == "incremental" and all_news_are_new) or (
                mode == "current" and is_first_today
            ):
                matched_new_count += 1

            source_ranks = title_data.get("ranks", [])
            source_url = title_data.get("url", "")
            source_mobile_url = title_data.get("mobileUrl", "")

            # 找到匹配的詞組
            title_lower = title.lower()
            for group in word_groups:
                required_words = group["required"]
                normal_words = group["normal"]

                # 如果是"全部新聞"模式，所有標題都匹配第一個（唯一的）詞組
                if len(word_groups) == 1 and word_groups[0]["group_key"] == "全部新聞":
                    group_key = group["group_key"]
                    word_stats[group_key]["count"] += 1
                    if source_id not in word_stats[group_key]["titles"]:
                        word_stats[group_key]["titles"][source_id] = []
                else:
                    # 原有的匹配邏輯
                    if required_words:
                        all_required_present = all(
                            req_word.lower() in title_lower
                            for req_word in required_words
                        )
                        if not all_required_present:
                            continue

                    if normal_words:
                        any_normal_present = any(
                            normal_word.lower() in title_lower
                            for normal_word in normal_words
                        )
                        if not any_normal_present:
                            continue

                    group_key = group["group_key"]
                    word_stats[group_key]["count"] += 1
                    if source_id not in word_stats[group_key]["titles"]:
                        word_stats[group_key]["titles"][source_id] = []

                first_time = ""
                last_time = ""
                count_info = 1
                ranks = source_ranks if source_ranks else []
                url = source_url
                mobile_url = source_mobile_url

                # 對於 current 模式，從歷史統計信息中獲取完整數據
                if (
                    mode == "current"
                    and title_info
                    and source_id in title_info
                    and title in title_info[source_id]
                ):
                    info = title_info[source_id][title]
                    first_time = info.get("first_time", "")
                    last_time = info.get("last_time", "")
                    count_info = info.get("count", 1)
                    if "ranks" in info and info["ranks"]:
                        ranks = info["ranks"]
                    url = info.get("url", source_url)
                    mobile_url = info.get("mobileUrl", source_mobile_url)
                elif (
                    title_info
                    and source_id in title_info
                    and title in title_info[source_id]
                ):
                    info = title_info[source_id][title]
                    first_time = info.get("first_time", "")
                    last_time = info.get("last_time", "")
                    count_info = info.get("count", 1)
                    if "ranks" in info and info["ranks"]:
                        ranks = info["ranks"]
                    url = info.get("url", source_url)
                    mobile_url = info.get("mobileUrl", source_mobile_url)

                if not ranks:
                    ranks = [99]

                time_display = format_time_display(first_time, last_time)

                source_name = id_to_name.get(source_id, source_id)

                # 判斷是否為新增
                is_new = False
                if all_news_are_new:
                    # 增量模式下所有處理的新聞都是新增，或者當天第一次的所有新聞都是新增
                    is_new = True
                elif new_titles and source_id in new_titles:
                    # 檢查是否在新增列表中
                    new_titles_for_source = new_titles[source_id]
                    is_new = title in new_titles_for_source

                word_stats[group_key]["titles"][source_id].append(
                    {
                        "title": title,
                        "source_name": source_name,
                        "first_time": first_time,
                        "last_time": last_time,
                        "time_display": time_display,
                        "count": count_info,
                        "ranks": ranks,
                        "rank_threshold": rank_threshold,
                        "url": url,
                        "mobileUrl": mobile_url,
                        "is_new": is_new,
                    }
                )

                if source_id not in processed_titles:
                    processed_titles[source_id] = {}
                processed_titles[source_id][title] = True

                break

    # 最後統一打印匯總信息
    if mode == "incremental":
        if is_first_today:
            total_input_news = sum(len(titles) for titles in results.values())
            filter_status = (
                "全部顯示"
                if len(word_groups) == 1 and word_groups[0]["group_key"] == "全部新聞"
                else "頻率詞匹配"
            )
            print(
                f"增量模式：當天第一次爬取，{total_input_news} 條新聞中有 {matched_new_count} 條{filter_status}"
            )
        else:
            if new_titles:
                total_new_count = sum(len(titles) for titles in new_titles.values())
                filter_status = (
                    "全部顯示"
                    if len(word_groups) == 1
                    and word_groups[0]["group_key"] == "全部新聞"
                    else "匹配頻率詞"
                )
                print(
                    f"增量模式：{total_new_count} 條新增新聞中，有 {matched_new_count} 條{filter_status}"
                )
                if matched_new_count == 0 and len(word_groups) > 1:
                    print("增量模式：沒有新增新聞匹配頻率詞，將不會發送通知")
            else:
                print("增量模式：未檢測到新增新聞")
    elif mode == "current":
        total_input_news = sum(len(titles) for titles in results_to_process.values())
        if is_first_today:
            filter_status = (
                "全部顯示"
                if len(word_groups) == 1 and word_groups[0]["group_key"] == "全部新聞"
                else "頻率詞匹配"
            )
            print(
                f"當前榜單模式：當天第一次爬取，{total_input_news} 條當前榜單新聞中有 {matched_new_count} 條{filter_status}"
            )
        else:
            matched_count = sum(stat["count"] for stat in word_stats.values())
            filter_status = (
                "全部顯示"
                if len(word_groups) == 1 and word_groups[0]["group_key"] == "全部新聞"
                else "頻率詞匹配"
            )
            print(
                f"當前榜單模式：{total_input_news} 條當前榜單新聞中有 {matched_count} 條{filter_status}"
            )

    stats = []
    for group_key, data in word_stats.items():
        all_titles = []
        for source_id, title_list in data["titles"].items():
            all_titles.extend(title_list)

        # 按權重排序
        sorted_titles = sorted(
            all_titles,
            key=lambda x: (
                -calculate_news_weight(x, rank_threshold),
                min(x["ranks"]) if x["ranks"] else 999,
                -x["count"],
            ),
        )

        stats.append(
            {
                "word": group_key,
                "count": data["count"],
                "titles": sorted_titles,
                "percentage": (
                    round(data["count"] / total_titles * 100, 2)
                    if total_titles > 0
                    else 0
                ),
            }
        )

    stats.sort(key=lambda x: x["count"], reverse=True)
    return stats, total_titles


# === 報告生成 ===
def prepare_report_data(
    stats: List[Dict],
    failed_ids: Optional[List] = None,
    new_titles: Optional[Dict] = None,
    id_to_name: Optional[Dict] = None,
    mode: str = "daily",
) -> Dict:
    """準備報告數據"""
    processed_new_titles = []

    # 在增量模式下隱藏新增新聞區域
    hide_new_section = mode == "incremental"

    # 只有在非隱藏模式下才處理新增新聞部分
    if not hide_new_section:
        filtered_new_titles = {}
        if new_titles and id_to_name:
            word_groups, filter_words = load_frequency_words()
            for source_id, titles_data in new_titles.items():
                filtered_titles = {}
                for title, title_data in titles_data.items():
                    if matches_word_groups(title, word_groups, filter_words):
                        filtered_titles[title] = title_data
                if filtered_titles:
                    filtered_new_titles[source_id] = filtered_titles

        if filtered_new_titles and id_to_name:
            for source_id, titles_data in filtered_new_titles.items():
                source_name = id_to_name.get(source_id, source_id)
                source_titles = []

                for title, title_data in titles_data.items():
                    url = title_data.get("url", "")
                    mobile_url = title_data.get("mobileUrl", "")
                    ranks = title_data.get("ranks", [])

                    processed_title = {
                        "title": title,
                        "source_name": source_name,
                        "time_display": "",
                        "count": 1,
                        "ranks": ranks,
                        "rank_threshold": CONFIG["RANK_THRESHOLD"],
                        "url": url,
                        "mobile_url": mobile_url,
                        "is_new": True,
                    }
                    source_titles.append(processed_title)

                if source_titles:
                    processed_new_titles.append(
                        {
                            "source_id": source_id,
                            "source_name": source_name,
                            "titles": source_titles,
                        }
                    )

    processed_stats = []
    for stat in stats:
        if stat["count"] <= 0:
            continue

        processed_titles = []
        for title_data in stat["titles"]:
            processed_title = {
                "title": title_data["title"],
                "source_name": title_data["source_name"],
                "time_display": title_data["time_display"],
                "count": title_data["count"],
                "ranks": title_data["ranks"],
                "rank_threshold": title_data["rank_threshold"],
                "url": title_data.get("url", ""),
                "mobile_url": title_data.get("mobileUrl", ""),
                "is_new": title_data.get("is_new", False),
            }
            processed_titles.append(processed_title)

        processed_stats.append(
            {
                "word": stat["word"],
                "count": stat["count"],
                "percentage": stat.get("percentage", 0),
                "titles": processed_titles,
            }
        )

    return {
        "stats": processed_stats,
        "new_titles": processed_new_titles,
        "failed_ids": failed_ids or [],
        "total_new_count": sum(
            len(source["titles"]) for source in processed_new_titles
        ),
    }


def format_title_for_platform(
    platform: str, title_data: Dict, show_source: bool = True
) -> str:
    """統一的標題格式化方法"""
    rank_display = format_rank_display(
        title_data["ranks"], title_data["rank_threshold"], platform
    )

    link_url = title_data["mobile_url"] or title_data["url"]

    cleaned_title = clean_title(title_data["title"])

    if platform == "feishu":
        if link_url:
            formatted_title = f"[{cleaned_title}]({link_url})"
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"<font color='grey'>[{title_data['source_name']}]</font> {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" <font color='grey'>- {title_data['time_display']}</font>"
        if title_data["count"] > 1:
            result += f" <font color='green'>({title_data['count']}次)</font>"

        return result

    elif platform == "dingtalk":
        if link_url:
            formatted_title = f"[{cleaned_title}]({link_url})"
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"[{title_data['source_name']}] {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" - {title_data['time_display']}"
        if title_data["count"] > 1:
            result += f" ({title_data['count']}次)"

        return result

    elif platform == "wework":
        if link_url:
            formatted_title = f"[{cleaned_title}]({link_url})"
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"[{title_data['source_name']}] {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" - {title_data['time_display']}"
        if title_data["count"] > 1:
            result += f" ({title_data['count']}次)"

        return result

    elif platform == "telegram":
        if link_url:
            formatted_title = f'<a href="{link_url}">{html_escape(cleaned_title)}</a>'
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"[{title_data['source_name']}] {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" <code>- {title_data['time_display']}</code>"
        if title_data["count"] > 1:
            result += f" <code>({title_data['count']}次)</code>"

        return result

    elif platform == "html":
        rank_display = format_rank_display(
            title_data["ranks"], title_data["rank_threshold"], "html"
        )

        link_url = title_data["mobile_url"] or title_data["url"]

        escaped_title = html_escape(cleaned_title)
        escaped_source_name = html_escape(title_data["source_name"])

        if link_url:
            escaped_url = html_escape(link_url)
            formatted_title = f'[{escaped_source_name}] <a href="{escaped_url}" target="_blank" class="news-link">{escaped_title}</a>'
        else:
            formatted_title = (
                f'[{escaped_source_name}] <span class="no-link">{escaped_title}</span>'
            )

        if rank_display:
            formatted_title += f" {rank_display}"
        if title_data["time_display"]:
            escaped_time = html_escape(title_data["time_display"])
            formatted_title += f" <font color='grey'>- {escaped_time}</font>"
        if title_data["count"] > 1:
            formatted_title += f" <font color='green'>({title_data['count']}次)</font>"

        if title_data.get("is_new"):
            formatted_title = f"<div class='new-title'>🆕 {formatted_title}</div>"

        return formatted_title

    else:
        return cleaned_title


def generate_html_report(
    stats: List[Dict],
    total_titles: int,
    failed_ids: Optional[List] = None,
    new_titles: Optional[Dict] = None,
    id_to_name: Optional[Dict] = None,
    mode: str = "daily",
    is_daily_summary: bool = False,
) -> str:
    """生成HTML報告"""
    if is_daily_summary:
        if mode == "current":
            filename = "當前榜單匯總.html"
        elif mode == "incremental":
            filename = "當日增量.html"
        else:
            filename = "當日匯總.html"
    else:
        filename = f"{format_time_filename()}.html"

    file_path = get_output_path("html", filename)

    report_data = prepare_report_data(stats, failed_ids, new_titles, id_to_name, mode)

    html_content = render_html_content(
        report_data, total_titles, is_daily_summary, mode
    )

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    if is_daily_summary:
        root_file_path = Path("index.html")
        with open(root_file_path, "w", encoding="utf-8") as f:
            f.write(html_content)

    return file_path


def render_html_content(
    report_data: Dict,
    total_titles: int,
    is_daily_summary: bool = False,
    mode: str = "daily",
) -> str:
    """渲染HTML內容"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>熱點新聞分析</title>
        <style>
            * { box-sizing: border-box; }
            body { 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
                margin: 0; 
                padding: 16px; 
                background: #fafafa;
                color: #333;
                line-height: 1.5;
            }
            
            .container {
                max-width: 600px;
                margin: 0 auto;
                background: white;
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 2px 16px rgba(0,0,0,0.06);
            }
            
            .header {
                background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
                color: white;
                padding: 32px 24px;
                text-align: center;
            }
            
            .header-title {
                font-size: 22px;
                font-weight: 700;
                margin: 0 0 20px 0;
            }
            
            .header-info {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 16px;
                font-size: 14px;
                opacity: 0.95;
            }
            
            .info-item {
                text-align: center;
            }
            
            .info-label {
                display: block;
                font-size: 12px;
                opacity: 0.8;
                margin-bottom: 4px;
            }
            
            .info-value {
                font-weight: 600;
                font-size: 16px;
            }
            
            .content {
                padding: 24px;
            }
            
            .word-group {
                margin-bottom: 40px;
            }
            
            .word-group:first-child {
                margin-top: 0;
            }
            
            .word-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 20px;
                padding-bottom: 8px;
                border-bottom: 1px solid #f0f0f0;
            }
            
            .word-info {
                display: flex;
                align-items: center;
                gap: 12px;
            }
            
            .word-name {
                font-size: 17px;
                font-weight: 600;
                color: #1a1a1a;
            }
            
            .word-count {
                color: #666;
                font-size: 13px;
                font-weight: 500;
            }
            
            .word-count.hot { color: #dc2626; font-weight: 600; }
            .word-count.warm { color: #ea580c; font-weight: 600; }
            
            .word-index {
                color: #999;
                font-size: 12px;
            }
            
            .news-item {
                margin-bottom: 20px;
                padding: 16px 0;
                border-bottom: 1px solid #f5f5f5;
                position: relative;
                display: flex;
                gap: 12px;
                align-items: center;
            }
            
            .news-item:last-child {
                border-bottom: none;
            }
            
            .news-item.new::after {
                content: "NEW";
                position: absolute;
                top: 12px;
                right: 0;
                background: #fbbf24;
                color: #92400e;
                font-size: 9px;
                font-weight: 700;
                padding: 3px 6px;
                border-radius: 4px;
                letter-spacing: 0.5px;
            }
            
            .news-number {
                color: #999;
                font-size: 13px;
                font-weight: 600;
                min-width: 20px;
                text-align: center;
                flex-shrink: 0;
                background: #f8f9fa;
                border-radius: 50%;
                width: 24px;
                height: 24px;
                display: flex;
                align-items: center;
                justify-content: center;
                align-self: flex-start;
                margin-top: 8px;
            }
            
            .news-content {
                flex: 1;
                min-width: 0;
                padding-right: 40px;
            }
            
            .news-item.new .news-content {
                padding-right: 50px;
            }
            
            .news-header {
                display: flex;
                align-items: center;
                gap: 8px;
                margin-bottom: 8px;
                flex-wrap: wrap;
            }
            
            .source-name {
                color: #666;
                font-size: 12px;
                font-weight: 500;
            }
            
            .rank-num {
                color: #fff;
                background: #6b7280;
                font-size: 10px;
                font-weight: 700;
                padding: 2px 6px;
                border-radius: 10px;
                min-width: 18px;
                text-align: center;
            }
            
            .rank-num.top { background: #dc2626; }
            .rank-num.high { background: #ea580c; }
            
            .time-info {
                color: #999;
                font-size: 11px;
            }
            
            .count-info {
                color: #059669;
                font-size: 11px;
                font-weight: 500;
            }
            
            .news-title {
                font-size: 15px;
                line-height: 1.4;
                color: #1a1a1a;
                margin: 0;
            }
            
            .news-link {
                color: #2563eb;
                text-decoration: none;
            }
            
            .news-link:hover {
                text-decoration: underline;
            }
            
            .news-link:visited {
                color: #7c3aed;
            }
            
            .new-section {
                margin-top: 40px;
                padding-top: 24px;
                border-top: 2px solid #f0f0f0;
            }
            
            .new-section-title {
                color: #1a1a1a;
                font-size: 16px;
                font-weight: 600;
                margin: 0 0 20px 0;
            }
            
            .new-source-group {
                margin-bottom: 24px;
            }
            
            .new-source-title {
                color: #666;
                font-size: 13px;
                font-weight: 500;
                margin: 0 0 12px 0;
                padding-bottom: 6px;
                border-bottom: 1px solid #f5f5f5;
            }
            
            .new-item {
                display: flex;
                align-items: center;
                gap: 12px;
                padding: 8px 0;
                border-bottom: 1px solid #f9f9f9;
            }
            
            .new-item:last-child {
                border-bottom: none;
            }
            
            .new-item-number {
                color: #999;
                font-size: 12px;
                font-weight: 600;
                min-width: 18px;
                text-align: center;
                flex-shrink: 0;
                background: #f8f9fa;
                border-radius: 50%;
                width: 20px;
                height: 20px;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            
            .new-item-rank {
                color: #fff;
                background: #6b7280;
                font-size: 10px;
                font-weight: 700;
                padding: 3px 6px;
                border-radius: 8px;
                min-width: 20px;
                text-align: center;
                flex-shrink: 0;
            }
            
            .new-item-rank.top { background: #dc2626; }
            .new-item-rank.high { background: #ea580c; }
            
            .new-item-content {
                flex: 1;
                min-width: 0;
            }
            
            .new-item-title {
                font-size: 14px;
                line-height: 1.4;
                color: #1a1a1a;
                margin: 0;
            }
            
            .error-section {
                background: #fef2f2;
                border: 1px solid #fecaca;
                border-radius: 8px;
                padding: 16px;
                margin-bottom: 24px;
            }
            
            .error-title {
                color: #dc2626;
                font-size: 14px;
                font-weight: 600;
                margin: 0 0 8px 0;
            }
            
            .error-list {
                list-style: none;
                padding: 0;
                margin: 0;
            }
            
            .error-item {
                color: #991b1b;
                font-size: 13px;
                padding: 2px 0;
                font-family: 'SF Mono', Consolas, monospace;
            }
            
            @media (max-width: 480px) {
                body { padding: 12px; }
                .header { padding: 24px 20px; }
                .content { padding: 20px; }
                .header-info { grid-template-columns: 1fr; gap: 12px; }
                .news-header { gap: 6px; }
                .news-content { padding-right: 45px; }
                .news-item { gap: 8px; }
                .new-item { gap: 8px; }
                .news-number { width: 20px; height: 20px; font-size: 12px; }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="header-title">熱點新聞分析</div>
                <div class="header-info">
                    <div class="info-item">
                        <span class="info-label">報告類型</span>
                        <span class="info-value">"""

    # 處理報告類型顯示
    if is_daily_summary:
        if mode == "current":
            html += "當前榜單"
        elif mode == "incremental":
            html += "增量模式"
        else:
            html += "當日匯總"
    else:
        html += "實時分析"

    html += """</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">新聞總數</span>
                        <span class="info-value">"""
    
    html += f"{total_titles} 條"
    
    # 計算篩選後的熱點新聞數量
    hot_news_count = sum(len(stat["titles"]) for stat in report_data["stats"])
    
    html += """</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">熱點新聞</span>
                        <span class="info-value">"""
    
    html += f"{hot_news_count} 條"

    html += """</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">生成時間</span>
                        <span class="info-value">"""

    now = get_beijing_time()
    html += now.strftime('%m-%d %H:%M')

    html += """</span>
                    </div>
                </div>
            </div>
            
            <div class="content">"""

    # 處理失敗ID錯誤信息
    if report_data["failed_ids"]:
        html += """
                <div class="error-section">
                    <div class="error-title">⚠️ 請求失敗的平台</div>
                    <ul class="error-list">"""
        for id_value in report_data["failed_ids"]:
            html += f'<li class="error-item">{html_escape(id_value)}</li>'
        html += """
                    </ul>
                </div>"""

    # 處理主要統計數據
    if report_data["stats"]:
        total_count = len(report_data["stats"])
        
        for i, stat in enumerate(report_data["stats"], 1):
            count = stat["count"]
            
            # 確定熱度等級
            if count >= 10:
                count_class = "hot"
            elif count >= 5:
                count_class = "warm"
            else:
                count_class = ""

            escaped_word = html_escape(stat["word"])
            
            html += f"""
                <div class="word-group">
                    <div class="word-header">
                        <div class="word-info">
                            <div class="word-name">{escaped_word}</div>
                            <div class="word-count {count_class}">{count} 條</div>
                        </div>
                        <div class="word-index">{i}/{total_count}</div>
                    </div>"""

            # 處理每個詞組下的新聞標題，給每條新聞標上序號
            for j, title_data in enumerate(stat["titles"], 1):
                is_new = title_data.get("is_new", False)
                new_class = "new" if is_new else ""
                
                html += f"""
                    <div class="news-item {new_class}">
                        <div class="news-number">{j}</div>
                        <div class="news-content">
                            <div class="news-header">
                                <span class="source-name">{html_escape(title_data["source_name"])}</span>"""
                
                # 處理排名顯示
                ranks = title_data.get("ranks", [])
                if ranks:
                    min_rank = min(ranks)
                    max_rank = max(ranks)
                    rank_threshold = title_data.get("rank_threshold", 10)
                    
                    # 確定排名等級
                    if min_rank <= 3:
                        rank_class = "top"
                    elif min_rank <= rank_threshold:
                        rank_class = "high" 
                    else:
                        rank_class = ""
                    
                    if min_rank == max_rank:
                        rank_text = str(min_rank)
                    else:
                        rank_text = f"{min_rank}-{max_rank}"
                        
                    html += f'<span class="rank-num {rank_class}">{rank_text}</span>'
                
                # 處理時間顯示
                time_display = title_data.get("time_display", "")
                if time_display:
                    # 簡化時間顯示格式，將波浪線替換為~
                    simplified_time = time_display.replace(" ~ ", "~").replace("[", "").replace("]", "")
                    html += f'<span class="time-info">{html_escape(simplified_time)}</span>'
                
                # 處理出現次數
                count_info = title_data.get("count", 1)
                if count_info > 1:
                    html += f'<span class="count-info">{count_info}次</span>'
                
                html += """
                            </div>
                            <div class="news-title">"""
                
                # 處理標題和鏈接
                escaped_title = html_escape(title_data["title"])
                link_url = title_data.get("mobile_url") or title_data.get("url", "")
                
                if link_url:
                    escaped_url = html_escape(link_url)
                    html += f'<a href="{escaped_url}" target="_blank" class="news-link">{escaped_title}</a>'
                else:
                    html += escaped_title
                
                html += """
                            </div>
                        </div>
                    </div>"""

            html += """
                </div>"""

    # 處理新增新聞區域
    if report_data["new_titles"]:
        html += f"""
                <div class="new-section">
                    <div class="new-section-title">本次新增熱點 (共 {report_data['total_new_count']} 條)</div>"""

        for source_data in report_data["new_titles"]:
            escaped_source = html_escape(source_data["source_name"])
            titles_count = len(source_data["titles"])
            
            html += f"""
                    <div class="new-source-group">
                        <div class="new-source-title">{escaped_source} · {titles_count}條</div>"""

            # 為新增新聞也添加序號
            for idx, title_data in enumerate(source_data["titles"], 1):
                ranks = title_data.get("ranks", [])
                
                # 處理新增新聞的排名顯示
                rank_class = ""
                if ranks:
                    min_rank = min(ranks)
                    if min_rank <= 3:
                        rank_class = "top"
                    elif min_rank <= title_data.get("rank_threshold", 10):
                        rank_class = "high"
                    
                    if len(ranks) == 1:
                        rank_text = str(ranks[0])
                    else:
                        rank_text = f"{min(ranks)}-{max(ranks)}"
                else:
                    rank_text = "?"

                html += f"""
                        <div class="new-item">
                            <div class="new-item-number">{idx}</div>
                            <div class="new-item-rank {rank_class}">{rank_text}</div>
                            <div class="new-item-content">
                                <div class="new-item-title">"""
                
                # 處理新增新聞的鏈接
                escaped_title = html_escape(title_data["title"])
                link_url = title_data.get("mobile_url") or title_data.get("url", "")
                
                if link_url:
                    escaped_url = html_escape(link_url)
                    html += f'<a href="{escaped_url}" target="_blank" class="news-link">{escaped_title}</a>'
                else:
                    html += escaped_title
                
                html += """
                                </div>
                            </div>
                        </div>"""

            html += """
                    </div>"""

        html += """
                </div>"""

    html += """
            </div>
        </div>
    </body>
    </html>
    """

    return html


def render_feishu_content(
    report_data: Dict, update_info: Optional[Dict] = None, mode: str = "daily"
) -> str:
    """渲染飛書內容"""
    text_content = ""

    if report_data["stats"]:
        text_content += f"📊 **熱點詞彙統計**\n\n"

    total_count = len(report_data["stats"])

    for i, stat in enumerate(report_data["stats"]):
        word = stat["word"]
        count = stat["count"]

        sequence_display = f"<font color='grey'>[{i + 1}/{total_count}]</font>"

        if count >= 10:
            text_content += f"🔥 {sequence_display} **{word}** : <font color='red'>{count}</font> 條\n\n"
        elif count >= 5:
            text_content += f"📈 {sequence_display} **{word}** : <font color='orange'>{count}</font> 條\n\n"
        else:
            text_content += f"📌 {sequence_display} **{word}** : {count} 條\n\n"

        for j, title_data in enumerate(stat["titles"], 1):
            formatted_title = format_title_for_platform(
                "feishu", title_data, show_source=True
            )
            text_content += f"  {j}. {formatted_title}\n"

            if j < len(stat["titles"]):
                text_content += "\n"

        if i < len(report_data["stats"]) - 1:
            text_content += f"\n{CONFIG['FEISHU_MESSAGE_SEPARATOR']}\n\n"

    if not text_content:
        if mode == "incremental":
            mode_text = "增量模式下暫無新增匹配的熱點詞彙"
        elif mode == "current":
            mode_text = "當前榜單模式下暫無匹配的熱點詞彙"
        else:
            mode_text = "暫無匹配的熱點詞彙"
        text_content = f"📭 {mode_text}\n\n"

    if report_data["new_titles"]:
        if text_content and "暫無匹配" not in text_content:
            text_content += f"\n{CONFIG['FEISHU_MESSAGE_SEPARATOR']}\n\n"

        text_content += (
            f"🆕 **本次新增熱點新聞** (共 {report_data['total_new_count']} 條)\n\n"
        )

        for source_data in report_data["new_titles"]:
            text_content += (
                f"**{source_data['source_name']}** ({len(source_data['titles'])} 條):\n"
            )

            for j, title_data in enumerate(source_data["titles"], 1):
                title_data_copy = title_data.copy()
                title_data_copy["is_new"] = False
                formatted_title = format_title_for_platform(
                    "feishu", title_data_copy, show_source=False
                )
                text_content += f"  {j}. {formatted_title}\n"

            text_content += "\n"

    if report_data["failed_ids"]:
        if text_content and "暫無匹配" not in text_content:
            text_content += f"\n{CONFIG['FEISHU_MESSAGE_SEPARATOR']}\n\n"

        text_content += "⚠️ **數據獲取失敗的平台：**\n\n"
        for i, id_value in enumerate(report_data["failed_ids"], 1):
            text_content += f"  ‧ <font color='red'>{id_value}</font>\n"

    now = get_beijing_time()
    text_content += (
        f"\n\n<font color='grey'>更新時間：{now.strftime('%Y-%m-%d %H:%M:%S')}</font>"
    )

    if update_info:
        text_content += f"\n<font color='grey'>TrendRadar 發現新版本 {update_info['remote_version']}，當前 {update_info['current_version']}</font>"

    return text_content


def render_dingtalk_content(
    report_data: Dict, update_info: Optional[Dict] = None, mode: str = "daily"
) -> str:
    """渲染釘釘內容"""
    text_content = ""

    total_titles = sum(
        len(stat["titles"]) for stat in report_data["stats"] if stat["count"] > 0
    )
    now = get_beijing_time()

    text_content += f"**總新聞數：** {total_titles}\n\n"
    text_content += f"**時間：** {now.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    text_content += f"**類型：** 熱點分析報告\n\n"

    text_content += "---\n\n"

    if report_data["stats"]:
        text_content += f"📊 **熱點詞彙統計**\n\n"

        total_count = len(report_data["stats"])

        for i, stat in enumerate(report_data["stats"]):
            word = stat["word"]
            count = stat["count"]

            sequence_display = f"[{i + 1}/{total_count}]"

            if count >= 10:
                text_content += f"🔥 {sequence_display} **{word}** : **{count}** 條\n\n"
            elif count >= 5:
                text_content += f"📈 {sequence_display} **{word}** : **{count}** 條\n\n"
            else:
                text_content += f"📌 {sequence_display} **{word}** : {count} 條\n\n"

            for j, title_data in enumerate(stat["titles"], 1):
                formatted_title = format_title_for_platform(
                    "dingtalk", title_data, show_source=True
                )
                text_content += f"  {j}. {formatted_title}\n"

                if j < len(stat["titles"]):
                    text_content += "\n"

            if i < len(report_data["stats"]) - 1:
                text_content += f"\n---\n\n"

    if not report_data["stats"]:
        if mode == "incremental":
            mode_text = "增量模式下暫無新增匹配的熱點詞彙"
        elif mode == "current":
            mode_text = "當前榜單模式下暫無匹配的熱點詞彙"
        else:
            mode_text = "暫無匹配的熱點詞彙"
        text_content += f"📭 {mode_text}\n\n"

    if report_data["new_titles"]:
        if text_content and "暫無匹配" not in text_content:
            text_content += f"\n---\n\n"

        text_content += (
            f"🆕 **本次新增熱點新聞** (共 {report_data['total_new_count']} 條)\n\n"
        )

        for source_data in report_data["new_titles"]:
            text_content += f"**{source_data['source_name']}** ({len(source_data['titles'])} 條):\n\n"

            for j, title_data in enumerate(source_data["titles"], 1):
                title_data_copy = title_data.copy()
                title_data_copy["is_new"] = False
                formatted_title = format_title_for_platform(
                    "dingtalk", title_data_copy, show_source=False
                )
                text_content += f"  {j}. {formatted_title}\n"

            text_content += "\n"

    if report_data["failed_ids"]:
        if text_content and "暫無匹配" not in text_content:
            text_content += f"\n---\n\n"

        text_content += "⚠️ **數據獲取失敗的平台：**\n\n"
        for i, id_value in enumerate(report_data["failed_ids"], 1):
            text_content += f"  ‧ **{id_value}**\n"

    text_content += f"\n\n> 更新時間：{now.strftime('%Y-%m-%d %H:%M:%S')}"

    if update_info:
        text_content += f"\n> TrendRadar 發現新版本 **{update_info['remote_version']}**，當前 **{update_info['current_version']}**"

    return text_content


def split_content_into_batches(
    report_data: Dict,
    format_type: str,
    update_info: Optional[Dict] = None,
    max_bytes: int = CONFIG["MESSAGE_BATCH_SIZE"],
    mode: str = "daily",
) -> List[str]:
    """分批處理消息內容，確保詞組標題+至少第一條新聞的完整性"""
    batches = []

    total_titles = sum(
        len(stat["titles"]) for stat in report_data["stats"] if stat["count"] > 0
    )
    now = get_beijing_time()

    base_header = ""
    if format_type == "wework":
        base_header = f"**總新聞數：** {total_titles}\n\n\n\n"
    elif format_type == "telegram":
        base_header = f"總新聞數： {total_titles}\n\n"

    base_footer = ""
    if format_type == "wework":
        base_footer = f"\n\n\n> 更新時間：{now.strftime('%Y-%m-%d %H:%M:%S')}"
        if update_info:
            base_footer += f"\n> TrendRadar 發現新版本 **{update_info['remote_version']}**，當前 **{update_info['current_version']}**"
    elif format_type == "telegram":
        base_footer = f"\n\n更新時間：{now.strftime('%Y-%m-%d %H:%M:%S')}"
        if update_info:
            base_footer += f"\nTrendRadar 發現新版本 {update_info['remote_version']}，當前 {update_info['current_version']}"

    stats_header = ""
    if report_data["stats"]:
        if format_type == "wework":
            stats_header = f"📊 **熱點詞彙統計**\n\n"
        elif format_type == "telegram":
            stats_header = f"📊 熱點詞彙統計\n\n"

    current_batch = base_header
    current_batch_has_content = False

    if (
        not report_data["stats"]
        and not report_data["new_titles"]
        and not report_data["failed_ids"]
    ):
        if mode == "incremental":
            mode_text = "增量模式下暫無新增匹配的熱點詞彙"
        elif mode == "current":
            mode_text = "當前榜單模式下暫無匹配的熱點詞彙"
        else:
            mode_text = "暫無匹配的熱點詞彙"
        simple_content = f"📭 {mode_text}\n\n"
        final_content = base_header + simple_content + base_footer
        batches.append(final_content)
        return batches

    # 處理熱點詞彙統計
    if report_data["stats"]:
        total_count = len(report_data["stats"])

        # 添加統計標題
        test_content = current_batch + stats_header
        if (
            len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
            < max_bytes
        ):
            current_batch = test_content
            current_batch_has_content = True
        else:
            if current_batch_has_content:
                batches.append(current_batch + base_footer)
            current_batch = base_header + stats_header
            current_batch_has_content = True

        # 逐個處理詞組（確保詞組標題+第一條新聞的原子性）
        for i, stat in enumerate(report_data["stats"]):
            word = stat["word"]
            count = stat["count"]
            sequence_display = f"[{i + 1}/{total_count}]"

            # 構建詞組標題
            word_header = ""
            if format_type == "wework":
                if count >= 10:
                    word_header = (
                        f"🔥 {sequence_display} **{word}** : **{count}** 條\n\n"
                    )
                elif count >= 5:
                    word_header = (
                        f"📈 {sequence_display} **{word}** : **{count}** 條\n\n"
                    )
                else:
                    word_header = f"📌 {sequence_display} **{word}** : {count} 條\n\n"
            elif format_type == "telegram":
                if count >= 10:
                    word_header = f"🔥 {sequence_display} {word} : {count} 條\n\n"
                elif count >= 5:
                    word_header = f"📈 {sequence_display} {word} : {count} 條\n\n"
                else:
                    word_header = f"📌 {sequence_display} {word} : {count} 條\n\n"

            # 構建第一條新聞
            first_news_line = ""
            if stat["titles"]:
                first_title_data = stat["titles"][0]
                if format_type == "wework":
                    formatted_title = format_title_for_platform(
                        "wework", first_title_data, show_source=True
                    )
                elif format_type == "telegram":
                    formatted_title = format_title_for_platform(
                        "telegram", first_title_data, show_source=True
                    )
                else:
                    formatted_title = f"{first_title_data['title']}"

                first_news_line = f"  1. {formatted_title}\n"
                if len(stat["titles"]) > 1:
                    first_news_line += "\n"

            # 原子性檢查：詞組標題+第一條新聞必須一起處理
            word_with_first_news = word_header + first_news_line
            test_content = current_batch + word_with_first_news

            if (
                len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
                >= max_bytes
            ):
                # 當前批次容納不下，開啟新批次
                if current_batch_has_content:
                    batches.append(current_batch + base_footer)
                current_batch = base_header + stats_header + word_with_first_news
                current_batch_has_content = True
                start_index = 1
            else:
                current_batch = test_content
                current_batch_has_content = True
                start_index = 1

            # 處理剩餘新聞條目
            for j in range(start_index, len(stat["titles"])):
                title_data = stat["titles"][j]
                if format_type == "wework":
                    formatted_title = format_title_for_platform(
                        "wework", title_data, show_source=True
                    )
                elif format_type == "telegram":
                    formatted_title = format_title_for_platform(
                        "telegram", title_data, show_source=True
                    )
                else:
                    formatted_title = f"{title_data['title']}"

                news_line = f"  {j + 1}. {formatted_title}\n"
                if j < len(stat["titles"]) - 1:
                    news_line += "\n"

                test_content = current_batch + news_line
                if (
                    len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
                    >= max_bytes
                ):
                    if current_batch_has_content:
                        batches.append(current_batch + base_footer)
                    current_batch = base_header + stats_header + word_header + news_line
                    current_batch_has_content = True
                else:
                    current_batch = test_content
                    current_batch_has_content = True

            # 詞組間分隔符
            if i < len(report_data["stats"]) - 1:
                separator = ""
                if format_type == "wework":
                    separator = f"\n\n\n\n"
                elif format_type == "telegram":
                    separator = f"\n\n"

                test_content = current_batch + separator
                if (
                    len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
                    < max_bytes
                ):
                    current_batch = test_content

    # 處理新增新聞（同樣確保來源標題+第一條新聞的原子性）
    if report_data["new_titles"]:
        new_header = ""
        if format_type == "wework":
            new_header = f"\n\n\n\n🆕 **本次新增熱點新聞** (共 {report_data['total_new_count']} 條)\n\n"
        elif format_type == "telegram":
            new_header = (
                f"\n\n🆕 本次新增熱點新聞 (共 {report_data['total_new_count']} 條)\n\n"
            )

        test_content = current_batch + new_header
        if (
            len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
            >= max_bytes
        ):
            if current_batch_has_content:
                batches.append(current_batch + base_footer)
            current_batch = base_header + new_header
            current_batch_has_content = True
        else:
            current_batch = test_content
            current_batch_has_content = True

        # 逐個處理新增新聞來源
        for source_data in report_data["new_titles"]:
            source_header = ""
            if format_type == "wework":
                source_header = f"**{source_data['source_name']}** ({len(source_data['titles'])} 條):\n\n"
            elif format_type == "telegram":
                source_header = f"{source_data['source_name']} ({len(source_data['titles'])} 條):\n\n"

            # 構建第一條新增新聞
            first_news_line = ""
            if source_data["titles"]:
                first_title_data = source_data["titles"][0]
                title_data_copy = first_title_data.copy()
                title_data_copy["is_new"] = False

                if format_type == "wework":
                    formatted_title = format_title_for_platform(
                        "wework", title_data_copy, show_source=False
                    )
                elif format_type == "telegram":
                    formatted_title = format_title_for_platform(
                        "telegram", title_data_copy, show_source=False
                    )
                else:
                    formatted_title = f"{title_data_copy['title']}"

                first_news_line = f"  1. {formatted_title}\n"

            # 原子性檢查：來源標題+第一條新聞
            source_with_first_news = source_header + first_news_line
            test_content = current_batch + source_with_first_news

            if (
                len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
                >= max_bytes
            ):
                if current_batch_has_content:
                    batches.append(current_batch + base_footer)
                current_batch = base_header + new_header + source_with_first_news
                current_batch_has_content = True
                start_index = 1
            else:
                current_batch = test_content
                current_batch_has_content = True
                start_index = 1

            # 處理剩餘新增新聞
            for j in range(start_index, len(source_data["titles"])):
                title_data = source_data["titles"][j]
                title_data_copy = title_data.copy()
                title_data_copy["is_new"] = False

                if format_type == "wework":
                    formatted_title = format_title_for_platform(
                        "wework", title_data_copy, show_source=False
                    )
                elif format_type == "telegram":
                    formatted_title = format_title_for_platform(
                        "telegram", title_data_copy, show_source=False
                    )
                else:
                    formatted_title = f"{title_data_copy['title']}"

                news_line = f"  {j + 1}. {formatted_title}\n"

                test_content = current_batch + news_line
                if (
                    len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
                    >= max_bytes
                ):
                    if current_batch_has_content:
                        batches.append(current_batch + base_footer)
                    current_batch = base_header + new_header + source_header + news_line
                    current_batch_has_content = True
                else:
                    current_batch = test_content
                    current_batch_has_content = True

            current_batch += "\n"

    if report_data["failed_ids"]:
        failed_header = ""
        if format_type == "wework":
            failed_header = f"\n\n\n\n⚠️ **數據獲取失敗的平台：**\n\n"
        elif format_type == "telegram":
            failed_header = f"\n\n⚠️ 數據獲取失敗的平台：\n\n"

        test_content = current_batch + failed_header
        if (
            len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
            >= max_bytes
        ):
            if current_batch_has_content:
                batches.append(current_batch + base_footer)
            current_batch = base_header + failed_header
            current_batch_has_content = True
        else:
            current_batch = test_content
            current_batch_has_content = True

        for i, id_value in enumerate(report_data["failed_ids"], 1):
            failed_line = f"  ‧ {id_value}\n"
            test_content = current_batch + failed_line
            if (
                len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
                >= max_bytes
            ):
                if current_batch_has_content:
                    batches.append(current_batch + base_footer)
                current_batch = base_header + failed_header + failed_line
                current_batch_has_content = True
            else:
                current_batch = test_content
                current_batch_has_content = True

    # 完成最後批次
    if current_batch_has_content:
        batches.append(current_batch + base_footer)

    return batches


def send_to_webhooks(
    stats: List[Dict],
    failed_ids: Optional[List] = None,
    report_type: str = "當日匯總",
    new_titles: Optional[Dict] = None,
    id_to_name: Optional[Dict] = None,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
) -> Dict[str, bool]:
    """發送數據到多個webhook平台"""
    results = {}

    report_data = prepare_report_data(stats, failed_ids, new_titles, id_to_name, mode)

    feishu_url = CONFIG["FEISHU_WEBHOOK_URL"]
    dingtalk_url = CONFIG["DINGTALK_WEBHOOK_URL"]
    wework_url = CONFIG["WEWORK_WEBHOOK_URL"]
    telegram_token = CONFIG["TELEGRAM_BOT_TOKEN"]
    telegram_chat_id = CONFIG["TELEGRAM_CHAT_ID"]

    update_info_to_send = update_info if CONFIG["SHOW_VERSION_UPDATE"] else None

    # 發送到飛書
    if feishu_url:
        results["feishu"] = send_to_feishu(
            feishu_url, report_data, report_type, update_info_to_send, proxy_url, mode
        )

    # 發送到釘釘
    if dingtalk_url:
        results["dingtalk"] = send_to_dingtalk(
            dingtalk_url, report_data, report_type, update_info_to_send, proxy_url, mode
        )

    # 發送到企業微信
    if wework_url:
        results["wework"] = send_to_wework(
            wework_url, report_data, report_type, update_info_to_send, proxy_url, mode
        )

    # 發送到 Telegram
    if telegram_token and telegram_chat_id:
        results["telegram"] = send_to_telegram(
            telegram_token,
            telegram_chat_id,
            report_data,
            report_type,
            update_info_to_send,
            proxy_url,
            mode,
        )

    if not results:
        print("未配置任何webhook URL，跳過通知發送")

    return results


def send_to_feishu(
    webhook_url: str,
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
) -> bool:
    """發送到飛書"""
    headers = {"Content-Type": "application/json"}

    text_content = render_feishu_content(report_data, update_info, mode)
    total_titles = sum(
        len(stat["titles"]) for stat in report_data["stats"] if stat["count"] > 0
    )

    now = get_beijing_time()
    payload = {
        "msg_type": "text",
        "content": {
            "total_titles": total_titles,
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "report_type": report_type,
            "text": text_content,
        },
    }

    proxies = None
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    try:
        response = requests.post(
            webhook_url, headers=headers, json=payload, proxies=proxies, timeout=30
        )
        if response.status_code == 200:
            print(f"飛書通知發送成功 [{report_type}]")
            return True
        else:
            print(f"飛書通知發送失敗 [{report_type}]，狀態碼：{response.status_code}")
            return False
    except Exception as e:
        print(f"飛書通知發送出錯 [{report_type}]：{e}")
        return False


def send_to_dingtalk(
    webhook_url: str,
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
) -> bool:
    """發送到釘釘"""
    headers = {"Content-Type": "application/json"}

    text_content = render_dingtalk_content(report_data, update_info, mode)

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": f"TrendRadar 熱點分析報告 - {report_type}",
            "text": text_content,
        },
    }

    proxies = None
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    try:
        response = requests.post(
            webhook_url, headers=headers, json=payload, proxies=proxies, timeout=30
        )
        if response.status_code == 200:
            result = response.json()
            if result.get("errcode") == 0:
                print(f"釘釘通知發送成功 [{report_type}]")
                return True
            else:
                print(f"釘釘通知發送失敗 [{report_type}]，錯誤：{result.get('errmsg')}")
                return False
        else:
            print(f"釘釘通知發送失敗 [{report_type}]，狀態碼：{response.status_code}")
            return False
    except Exception as e:
        print(f"釘釘通知發送出錯 [{report_type}]：{e}")
        return False


def send_to_wework(
    webhook_url: str,
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
) -> bool:
    """發送到企業微信（支持分批發送）"""
    headers = {"Content-Type": "application/json"}
    proxies = None
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    # 獲取分批內容
    batches = split_content_into_batches(report_data, "wework", update_info, mode=mode)

    print(f"企業微信消息分為 {len(batches)} 批次發送 [{report_type}]")

    # 逐批發送
    for i, batch_content in enumerate(batches, 1):
        batch_size = len(batch_content.encode("utf-8"))
        print(
            f"發送企業微信第 {i}/{len(batches)} 批次，大小：{batch_size} 字節 [{report_type}]"
        )

        # 添加批次標識
        if len(batches) > 1:
            batch_header = f"**[第 {i}/{len(batches)} 批次]**\n\n"
            batch_content = batch_header + batch_content

        payload = {"msgtype": "markdown", "markdown": {"content": batch_content}}

        try:
            response = requests.post(
                webhook_url, headers=headers, json=payload, proxies=proxies, timeout=30
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("errcode") == 0:
                    print(f"企業微信第 {i}/{len(batches)} 批次發送成功 [{report_type}]")
                    # 批次間間隔
                    if i < len(batches):
                        time.sleep(CONFIG["BATCH_SEND_INTERVAL"])
                else:
                    print(
                        f"企業微信第 {i}/{len(batches)} 批次發送失敗 [{report_type}]，錯誤：{result.get('errmsg')}"
                    )
                    return False
            else:
                print(
                    f"企業微信第 {i}/{len(batches)} 批次發送失敗 [{report_type}]，狀態碼：{response.status_code}"
                )
                return False
        except Exception as e:
            print(f"企業微信第 {i}/{len(batches)} 批次發送出錯 [{report_type}]：{e}")
            return False

    print(f"企業微信所有 {len(batches)} 批次發送完成 [{report_type}]")
    return True


def send_to_telegram(
    bot_token: str,
    chat_id: str,
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
) -> bool:
    """發送到Telegram（支持分批發送）"""
    headers = {"Content-Type": "application/json"}
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    proxies = None
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    # 獲取分批內容
    batches = split_content_into_batches(
        report_data, "telegram", update_info, mode=mode
    )

    print(f"Telegram消息分為 {len(batches)} 批次發送 [{report_type}]")

    # 逐批發送
    for i, batch_content in enumerate(batches, 1):
        batch_size = len(batch_content.encode("utf-8"))
        print(
            f"發送Telegram第 {i}/{len(batches)} 批次，大小：{batch_size} 字節 [{report_type}]"
        )

        # 添加批次標識
        if len(batches) > 1:
            batch_header = f"<b>[第 {i}/{len(batches)} 批次]</b>\n\n"
            batch_content = batch_header + batch_content

        payload = {
            "chat_id": chat_id,
            "text": batch_content,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        try:
            response = requests.post(
                url, headers=headers, json=payload, proxies=proxies, timeout=30
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    print(f"Telegram第 {i}/{len(batches)} 批次發送成功 [{report_type}]")
                    # 批次間間隔
                    if i < len(batches):
                        time.sleep(CONFIG["BATCH_SEND_INTERVAL"])
                else:
                    print(
                        f"Telegram第 {i}/{len(batches)} 批次發送失敗 [{report_type}]，錯誤：{result.get('description')}"
                    )
                    return False
            else:
                print(
                    f"Telegram第 {i}/{len(batches)} 批次發送失敗 [{report_type}]，狀態碼：{response.status_code}"
                )
                return False
        except Exception as e:
            print(f"Telegram第 {i}/{len(batches)} 批次發送出錯 [{report_type}]：{e}")
            return False

    print(f"Telegram所有 {len(batches)} 批次發送完成 [{report_type}]")
    return True


# === 主分析器 ===
class NewsAnalyzer:
    """新聞分析器"""

    # 模式策略定義
    MODE_STRATEGIES = {
        "incremental": {
            "mode_name": "增量模式",
            "description": "增量模式（只關注新增新聞，無新增時不推送）",
            "realtime_report_type": "實時增量",
            "summary_report_type": "當日匯總",
            "should_send_realtime": True,
            "should_generate_summary": True,
            "summary_mode": "daily",
        },
        "current": {
            "mode_name": "當前榜單模式",
            "description": "當前榜單模式（當前榜單匹配新聞 + 新增新聞區域 + 按時推送）",
            "realtime_report_type": "實時當前榜單",
            "summary_report_type": "當前榜單匯總",
            "should_send_realtime": True,
            "should_generate_summary": True,
            "summary_mode": "current",
        },
        "daily": {
            "mode_name": "當日匯總模式",
            "description": "當日匯總模式（所有匹配新聞 + 新增新聞區域 + 按時推送）",
            "realtime_report_type": "",
            "summary_report_type": "當日匯總",
            "should_send_realtime": False,
            "should_generate_summary": True,
            "summary_mode": "daily",
        },
    }

    def __init__(self):
        self.request_interval = CONFIG["REQUEST_INTERVAL"]
        self.report_mode = CONFIG["REPORT_MODE"]
        self.rank_threshold = CONFIG["RANK_THRESHOLD"]
        self.is_github_actions = os.environ.get("GITHUB_ACTIONS") == "true"
        self.is_docker_container = self._detect_docker_environment()
        self.update_info = None
        self.proxy_url = None
        self._setup_proxy()
        self.data_fetcher = DataFetcher(self.proxy_url)

        if self.is_github_actions:
            self._check_version_update()

    def _detect_docker_environment(self) -> bool:
        """檢測是否運行在 Docker 容器中"""
        try:
            if os.environ.get("DOCKER_CONTAINER") == "true":
                return True

            if os.path.exists("/.dockerenv"):
                return True

            return False
        except Exception:
            return False

    def _should_open_browser(self) -> bool:
        """判斷是否應該打開瀏覽器"""
        return not self.is_github_actions and not self.is_docker_container

    def _setup_proxy(self) -> None:
        """設置代理配置"""
        if not self.is_github_actions and CONFIG["USE_PROXY"]:
            self.proxy_url = CONFIG["DEFAULT_PROXY"]
            print("本地環境，使用代理")
        elif not self.is_github_actions and not CONFIG["USE_PROXY"]:
            print("本地環境，未啟用代理")
        else:
            print("GitHub Actions環境，不使用代理")

    def _check_version_update(self) -> None:
        """檢查版本更新"""
        try:
            need_update, remote_version = check_version_update(
                VERSION, CONFIG["VERSION_CHECK_URL"], self.proxy_url
            )

            if need_update and remote_version:
                self.update_info = {
                    "current_version": VERSION,
                    "remote_version": remote_version,
                }
                print(f"發現新版本: {remote_version} (當前: {VERSION})")
            else:
                print("版本檢查完成，當前為最新版本")
        except Exception as e:
            print(f"版本檢查出錯: {e}")

    def _get_mode_strategy(self) -> Dict:
        """獲取當前模式的策略配置"""
        return self.MODE_STRATEGIES.get(self.report_mode, self.MODE_STRATEGIES["daily"])

    def _has_webhook_configured(self) -> bool:
        """檢查是否配置了webhook"""
        return any(
            [
                CONFIG["FEISHU_WEBHOOK_URL"],
                CONFIG["DINGTALK_WEBHOOK_URL"],
                CONFIG["WEWORK_WEBHOOK_URL"],
                (CONFIG["TELEGRAM_BOT_TOKEN"] and CONFIG["TELEGRAM_CHAT_ID"]),
            ]
        )

    def _has_valid_content(
        self, stats: List[Dict], new_titles: Optional[Dict] = None
    ) -> bool:
        """檢查是否有有效的新聞內容"""
        if self.report_mode in ["incremental", "current"]:
            # 增量模式和current模式下，只要stats有內容就說明有匹配的新聞
            return any(stat["count"] > 0 for stat in stats)
        else:
            # 當日匯總模式下，檢查是否有匹配的頻率詞新聞或新增新聞
            has_matched_news = any(stat["count"] > 0 for stat in stats)
            has_new_news = bool(
                new_titles and any(len(titles) > 0 for titles in new_titles.values())
            )
            return has_matched_news or has_new_news

    def _load_analysis_data(
        self,
    ) -> Optional[Tuple[Dict, Dict, Dict, Dict, List, List]]:
        """統一的數據加載和預處理，使用當前監控平台列表過濾歷史數據"""
        try:
            # 獲取當前配置的監控平台ID列表
            current_platform_ids = []
            for platform in CONFIG["PLATFORMS"]:
                current_platform_ids.append(platform["id"])

            print(f"當前監控平台: {current_platform_ids}")

            all_results, id_to_name, title_info = read_all_today_titles(
                current_platform_ids
            )

            if not all_results:
                print("沒有找到當天的數據")
                return None

            total_titles = sum(len(titles) for titles in all_results.values())
            print(f"讀取到 {total_titles} 個標題（已按當前監控平台過濾）")

            new_titles = detect_latest_new_titles(current_platform_ids)
            word_groups, filter_words = load_frequency_words()

            return (
                all_results,
                id_to_name,
                title_info,
                new_titles,
                word_groups,
                filter_words,
            )
        except Exception as e:
            print(f"數據加載失敗: {e}")
            return None

    def _prepare_current_title_info(self, results: Dict, time_info: str) -> Dict:
        """從當前抓取結果構建標題信息"""
        title_info = {}
        for source_id, titles_data in results.items():
            title_info[source_id] = {}
            for title, title_data in titles_data.items():
                ranks = title_data.get("ranks", [])
                url = title_data.get("url", "")
                mobile_url = title_data.get("mobileUrl", "")

                title_info[source_id][title] = {
                    "first_time": time_info,
                    "last_time": time_info,
                    "count": 1,
                    "ranks": ranks,
                    "url": url,
                    "mobileUrl": mobile_url,
                }
        return title_info

    def _run_analysis_pipeline(
        self,
        data_source: Dict,
        mode: str,
        title_info: Dict,
        new_titles: Dict,
        word_groups: List[Dict],
        filter_words: List[str],
        id_to_name: Dict,
        failed_ids: Optional[List] = None,
        is_daily_summary: bool = False,
    ) -> Tuple[List[Dict], str]:
        """統一的分析流水線：數據處理 → 統計計算 → HTML生成"""

        # 統計計算
        stats, total_titles = count_word_frequency(
            data_source,
            word_groups,
            filter_words,
            id_to_name,
            title_info,
            self.rank_threshold,
            new_titles,
            mode=mode,
        )

        # HTML生成
        html_file = generate_html_report(
            stats,
            total_titles,
            failed_ids=failed_ids,
            new_titles=new_titles,
            id_to_name=id_to_name,
            mode=mode,
            is_daily_summary=is_daily_summary,
        )

        return stats, html_file

    def _send_notification_if_needed(
        self,
        stats: List[Dict],
        report_type: str,
        mode: str,
        failed_ids: Optional[List] = None,
        new_titles: Optional[Dict] = None,
        id_to_name: Optional[Dict] = None,
    ) -> bool:
        """統一的通知發送邏輯，包含所有判斷條件"""
        has_webhook = self._has_webhook_configured()

        if (
            CONFIG["ENABLE_NOTIFICATION"]
            and has_webhook
            and self._has_valid_content(stats, new_titles)
        ):
            send_to_webhooks(
                stats,
                failed_ids or [],
                report_type,
                new_titles,
                id_to_name,
                self.update_info,
                self.proxy_url,
                mode=mode,
            )
            return True
        elif CONFIG["ENABLE_NOTIFICATION"] and not has_webhook:
            print("⚠️ 警告：通知功能已啟用但未配置webhook URL，將跳過通知發送")
        elif not CONFIG["ENABLE_NOTIFICATION"]:
            print(f"跳過{report_type}通知：通知功能已禁用")
        elif (
            CONFIG["ENABLE_NOTIFICATION"]
            and has_webhook
            and not self._has_valid_content(stats, new_titles)
        ):
            mode_strategy = self._get_mode_strategy()
            if "實時" in report_type:
                print(
                    f"跳過實時推送通知：{mode_strategy['mode_name']}下未檢測到匹配的新聞"
                )
            else:
                print(
                    f"跳過{mode_strategy['summary_report_type']}通知：未匹配到有效的新聞內容"
                )

        return False

    def _generate_summary_report(self, mode_strategy: Dict) -> Optional[str]:
        """生成匯總報告（帶通知）"""
        summary_type = (
            "當前榜單匯總" if mode_strategy["summary_mode"] == "current" else "當日匯總"
        )
        print(f"生成{summary_type}報告...")

        # 加載分析數據
        analysis_data = self._load_analysis_data()
        if not analysis_data:
            return None

        all_results, id_to_name, title_info, new_titles, word_groups, filter_words = (
            analysis_data
        )

        # 運行分析流水線
        stats, html_file = self._run_analysis_pipeline(
            all_results,
            mode_strategy["summary_mode"],
            title_info,
            new_titles,
            word_groups,
            filter_words,
            id_to_name,
            is_daily_summary=True,
        )

        print(f"{summary_type}報告已生成: {html_file}")

        # 發送通知
        self._send_notification_if_needed(
            stats,
            mode_strategy["summary_report_type"],
            mode_strategy["summary_mode"],
            new_titles=new_titles,
            id_to_name=id_to_name,
        )

        return html_file

    def _generate_summary_html(self, mode: str = "daily") -> Optional[str]:
        """生成匯總HTML"""
        summary_type = "當前榜單匯總" if mode == "current" else "當日匯總"
        print(f"生成{summary_type}HTML...")

        # 加載分析數據
        analysis_data = self._load_analysis_data()
        if not analysis_data:
            return None

        all_results, id_to_name, title_info, new_titles, word_groups, filter_words = (
            analysis_data
        )

        # 運行分析流水線
        _, html_file = self._run_analysis_pipeline(
            all_results,
            mode,
            title_info,
            new_titles,
            word_groups,
            filter_words,
            id_to_name,
            is_daily_summary=True,
        )

        print(f"{summary_type}HTML已生成: {html_file}")
        return html_file

    def _initialize_and_check_config(self) -> None:
        """通用初始化和配置檢查"""
        now = get_beijing_time()
        print(f"當前北京時間: {now.strftime('%Y-%m-%d %H:%M:%S')}")

        if not CONFIG["ENABLE_CRAWLER"]:
            print("爬蟲功能已禁用（ENABLE_CRAWLER=False），程序退出")
            return

        has_webhook = self._has_webhook_configured()
        if not CONFIG["ENABLE_NOTIFICATION"]:
            print("通知功能已禁用（ENABLE_NOTIFICATION=False），將只進行數據抓取")
        elif not has_webhook:
            print("未配置任何webhook URL，將只進行數據抓取，不發送通知")
        else:
            print("通知功能已啟用，將發送webhook通知")

        mode_strategy = self._get_mode_strategy()
        print(f"報告模式: {self.report_mode}")
        print(f"運行模式: {mode_strategy['description']}")

    def _crawl_data(self) -> Tuple[Dict, Dict, List]:
        """執行數據爬取"""
        ids = []
        for platform in CONFIG["PLATFORMS"]:
            if "name" in platform:
                ids.append((platform["id"], platform["name"]))
            else:
                ids.append(platform["id"])

        print(
            f"配置的監控平台: {[p.get('name', p['id']) for p in CONFIG['PLATFORMS']]}"
        )
        print(f"開始爬取數據，請求間隔 {self.request_interval} 毫秒")
        ensure_directory_exists("output")

        results, id_to_name, failed_ids = self.data_fetcher.crawl_websites(
            ids, self.request_interval
        )

        title_file = save_titles_to_file(results, id_to_name, failed_ids)
        print(f"標題已保存到: {title_file}")

        return results, id_to_name, failed_ids

    def _execute_mode_strategy(
        self, mode_strategy: Dict, results: Dict, id_to_name: Dict, failed_ids: List
    ) -> Optional[str]:
        """執行模式特定邏輯"""
        # 獲取當前監控平台ID列表
        current_platform_ids = [platform["id"] for platform in CONFIG["PLATFORMS"]]

        new_titles = detect_latest_new_titles(current_platform_ids)
        time_info = Path(save_titles_to_file(results, id_to_name, failed_ids)).stem
        word_groups, filter_words = load_frequency_words()

        # current模式下，實時推送需要使用完整的歷史數據來保證統計信息的完整性
        if self.report_mode == "current":
            # 加載完整的歷史數據（已按當前平台過濾）
            analysis_data = self._load_analysis_data()
            if analysis_data:
                (
                    all_results,
                    historical_id_to_name,
                    historical_title_info,
                    historical_new_titles,
                    _,
                    _,
                ) = analysis_data

                print(
                    f"current模式：使用過濾後的歷史數據，包含平台：{list(all_results.keys())}"
                )

                stats, html_file = self._run_analysis_pipeline(
                    all_results,
                    self.report_mode,
                    historical_title_info,
                    historical_new_titles,
                    word_groups,
                    filter_words,
                    historical_id_to_name,
                    failed_ids=failed_ids,
                )

                combined_id_to_name = {**historical_id_to_name, **id_to_name}

                print(f"HTML報告已生成: {html_file}")

                # 發送實時通知（使用完整歷史數據的統計結果）
                summary_html = None
                if mode_strategy["should_send_realtime"]:
                    self._send_notification_if_needed(
                        stats,
                        mode_strategy["realtime_report_type"],
                        self.report_mode,
                        failed_ids=failed_ids,
                        new_titles=historical_new_titles,
                        id_to_name=combined_id_to_name,
                    )
            else:
                print("❌ 嚴重錯誤：無法讀取剛保存的數據文件")
                raise RuntimeError("數據一致性檢查失敗：保存後立即讀取失敗")
        else:
            title_info = self._prepare_current_title_info(results, time_info)
            stats, html_file = self._run_analysis_pipeline(
                results,
                self.report_mode,
                title_info,
                new_titles,
                word_groups,
                filter_words,
                id_to_name,
                failed_ids=failed_ids,
            )
            print(f"HTML報告已生成: {html_file}")

            # 發送實時通知（如果需要）
            summary_html = None
            if mode_strategy["should_send_realtime"]:
                self._send_notification_if_needed(
                    stats,
                    mode_strategy["realtime_report_type"],
                    self.report_mode,
                    failed_ids=failed_ids,
                    new_titles=new_titles,
                    id_to_name=id_to_name,
                )

        # 生成匯總報告（如果需要）
        summary_html = None
        if mode_strategy["should_generate_summary"]:
            if mode_strategy["should_send_realtime"]:
                # 如果已經發送了實時通知，匯總只生成HTML不發送通知
                summary_html = self._generate_summary_html(
                    mode_strategy["summary_mode"]
                )
            else:
                # daily模式：直接生成匯總報告並發送通知
                summary_html = self._generate_summary_report(mode_strategy)

        # 打開瀏覽器（僅在非容器環境）
        if self._should_open_browser() and html_file:
            if summary_html:
                summary_url = "file://" + str(Path(summary_html).resolve())
                print(f"正在打開匯總報告: {summary_url}")
                webbrowser.open(summary_url)
            else:
                file_url = "file://" + str(Path(html_file).resolve())
                print(f"正在打開HTML報告: {file_url}")
                webbrowser.open(file_url)
        elif self.is_docker_container and html_file:
            if summary_html:
                print(f"匯總報告已生成（Docker環境）: {summary_html}")
            else:
                print(f"HTML報告已生成（Docker環境）: {html_file}")

        return summary_html

    def run(self) -> None:
        """執行分析流程"""
        try:
            self._initialize_and_check_config()

            mode_strategy = self._get_mode_strategy()

            results, id_to_name, failed_ids = self._crawl_data()

            self._execute_mode_strategy(mode_strategy, results, id_to_name, failed_ids)

        except Exception as e:
            print(f"分析流程執行出錯: {e}")
            raise


def main():
    try:
        analyzer = NewsAnalyzer()
        analyzer.run()
    except FileNotFoundError as e:
        print(f"❌ 配置文件錯誤: {e}")
        print("\n請確保以下文件存在:")
        print("  ‧ config/config.yaml")
        print("  ‧ config/frequency_words.txt")
        print("\n參考項目文檔進行正確配置")
    except Exception as e:
        print(f"❌ 程序運行錯誤: {e}")
        raise


if __name__ == "__main__":
    main()
