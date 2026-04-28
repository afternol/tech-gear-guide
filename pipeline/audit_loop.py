# -*- coding: utf-8 -*-
"""
Tech Gear Guide — audit_loop.py
audit.py → correct.py を最大 MAX_ITERATIONS 回繰り返して記事の正確性を担保する。
FAIL除外で目標公開数を下回った場合、未使用ソースから補充生成して再公開する。

終了条件（いずれか早い方）:
  1. 全記事が PASS になった
  2. 前回ループと FAIL+WARN 件数が変わらなかった（収束）
  3. MAX_ITERATIONS 回に達した

使い方:
  python audit_loop.py                     # audit→correct を最大7回ループ後 publish
  python audit_loop.py --target 30         # 目標公開数30件（デフォルト）
  python audit_loop.py --no-publish        # publish は実行しない
  python audit_loop.py --max-iter 2        # ループ上限を変える
  python audit_loop.py --no-web-check      # ウェブ検索をスキップ（コスト節約）
"""

import argparse
import io
import json
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPORT_PATH    = Path("audit_report.jsonl")
ARTICLES_PATH  = Path("generated_articles.jsonl")
COLLECTED_PATH = Path("collected_articles.jsonl")
LOG_PATH       = Path("published_log.jsonl")
MAX_ITERATIONS = 7
MIN_ITERATIONS = 4
MAX_REFILL_ROUNDS = 2   # 補充サイクルの最大回数


# ─────────────────────────────────────────────
# ヘルパー
# ─────────────────────────────────────────────

