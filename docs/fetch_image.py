# -*- coding: utf-8 -*-
"""
DeviceBrief fetch_image.py 設計ドラフト v1

アイキャッチ画像取得・生成ツール
generate.py から呼び出されて使用する独立モジュール

処理フロー:
  Step1: 記事タイトルのキーワードからメーカー公式プレスルームを特定
         → httpxでog:image取得（報道利用許可済みサイト）
  Step2: Step1失敗時はUnsplash APIでカテゴリ別フリー画像を取得
  後処理: Pillowで1,200×628pxにリサイズ + ロゴ・バッジオーバーレイ
  保存:   Supabase Storage（またはローカルのimages/ディレクトリ）
"""

import sys
import io
import re
import hashlib
from pathlib import Path
from typing import Optional

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import httpx
from PIL import Image, ImageDraw, ImageFont

# ─────────────────────────────────────────────
# 設定
# ─────────────────────────────────────────────

OUTPUT_DIR     = Path("images")
OUTPUT_DIR.mkdir(exist_ok=True)

TARGET_W, TARGET_H = 1200, 628   # OGP推奨サイズ
LOGO_PATH      = Path("assets/devicebrief_logo.png")   # 事前用意
FONT_PATH      = Path("assets/NotoSansJP-Bold.ttf")    # 日本語フォント

UNSPLASH_ACCESS_KEY = ""   # .env から読み込む想定

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
}

# ─────────────────────────────────────────────
# プレスルームマッピング（著作権クリア・報道利用許可）
# ─────────────────────────────────────────────

PRESS_ROOM: dict[str, str] = {
    # Apple
    "iphone":     "https://www.apple.com/newsroom/",
    "ipad":       "https://www.apple.com/newsroom/",
    "mac":        "https://www.apple.com/newsroom/",
    "macbook":    "https://www.apple.com/newsroom/",
    "apple":      "https://www.apple.com/newsroom/",
    "ios":        "https://www.apple.com/newsroom/",
    "macos":      "https://www.apple.com/newsroom/",
    # Samsung
    "samsung":    "https://news.samsung.com/global/",
    "galaxy":     "https://news.samsung.com/global/",
    # NVIDIA
    "nvidia":     "https://nvidianews.nvidia.com/",
    "geforce":    "https://nvidianews.nvidia.com/",
    "rtx":        "https://nvidianews.nvidia.com/",
    "dlss":       "https://nvidianews.nvidia.com/",
    "cuda":       "https://nvidianews.nvidia.com/",
    # AMD
    "amd":        "https://www.amd.com/en/newsroom/",
    "radeon":     "https://www.amd.com/en/newsroom/",
    "ryzen":      "https://www.amd.com/en/newsroom/",
    "expo":       "https://www.amd.com/en/newsroom/",
    # Intel
    "intel":      "https://www.intel.com/content/www/us/en/newsroom/home.html",
    "core ultra": "https://www.intel.com/content/www/us/en/newsroom/home.html",
    # Microsoft
    "microsoft":  "https://news.microsoft.com/",
    "windows":    "https://news.microsoft.com/",
    "surface":    "https://news.microsoft.com/",
    "copilot":    "https://news.microsoft.com/",
    # Google
    "google":     "https://blog.google/",
    "pixel":      "https://blog.google/products/pixel/",
    "android":    "https://blog.google/products/android/",
    "gemini":     "https://blog.google/technology/ai/",
    # OpenAI
    "openai":     "https://openai.com/news/",
    "chatgpt":    "https://openai.com/news/",
    "gpt":        "https://openai.com/news/",
    "sora":       "https://openai.com/news/",
    # Qualcomm
    "qualcomm":   "https://news.qualcomm.com/",
    "snapdragon": "https://news.qualcomm.com/",
}

# ─────────────────────────────────────────────
# Unsplash カテゴリ別キーワード
# ─────────────────────────────────────────────

UNSPLASH_KEYWORDS: dict[str, list[str]] = {
    "smartphone": ["smartphone closeup", "mobile phone technology", "android iphone"],
    "tablet":     ["tablet device", "digital tablet", "ipad screen"],
    "windows":    ["laptop computer screen", "windows laptop", "desktop PC"],
    "cpu_gpu":    ["computer chip semiconductor", "gpu graphics card", "processor technology"],
    "ai":         ["artificial intelligence technology", "neural network abstract", "machine learning"],
    "general":    ["technology electronics", "gadget device", "tech background"],
}

# ─────────────────────────────────────────────
# カテゴリバッジ色（Pillowで描画）
# ─────────────────────────────────────────────

BADGE_COLORS: dict[str, tuple] = {
    "A型速報":   (220, 38, 38),    # 赤
    "B型深掘り": (37, 99, 235),    # 青
    "C型リーク": (217, 119, 6),    # オレンジ
}

CATEGORY_LABELS: dict[str, str] = {
    "smartphone": "スマートフォン",
    "tablet":     "タブレット",
    "windows":    "Windows",
    "cpu_gpu":    "CPU・GPU",
    "ai":         "AI",
    "general":    "テック",
}

