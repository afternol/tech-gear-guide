# -*- coding: utf-8 -*-
"""
Tech Gear Guide — prune.py
月次バッチ: 低PV記事のnoindex / 論理削除 / 類似タイトルnoindex

実行タイミング: GitHub Actions monthly cron (月初 JST 10:00)
手動実行:       cd pipeline && python prune.py [--dry-run]
"""

import json
import os
import re
import sys
import io
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    from supabase import create_client, Client
except ImportError:
    print("supabase パッケージが必要です: pip install supabase")
    sys.exit(1)

# ─────────────────────────────────────────────
# 設定
# ─────────────────────────────────────────────

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

DRY_RUN = "--dry-run" in sys.argv

# noindex: 60日以上経過 かつ PV < 30
NOINDEX_AGE_DAYS = 60
NOINDEX_PV_THRESHOLD = 30

# 論理削除: 90日以上経過 かつ PV < 10
DELETE_AGE_DAYS = 90
DELETE_PV_THRESHOLD = 10

# 類似タイトル: 同カテゴリ × 48時間以内 × ワード重複率 >= 0.6 の場合、低PV側をnoindex
SIMILAR_WINDOW_HOURS = 48
SIMILAR_WORD_OVERLAP = 0.6

LOG_PATH = Path("prune_log.jsonl")


# ─────────────────────────────────────────────
# ユーティリティ
# ─────────────────────────────────────────────

def _title_words(title: str) -> set[str]:
    """タイトルを単語セットに変換（英数字トークン + 日本語2gram）"""
    title = title.lower()
    en_tokens = set(re.findall(r'[a-z0-9]+', title))
    jp_chars  = re.sub(r'[a-z0-9\s\W]', '', title)
    jp_grams  = {jp_chars[i:i+2] for i in range(len(jp_chars) - 1)} if len(jp_chars) >= 2 else set()
    return en_tokens | jp_grams


def _overlap(a: str, b: str) -> float:
    wa, wb = _title_words(a), _title_words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def _log(entry: dict):
    mode = "DRY-RUN" if DRY_RUN else "EXEC"
    entry["mode"] = mode
    entry["logged_at"] = datetime.now(timezone.utc).isoformat()
    print(json.dumps(entry, ensure_ascii=False))
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ─────────────────────────────────────────────
# Supabase ヘルパー
# ─────────────────────────────────────────────

def get_pv(sb: "Client", slug: str) -> int:
    """page_views テーブルからPV合計を取得。テーブルが空の場合は0を返す。"""
    try:
        res = sb.table("page_views").select("id", count="exact").eq("slug", slug).execute()
        return res.count or 0
    except Exception:
        return 0


def set_noindex(sb: "Client", slug: str, reason: str):
    if DRY_RUN:
        return
    sb.table("articles").update({
        "is_indexed":    False,
        "noindex_reason": reason,
    }).eq("slug", slug).execute()


def set_unpublished(sb: "Client", slug: str, reason: str):
    if DRY_RUN:
        return
    sb.table("articles").update({
        "is_published":  False,
        "is_indexed":    False,
        "noindex_reason": reason,
    }).eq("slug", slug).execute()


# ─────────────────────────────────────────────
# 処理ロジック
# ─────────────────────────────────────────────

