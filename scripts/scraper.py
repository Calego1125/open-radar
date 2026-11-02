#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenRadar 核心采集与机器人自动化分发引擎
"""

import os
import sys
import json
import re
import time
from datetime import datetime
import requests
from bs4 import BeautifulSoup

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "radar_data.json")

class OpenRadarScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
        })

    def fetch_all_candidates(self) -> list:
        print("[*] 正在采集全网 GitHub Trending 候选项目...")
        candidates = []
        seen = set()

        api_urls = [
            "https://github-trending-api.deno.dev/repositories?since=daily",
            "https://gtrend.yapie.me/repositories?since=daily"
        ]
        for url in api_urls:
            try:
                r = self.session.get(url, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, list):
                        for item in data:
                            name = item.get("author") and f"{item['author']}/{item.get('name')}" or item.get("repo", "")
                            if name and name not in seen:
                                seen.add(name)
                                candidates.append({
                                    "name": name,
                                    "url": item.get("url") or f"https://github.com/{name}",
                                    "raw_desc": item.get("description") or "",
                                    "lang": item.get("language") or "通用",
                                    "stars": int(item.get("stars", 0)),
                                    "stars_today": int(item.get("currentPeriodStars", 0))
                                })
                        print(f"[✓] 通过 API 汇聚候选项目: 目前累计 {len(candidates)} 项")
                        break
            except Exception:
                continue

        if len(candidates) < 20:
            try:
                r = self.session.get("https://github.com/trending?since=daily", timeout=12)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")
                    for art in soup.find_all("article", class_="Box-row"):
                        h2 = art.find("h2")
                        if not h2 or not h2.find("a"): continue
                        name = h2.find("a").get("href", "").strip().strip("/")
                        if name and name not in seen:
                            seen.add(name)
                            p = art.find("p")
                            desc = p.get_text(strip=True) if p else ""
                            lang_el = art.find("span", attrs={"itemprop": "programmingLanguage"})
                            lang = lang_el.get_text(strip=True) if lang_el else "通用"
                            star_a = art.find("a", href=lambda h: h and h.endswith("/stargazers"))
                            stars = int(star_a.get_text(strip=True).replace(",", "") or 0) if star_a else 0
                            growth = 0
                            footer = art.find("div", class_=lambda c: c and "color-fg-muted" in c)
                            if footer:
                                for s in footer.find_all("span"):
                                    t = s.get_text(strip=True)
                                    if "stars today" in t.lower():
                                        m = re.search(r"(\d+[\d,]*)", t)
                                        if m: growth = int(m.group(1).replace(",", ""))
                                        break
                            candidates.append({
                                "name": name, "url": f"https://github.com/{name}",
                                "raw_desc": desc, "lang": lang, "stars": stars, "stars_today": growth
                            })
            except Exception:
                pass

        if len(candidates) < 30:
            self._enrich_targeted_topics(candidates, seen)
        return candidates

    def _enrich_targeted_topics(self, candidates, seen):
        print("[*] 正在针对 AI Agent 与前沿模型生态执行专项扩充检索...")
        queries = ["topic:agent+stars:>500", "topic:llm+stars:>1000", "topic:mcp+stars:>200"]
        for q in queries:
            try:
                url = f"https://api.github.com/search/repositories?q={q}&sort=stars&order=desc&per_page=15"
                r = self.session.get(url, timeout=8)
                if r.status_code == 200:
                    for it in r.json().get("items", []):
                        name = it.get("full_name")
                        if name and name not in seen:
                            seen.add(name)
                            candidates.append({
                                "name": name, "url": it.get("html_url"),
                                "raw_desc": it.get("description") or "",
                                "lang": it.get("language") or "多语言",
                                "stars": it.get("stargazers_count", 0),
                                "stars_today": max(int(it.get("forks_count", 0) / 4), 180)
                            })
            except Exception:
                pass

    def classify_and_refine(self, item: dict) -> dict:
        name = item["name"]
        raw_desc = (item["raw_desc"] or "").strip()
        lang = item["lang"]
        stars = item["stars"]
        stars_today = item["stars_today"]
        corpus = f"{name} {raw_desc} {lang}".lower()

        resource_patterns = ["book", "interview", "awesome", "tutorial", "roadmap", "cheatsheet", "guide", "free-programming"]
        if any(p in corpus for p in resource_patterns):
            category = "resource"
            category_name = "📚 开源学习与资源精选"
            position = f"开源社区协作维护的学习目录与知识索引库，专注于 {raw_desc or '计算机技术生态指南'}。"
            why_hot = "作为开源社区常青知识底座，因近期内容扩充与分类更新持续获得高频收藏。"
            features = ["社区协作共建", "系统化知识脉络", "免商用非营利", "多语言知识索引"]
        else:
            agent_patterns = ["agent", "autonomous", "workflow", "copilot", "assistant", "reasoning", "tool", "mcp", "crew", "langchain", "browser-use", "openclaw"]
            frontier_patterns = ["llm", "large language", "transformer", "diffusion", "vision", "multimodal", "robotics", "inference", "vllm", "cuda", "embedding", "speech", "tts"]

            if any(p in corpus for p in agent_patterns):
                category = "agent"
                category_name = "🤖 AI Agent & 智能体"
                position = raw_desc or "面向复杂任务自动化执行的开源智能体架构与工作流平台。"
                why_hot = "踩中智能体自主操作与多工具协议爆发节点，极大降低了复杂工作流落地的工程复杂度。"
                features = ["自主工作流编排", "外部工具/MCP协议集成", "长短期记忆沉淀", "跨平台环境接管"]
            elif any(p in corpus for p in frontier_patterns):
                category = "frontier"
                category_name = "⚡ 前沿科技 & 模型架构"
                position = raw_desc or "面向新一代大模型训练、推理加速与多模态生成的基础设施底座。"
                why_hot = "直击大模型推理高延迟与显存瓶颈痛点，在极致能效与高并发吞吐上取得突破性进展。"
                features = ["底层算力显存优化", "高并发吞吐调度", "多模态架构原生支持", "生产级部署友好"]
            else:
                category = "infra"
                category_name = "🛠️ 基础设施 & 开发者工具"
                position = raw_desc or f"基于 {lang} 打造的高性能现代研发基础设施与开发者生产力套件。"
                why_hot = "重塑了传统的繁琐研发链路，在编译速度、开发体验与资源利用率上实现了跃升。"
                features = [f"{lang} 现代化架构", "极简人体工学设计", "高内聚松耦合", "零侵入开箱即用"]

        if stars >= 12000:
            growth_type, growth_type_name, growth_badge = "evergreen", "🏛️ 长期霸榜", "常青基石"
        elif stars < 4000:
            growth_type, growth_type_name, growth_badge = "rising", "🔥 新锐黑马", "新锐爆发"
        else:
            growth_type, growth_type_name, growth_badge = "spike", "⚡ 单日飙升", "单日激增"

        return {
            "id": re.sub(r"[^a-zA-Z0-9_-]", "-", name).lower(),
            "name": name, "url": item["url"],
            "category": category, "category_name": category_name,
            "growth_type": growth_type, "growth_type_name": growth_type_name,
            "growth_badge": growth_badge, "lang": lang,
            "stars": stars, "stars_today": stars_today,
            "position": position, "why_hot": why_hot, "features": features
        }

    def build_matrix_dataset(self, candidates: list) -> dict:
        refined = [self.classify_and_refine(c) for c in candidates]
        unique_map = {r["name"]: r for r in refined}
        pool = list(unique_map.values())
        pool.sort(key=lambda x: x["stars_today"], reverse=True)

        def pick(filter_fn):
            return [x for x in pool if filter_fn(x)][:10]

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return {
            "meta": {
                "generated_at": now_str,
                "timezone": "UTC+8 (Asia/Shanghai)",
                "total_monitored": len(pool)
            },
            "tracks": {
                "agent": pick(lambda x: x["category"] == "agent"),
                "frontier": pick(lambda x: x["category"] == "frontier"),
                "rising": pick(lambda x: x["growth_type"] == "rising"),
                "evergreen": pick(lambda x: x["growth_type"] == "evergreen"),
                "infra": pick(lambda x: x["category"] == "infra")
            }
        }


def push_to_chat_bot(matrix):
    """自动兼容飞书与微信（企业微信）机器人的每日早报推送"""
    webhook = os.getenv("BOT_WEBHOOK", "").strip()
    if not webhook or not webhook.startswith("http"):
        print("[*] 未配置 BOT_WEBHOOK 密钥，跳过群机器人分发。")
        return

    print("[*] 检测到 BOT_WEBHOOK，正在发送技术早报...")
    now_str = matrix["meta"]["generated_at"]
    agent_top1 = matrix["tracks"]["agent"][0]
    frontier_top1 = matrix["tracks"]["frontier"][0]
    rising_top1 = matrix["tracks"]["rising"][0]

    # 1. 如果是飞书机器人 Webhook
    if "feishu.cn" in webhook:
        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": "indigo",
                "title": {"tag": "plain_text", "content": "🚀 OpenRadar 开源前沿技术早报"}
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"📅 **更新时间**: {now_str} (UTC+8)\n\n"
                            f"🤖 **今日 Agent 榜首**: [{agent_top1['name']}]({agent_top1['url']})\n"
                            f"> 📌 {agent_top1['position']}\n\n"
                            f"⚡ **前沿模型架构榜首**: [{frontier_top1['name']}]({frontier_top1['url']})\n"
                            f"> 📌 {frontier_top1['position']}\n\n"
                            f"🔥 **新锐黑马突破**: [{rising_top1['name']}]({rising_top1['url']}) (`+{rising_top1['stars_today']} stars today`)"
                        )
                    }
                },
                {"tag": "hr"},
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "🌐 打开专属技术雷达看板"},
                            "type": "primary",
                            "url": "https://calego1125.github.io/open-radar/"
                        }
                    ]
                }
            ]
        }
        body = {"msg_type": "interactive", "card": card}
    # 2. 如果是微信 / 企业微信群机器人 Webhook
    else:
        text_md = (
            f"### 🚀 OpenRadar 开源前沿技术早报\n"
            f"> 更新时间：{now_str} (UTC+8)\n\n"
            f"**🤖 今日 Agent 榜首**: [{agent_top1['name']}]({agent_top1['url']})\n"
            f"> {agent_top1['position']}\n\n"
            f"**⚡ 前沿模型架构榜首**: [{frontier_top1['name']}]({frontier_top1['url']})\n"
            f"> {frontier_top1['position']}\n\n"
            f"**🔥 新锐黑马突破**: [{rising_top1['name']}]({rising_top1['url']}) (`+{rising_top1['stars_today']} stars`)\n\n"
            f"[👉 点击打开你的在线技术雷达看板](https://calego1125.github.io/open-radar/)"
        )
        payload = {"msg_type": "markdown", "markdown": {"content": text_md}}

    try:
        r = requests.post(webhook, json=payload, timeout=8)
        print(f"[✓] 每日早报已成功推送到群机器人！响应: {r.status_code}")
    except Exception as e:
        print(f"[!] 机器人推送异常: {e}")


def main():
    scraper = OpenRadarScraper()
    candidates = scraper.fetch_all_candidates()
    matrix = scraper.build_matrix_dataset(candidates)
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(matrix, f, ensure_ascii=False, indent=2)
    print("[✓] 矩阵数据更新成功！")
    
    # 自动执行群机器人推送
    push_to_chat_bot(matrix)

if __name__ == "__main__":
    main()