# ─────────────────────────────────────────────
# Step 1: プレスルームからog:image取得
# ─────────────────────────────────────────────

def detect_press_room(title: str) -> Optional[str]:
    """記事タイトルのキーワードからプレスルームURLを返す"""
    t = title.lower()
    for kw, url in PRESS_ROOM.items():
        if kw in t:
            return url
    return None

def fetch_og_image_url(press_url: str) -> Optional[str]:
    """プレスルームのトップページからog:imageを取得"""
    try:
        with httpx.Client(headers=BROWSER_HEADERS, timeout=15, follow_redirects=True) as c:
            r = c.get(press_url)
            if r.status_code != 200:
                return None
            # og:image メタタグを抽出
            m = re.search(
                r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
                r.text, re.IGNORECASE
            )
            if not m:
                # content/property の順番が逆のケースにも対応
                m = re.search(
                    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
                    r.text, re.IGNORECASE
                )
            return m.group(1) if m else None
    except Exception:
        return None

def download_image(url: str) -> Optional[Image.Image]:
    """URLから画像をダウンロードしてPillow Imageとして返す"""
    try:
        with httpx.Client(headers=BROWSER_HEADERS, timeout=20, follow_redirects=True) as c:
            r = c.get(url)
            if r.status_code != 200:
                return None
            import io as _io
            return Image.open(_io.BytesIO(r.content)).convert("RGB")
    except Exception:
        return None

# ─────────────────────────────────────────────
# Step 2: Unsplash API
# ─────────────────────────────────────────────

def fetch_unsplash_image(category: str) -> Optional[Image.Image]:
    """Unsplash APIでカテゴリ別フリー画像を取得"""
    if not UNSPLASH_ACCESS_KEY:
        return None

    keywords = UNSPLASH_KEYWORDS.get(category, UNSPLASH_KEYWORDS["general"])
    query = keywords[0]  # 最初のキーワードを使用

    try:
        with httpx.Client(timeout=15) as c:
            r = c.get(
                "https://api.unsplash.com/search/photos",
                params={
                    "query": query,
                    "per_page": 5,
                    "orientation": "landscape",
                    "client_id": UNSPLASH_ACCESS_KEY,
                },
            )
            if r.status_code != 200:
                return None
            data = r.json()
            results = data.get("results", [])
            if not results:
                return None
            # 最初の画像のregular URLを使用
            img_url = results[0]["urls"]["regular"]
            return download_image(img_url)
    except Exception:
        return None

def get_unsplash_credit(category: str) -> str:
    """Unsplash使用時のクレジット文字列を返す（記事末尾に追加）"""
    # 実際にはAPIレスポンスから author を取得する
    return "Photo via Unsplash"

# ─────────────────────────────────────────────
# 後処理: Pillowでオーバーレイ
# ─────────────────────────────────────────────