def prune_low_pv(sb: "Client") -> tuple[int, int]:
    """60日+PV<30→noindex / 90日+PV<10→論理削除"""
    now = datetime.now(timezone.utc)
    cutoff_noindex = (now - timedelta(days=NOINDEX_AGE_DAYS)).isoformat()
    cutoff_delete  = (now - timedelta(days=DELETE_AGE_DAYS)).isoformat()

    # 60日以上の公開記事を取得
    res = sb.table("articles").select(
        "slug,title,category,published_at,is_indexed,noindex_reason"
    ).eq("is_published", True).lt("published_at", cutoff_noindex).execute()

    articles = res.data or []
    n_noindex = 0
    n_delete  = 0

    for a in articles:
        slug = a["slug"]
        pv   = get_pv(sb, slug)
        age_days = (now - datetime.fromisoformat(a["published_at"].replace("Z", "+00:00"))).days

        if age_days >= DELETE_AGE_DAYS and pv < DELETE_PV_THRESHOLD:
            _log({
                "action": "unpublish",
                "slug": slug,
                "title": a["title"][:60],
                "age_days": age_days,
                "pv": pv,
                "reason": f"prune:low_pv_{DELETE_AGE_DAYS}d",
            })
            set_unpublished(sb, slug, f"prune:low_pv_{DELETE_AGE_DAYS}d")
            n_delete += 1

        elif pv < NOINDEX_PV_THRESHOLD and not (a.get("noindex_reason") or "").startswith("prune:"):
            _log({
                "action": "noindex",
                "slug": slug,
                "title": a["title"][:60],
                "age_days": age_days,
                "pv": pv,
                "reason": f"prune:low_pv_{NOINDEX_AGE_DAYS}d",
            })
            set_noindex(sb, slug, f"prune:low_pv_{NOINDEX_AGE_DAYS}d")
            n_noindex += 1

    return n_noindex, n_delete


def prune_similar_titles(sb: "Client") -> int:
    """類似タイトルペアを検出し、低PV側をnoindex"""
    now = datetime.now(timezone.utc)
    # 過去30日の記事を対象（類似タイトルは近い時期に発生する）
    cutoff = (now - timedelta(days=30)).isoformat()

    res = sb.table("articles").select(
        "slug,title,category,published_at"
    ).eq("is_published", True).eq("is_indexed", True).gte("published_at", cutoff).execute()

    articles = res.data or []
    n_noindex = 0

    # カテゴリ別に分類
    by_cat: dict[str, list[dict]] = {}
    for a in articles:
        by_cat.setdefault(a["category"], []).append(a)

    for cat, group in by_cat.items():
        # published_at でソート
        group.sort(key=lambda x: x["published_at"])

        for i, a in enumerate(group):
            pub_a = datetime.fromisoformat(a["published_at"].replace("Z", "+00:00"))
            for b in group[i + 1:]:
                pub_b = datetime.fromisoformat(b["published_at"].replace("Z", "+00:00"))
                if (pub_b - pub_a).total_seconds() > SIMILAR_WINDOW_HOURS * 3600:
                    break
                if _overlap(a["title"], b["title"]) < SIMILAR_WORD_OVERLAP:
                    continue

                # 類似ペア: PVが少ない方をnoindex
                pv_a = get_pv(sb, a["slug"])
                pv_b = get_pv(sb, b["slug"])
                loser = a if pv_a <= pv_b else b
                _log({
                    "action": "noindex_similar",
                    "slug": loser["slug"],
                    "title": loser["title"][:60],
                    "similar_to": (b if loser == a else a)["slug"],
                    "overlap": round(_overlap(a["title"], b["title"]), 2),
                    "pv": pv_a if loser == a else pv_b,
                    "reason": "prune:similar_title",
                })
                set_noindex(sb, loser["slug"], "prune:similar_title")
                n_noindex += 1

    return n_noindex


# ─────────────────────────────────────────────
# メイン
# ─────────────────────────────────────────────

def main():
    if DRY_RUN:
        print("=== DRY-RUN モード（実際の更新なし）===")

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    print("── 低PV記事の処理 ──")
    n_noindex, n_delete = prune_low_pv(sb)
    print(f"  noindex: {n_noindex}件 / 論理削除: {n_delete}件")

    print("── 類似タイトルの処理 ──")
    n_similar = prune_similar_titles(sb)
    print(f"  類似noindex: {n_similar}件")

    total = n_noindex + n_delete + n_similar
    print(f"\n合計 {total}件を処理しました")
    if DRY_RUN:
        print("（DRY-RUNのため実際の変更は行われていません）")


if __name__ == "__main__":
    main()