def read_report() -> dict[str, int]:
    counts: dict[str, int] = {"PASS": 0, "WARN": 0, "FAIL": 0}
    if not REPORT_PATH.exists():
        return counts
    with open(REPORT_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                s = r.get("status", "FAIL")
                counts[s] = counts.get(s, 0) + 1
    return counts


def read_fail_count() -> int:
    return read_report().get("FAIL", 0)


def count_articles_in_file() -> int:
    """generated_articles.jsonl の現在の件数"""
    if not ARTICLES_PATH.exists():
        return 0
    with open(ARTICLES_PATH, encoding="utf-8") as f:
        return sum(1 for l in f if l.strip())


def get_used_urls() -> set[str]:
    """generated_articles.jsonl に含まれる sources の URL 一覧（使用済みソース）"""
    urls: set[str] = set()
    if not ARTICLES_PATH.exists():
        return urls
    with open(ARTICLES_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                a = json.loads(line)
                for s in a.get("sources", []):
                    u = s.get("url", "")
                    if u:
                        urls.add(u)
    return urls


def count_published_in_log(batch_slugs: set[str]) -> int:
    """published_log.jsonl から今回のバッチで公開された件数"""
    if not LOG_PATH.exists():
        return 0
    count = 0
    with open(LOG_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                if d.get("slug") in batch_slugs and d.get("status") == "published":
                    count += 1
    return count


def get_collected_offset(used_urls: set[str]) -> int:
    """collected_articles.jsonl で使用済みURLがどこまであるか（offset）"""
    if not COLLECTED_PATH.exists():
        return 0
    offset = 0
    with open(COLLECTED_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                a = json.loads(line)
                if a.get("url", "") in used_urls:
                    offset += 1
                else:
                    break
    return offset


def count_unused_sources(used_urls: set[str]) -> int:
    """collected_articles.jsonl の未使用ソース件数"""
    if not COLLECTED_PATH.exists():
        return 0
    count = 0
    with open(COLLECTED_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                a = json.loads(line)
                if a.get("url", "") not in used_urls:
                    count += 1
    return count


def get_batch_slugs() -> set[str]:
    """generated_articles.jsonl の現在のスラッグ一覧"""
    slugs: set[str] = set()
    if not ARTICLES_PATH.exists():
        return slugs
    with open(ARTICLES_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                a = json.loads(line)
                s = a.get("slug", "")
                if s:
                    slugs.add(s)
    return slugs


def run_step(label: str, cmd: list[str]) -> bool:
    print(f"\n  ▶ {label}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"  ❌ {label} が異常終了（code={result.returncode}）")
        return False
    return True


def bar(counts: dict[str, int]) -> str:
    total = sum(counts.values())
    if total == 0:
        return "（記事なし）"
    p = counts.get("PASS", 0)
    w = counts.get("WARN", 0)
    f = counts.get("FAIL", 0)
    pct = p / total * 100
    return (f"PASS {p} / WARN {w} / FAIL {f}  [PASS率 {pct:.0f}%]")


# ─────────────────────────────────────────────
# 監査ループ（1バッチ分）
# ─────────────────────────────────────────────

def run_audit_loop(py: str, max_iter: int, min_iter: int,
                   no_web_check: bool, label: str = "") -> None:
    """audit → correct を max_iter 回ループする"""
    prev_fail = None
    no_improve_count = 0
    tag = f"[{label}] " if label else ""

    for iteration in range(1, max_iter + 1):
        print(f"\n{'='*60}")
        print(f"  {tag}ループ {iteration} / {max_iter}  （最低保証: {min_iter} 回）")
        print(f"{'='*60}")

        audit_cmd = [py, "audit.py"]
        if iteration >= 2:
            audit_cmd.append("--no-quality-check")
        if no_web_check:
            audit_cmd.append("--no-web-check")

        lbl = "フルAI" if iteration == 1 else "事実＋WEB"
        if no_web_check:
            lbl = "フルAI（WEBなし）" if iteration == 1 else "事実チェックのみ"

        if not run_step(f"audit.py（{lbl}）", audit_cmd):
            break

        counts = read_report()
        print(f"\n  監査結果: {bar(counts)}")

        fail          = counts.get("FAIL", 0)
        warn          = counts.get("WARN", 0)
        force_continue = iteration < min_iter

        if not force_continue:
            if fail == 0:
                msg = "全記事 PASS 達成" if warn == 0 else f"FAIL ゼロ達成（WARN {warn} 件は許容範囲）"
                print(f"\n  ✅ {msg}（{iteration} ループ目）")
                break

            if prev_fail is not None and fail >= prev_fail:
                no_improve_count += 1
                print(f"\n  FAIL が改善しませんでした（{prev_fail} → {fail}）。連続 {no_improve_count} 回。")
                if no_improve_count >= 2:
                    print(f"  ⚠️  2回連続 FAIL 改善なし。ループを打ち切ります。")
                    break
                print(f"  → correct で再修正を試みます。")
            else:
                no_improve_count = 0

            if iteration == max_iter:
                print(f"\n  ⚠️  最大ループ数（{max_iter}）に達しました。")
                break
        else:
            print(f"  → 最低保証 {min_iter} 回未満のため、収束・PASS 判定をスキップして続行します。")

        prev_fail = fail

        if not run_step("correct.py", [py, "correct.py"]):
            break

    final = read_report()
    print(f"\n{'='*60}")
    print(f"  {tag}ループ完了 — 最終監査結果: {bar(final)}")
    print(f"{'='*60}")


# ─────────────────────────────────────────────
# メイン
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-iter",    type=int, default=MAX_ITERATIONS)
    parser.add_argument("--min-iter",    type=int, default=MIN_ITERATIONS)
    parser.add_argument("--target",      type=int, default=30,
                        help="目標公開件数（不足時に未使用ソースから補充生成）")
    parser.add_argument("--no-publish",  action="store_true")
    parser.add_argument("--no-web-check", action="store_true")
    args = parser.parse_args()

    if not ARTICLES_PATH.exists():
        print("generated_articles.jsonl が見つかりません。generate.py を先に実行してください。")
        return

    py = sys.executable

    # ── メイン監査ループ ──────────────────────────────────
    run_audit_loop(py, args.max_iter, args.min_iter, args.no_web_check)

    if args.no_publish:
        print("\n  --no-publish 指定のため publish.py はスキップします。")
        return

    # ── 初回 publish ────────────────────────────────────
    batch_slugs   = get_batch_slugs()
    all_used_urls = get_used_urls()          # 使用済みURLを累積管理（generate.py は上書きするため）
    run_step("publish.py", [py, "publish.py"])

    # ── 補充サイクル ────────────────────────────────────
    for refill_round in range(1, MAX_REFILL_ROUNDS + 1):
        published = count_published_in_log(batch_slugs)
        shortage  = args.target - published

        if shortage <= 0:
            print(f"\n  ✅ 目標公開数 {args.target} 件達成（実績: {published} 件）")
            break

        # 未使用ソースの確認（累積済みURLで判定）
        unused_count = count_unused_sources(all_used_urls)

        print(f"\n{'='*60}")
        print(f"  🔄 補充サイクル {refill_round} / {MAX_REFILL_ROUNDS}")
        print(f"  公開済み: {published} 件 / 目標: {args.target} 件 / 不足: {shortage} 件")
        print(f"  未使用ソース: {unused_count} 件")
        print(f"{'='*60}")

        if unused_count == 0:
            print("  ⚠️  未使用ソースがありません。補充不可。")
            break

        # 補充件数は不足分と未使用ソース数の小さい方
        refill_count = min(shortage, unused_count)
        offset       = len(all_used_urls)    # 累積使用済みURL数をoffsetとして使用

        print(f"  → {refill_count} 件を offset={offset} から追加生成します。")

        # 補充生成（generate.py は generated_articles.jsonl を上書きする）
        if not run_step(
            f"generate.py（補充: {refill_count}件）",
            [py, "generate.py", "--offset", str(offset), "--max", str(refill_count)],
        ):
            break

        # 補充分の監査（2ループ・最低2回保証）
        run_audit_loop(py, max_iter=4, min_iter=2,
                       no_web_check=args.no_web_check,
                       label=f"補充R{refill_round}")

        # 補充分 publish（上書き後のファイルからURLを累積追加）
        new_slugs      = get_batch_slugs() - batch_slugs
        all_used_urls |= get_used_urls()     # 補充記事のURLを累積セットに追加
        batch_slugs   |= new_slugs
        run_step("publish.py（補充分）", [py, "publish.py"])

    # ── 最終サマリー ────────────────────────────────────
    final_published = count_published_in_log(batch_slugs)
    print(f"\n{'='*60}")
    print(f"  📊 最終公開件数: {final_published} 件 / 目標: {args.target} 件")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