def apply_overlay(
    img: Image.Image,
    article_type: str,
    category: str,
) -> Image.Image:
    """
    1. 1,200×628にリサイズ（中央クロップ）
    2. 下部グラデーション（テキスト可読性確保）
    3. カテゴリバッジ
    4. DeviceBriefロゴ（右下）
    """
    # ── 1. リサイズ（中央クロップ） ──────────────
    img = img.convert("RGB")
    src_w, src_h = img.size
    src_ratio = src_w / src_h
    tgt_ratio = TARGET_W / TARGET_H

    if src_ratio > tgt_ratio:
        # 横が余る → 高さに合わせてクロップ
        new_h = src_h
        new_w = int(src_h * tgt_ratio)
    else:
        new_w = src_w
        new_h = int(src_w / tgt_ratio)

    left = (src_w - new_w) // 2
    top  = (src_h - new_h) // 2
    img = img.crop((left, top, left + new_w, top + new_h))
    img = img.resize((TARGET_W, TARGET_H), Image.LANCZOS)

    draw = ImageDraw.Draw(img)

    # ── 2. 下部グラデーションオーバーレイ ──────────
    # 下部 1/4 を半透明ブラックで覆う（ロゴ・バッジの視認性向上）
    overlay = Image.new("RGBA", (TARGET_W, TARGET_H // 4), (0, 0, 0, 160))
    img.paste(
        Image.new("RGB", (TARGET_W, TARGET_H // 4), (0, 0, 0)),
        (0, TARGET_H - TARGET_H // 4),
        overlay,
    )

    # ── 3. カテゴリバッジ（左下） ─────────────────
    badge_color = BADGE_COLORS.get(article_type, (100, 100, 100))
    cat_label   = CATEGORY_LABELS.get(category, "テック")
    badge_text  = f" {cat_label} "

    try:
        font_badge = ImageFont.truetype(str(FONT_PATH), 22) if FONT_PATH.exists() else ImageFont.load_default()
    except Exception:
        font_badge = ImageFont.load_default()

    # バッジ背景
    bbox = draw.textbbox((0, 0), badge_text, font=font_badge)
    bw = bbox[2] - bbox[0] + 16
    bh = bbox[3] - bbox[1] + 10
    bx, by = 20, TARGET_H - bh - 20
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=6, fill=badge_color)
    draw.text((bx + 8, by + 5), badge_text.strip(), fill=(255, 255, 255), font=font_badge)

    # ── 4. DeviceBriefロゴ（右下） ────────────────
    if LOGO_PATH.exists():
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA")
            logo_h = 36
            logo_w = int(logo.width * (logo_h / logo.height))
            logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
            lx = TARGET_W - logo_w - 20
            ly = TARGET_H - logo_h - 20
            img.paste(logo, (lx, ly), logo)
        except Exception:
            pass
    else:
        # ロゴファイルがない場合はテキストで代替
        try:
            font_logo = ImageFont.truetype(str(FONT_PATH), 18) if FONT_PATH.exists() else ImageFont.load_default()
        except Exception:
            font_logo = ImageFont.load_default()
        logo_text = "DeviceBrief"
        bbox_l = draw.textbbox((0, 0), logo_text, font=font_logo)
        lw = bbox_l[2] - bbox_l[0]
        lh = bbox_l[3] - bbox_l[1]
        draw.text(
            (TARGET_W - lw - 20, TARGET_H - lh - 20),
            logo_text, fill=(255, 255, 255), font=font_logo,
        )

    return img

# ─────────────────────────────────────────────
# メイン関数（generate.py から呼び出す）
# ─────────────────────────────────────────────

def fetch_article_image(
    title: str,
    category: str,
    article_type: str,
    slug: str,
) -> dict:
    """
    記事のアイキャッチ画像を取得・生成して保存する。

    戻り値:
        {
            "local_path": str,       # ローカル保存パス
            "source": "press"|"unsplash"|"failed",
            "credit": str,           # Unsplash使用時のクレジット文
        }
    """
    output_path = OUTPUT_DIR / f"{slug}.jpg"
    img = None
    source = "failed"
    credit = ""

    # ── Step 1: プレスルーム画像 ──────────────────
    press_url = detect_press_room(title)
    if press_url:
        og_url = fetch_og_image_url(press_url)
        if og_url:
            img = download_image(og_url)
            if img:
                source = "press"
                print(f"    [image] プレス画像取得: {press_url[:60]}")

    # ── Step 2: Unsplash ──────────────────────────
    if img is None:
        img = fetch_unsplash_image(category)
        if img:
            source = "unsplash"
            credit = get_unsplash_credit(category)
            print(f"    [image] Unsplash取得: category={category}")

    # ── 失敗時はデフォルト背景色画像を生成 ──────────
    if img is None:
        img = _make_fallback_image(category)
        source = "fallback"
        print(f"    [image] フォールバック生成: category={category}")

    # ── 後処理: リサイズ + オーバーレイ ──────────────
    final = apply_overlay(img, article_type, category)
    final.save(str(output_path), "JPEG", quality=90)
    print(f"    [image] 保存: {output_path}")

    return {
        "local_path": str(output_path),
        "source": source,
        "credit": credit,
    }


def _make_fallback_image(category: str) -> Image.Image:
    """画像取得が完全に失敗したときのグラデーション背景"""
    GRAD_COLORS: dict[str, tuple] = {
        "smartphone": ((17, 24, 39), (37, 99, 235)),
        "tablet":     ((17, 24, 39), (109, 40, 217)),
        "windows":    ((17, 24, 39), (6, 95, 70)),
        "cpu_gpu":    ((17, 24, 39), (180, 83, 9)),
        "ai":         ((17, 24, 39), (124, 58, 237)),
        "general":    ((17, 24, 39), (55, 65, 81)),
    }
    c1, c2 = GRAD_COLORS.get(category, GRAD_COLORS["general"])
    img = Image.new("RGB", (TARGET_W, TARGET_H), c1)
    draw = ImageDraw.Draw(img)
    for x in range(TARGET_W):
        ratio = x / TARGET_W
        r = int(c1[0] + (c2[0] - c1[0]) * ratio)
        g = int(c1[1] + (c2[1] - c1[1]) * ratio)
        b = int(c1[2] + (c2[2] - c1[2]) * ratio)
        draw.line([(x, 0), (x, TARGET_H)], fill=(r, g, b))
    return img


# ─────────────────────────────────────────────
# スタンドアロン動作確認
# ─────────────────────────────────────────────

if __name__ == "__main__":
    test_cases = [
        {
            "title": "AMD EXPO 1.2が登場——MRDIMMに正式対応",
            "category": "cpu_gpu",
            "article_type": "A型速報",
            "slug": "amd-expo-1-2-test",
        },
        {
            "title": "iPhone 17 Pro Maxのダミーユニット比較で厚さ増加が判明",
            "category": "smartphone",
            "article_type": "C型リーク",
            "slug": "iphone-17-pro-max-leak-test",
        },
        {
            "title": "OpenAI、ChatGPTに企業向けWorkspace Agentsを追加",
            "category": "ai",
            "article_type": "A型速報",
            "slug": "openai-workspace-agents-test",
        },
    ]

    for case in test_cases:
        print(f"\n[{case['title'][:40]}...]")
        result = fetch_article_image(**case)
        print(f"  → source={result['source']}, path={result['local_path']}")
        if result["credit"]:
            print(f"  → credit: {result['credit']}")
