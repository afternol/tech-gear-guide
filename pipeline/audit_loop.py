# -*- coding: utf-8 -*-
"""
Tech Gear Guide — audit_loop.py
audit.py → correct.py を最大 MAX_ITERATIONS 回繰り返して記事の正確性を担保する。

終了条件（いずれか早い方）:
  1. 全記事が PASS になった
  2. 前回ループと FAIL+WARN 件数が変わらなかった（収束）
  3. MAX_ITERATIONS 回に達した

使い方:
  python audit_loop.py           # audit→correct を最大3回ループ後 publish
  python audit_loop.py --no-publish   # publish は実行しない
  python audit_loop.py --max-iter 2   # ループ上限を変える
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
MAX_ITERATIONS = 7   # 上限（全PASS時は早期終了）
MIN_ITERATIONS = 4   # 必ずこの回数はaudit→correctを実施する


# ─────────────────────────────────────────────
# ヘルパー
# ─────────────────────────────────────────────

def read_report() -> dict[str, int]:
    """audit_report.jsonl から PASS/WARN/FAIL 件数を返す"""
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
    """FAIL件数のみを返す（収束判定に使用）"""
    return read_report().get("FAIL", 0)


def run_step(label: str, cmd: list[str]) -> bool:
    """サブプロセスを実行。成功なら True を返す。"""
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
    return (f"PASS {p} / WARN {w} / FAIL {f}  "
            f"[PASS率 {pct:.0f}%]")


# ─────────────────────────────────────────────
# メイン
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-iter",    type=int, default=MAX_ITERATIONS,
                        help=f"最大ループ回数（デフォルト {MAX_ITERATIONS}）")
    parser.add_argument("--min-iter",   type=int, default=MIN_ITERATIONS,
                        help=f"最低保証ループ回数（デフォルト {MIN_ITERATIONS}）")
    parser.add_argument("--no-publish", action="store_true",
                        help="最終 publish をスキップする")
    parser.add_argument("--no-web-check", action="store_true",
                        help="ウェブ検索ファクトチェックをスキップ（コスト節約）")
    args = parser.parse_args()

    if not ARTICLES_PATH.exists():
        print("generated_articles.jsonl が見つかりません。generate.py を先に実行してください。")
        return

    py = sys.executable
    prev_fail = None   # 前回ループの FAIL 件数（収束判定: FAILのみで判断）
    no_improve_count = 0  # FAIL が改善しなかった連続回数

    for iteration in range(1, args.max_iter + 1):
        print(f"\n{'='*60}")
        print(f"  ループ {iteration} / {args.max_iter}  （最低保証: {args.min_iter} 回）")
        print(f"{'='*60}")

        # ── audit ──────────────────────────────────────
        # イテレーション1: フルAI（事実＋品質＋ウェブ検索）
        # 2回目以降: 事実チェック＋ウェブ検索のみ（品質はスキップ）
        audit_cmd = [py, "audit.py"]
        if iteration >= 2:
            audit_cmd.append("--no-quality-check")
        if args.no_web_check:
            audit_cmd.append("--no-web-check")

        label = "フルAI" if iteration == 1 else "事実＋WEB"
        if args.no_web_check:
            label = "フルAI（WEBなし）" if iteration == 1 else "事実チェックのみ"

        if not run_step(f"audit.py（{label}）", audit_cmd):
            break

        counts = read_report()
        print(f"\n  監査結果: {bar(counts)}")

        fail          = counts.get("FAIL", 0)
        warn          = counts.get("WARN", 0)
        force_continue = iteration < args.min_iter  # 最低回数未満は強制続行

        # ── 終了判定（最低回数を超えた場合のみ有効）──────
        # ★ 収束判定は FAIL のみで行う（WARN は許容）
        if not force_continue:
            if fail == 0:
                if warn == 0:
                    print(f"\n  ✅ 全記事 PASS 達成（{iteration} ループ目）")
                else:
                    print(f"\n  ✅ FAIL ゼロ達成（WARN {warn} 件は許容範囲）（{iteration} ループ目）")
                break

            if prev_fail is not None and fail >= prev_fail:
                no_improve_count += 1
                print(f"\n  FAIL が改善しませんでした（{prev_fail} → {fail}）。連続 {no_improve_count} 回。")
                # 2回連続改善なしで打ち切り
                if no_improve_count >= 2:
                    print(f"  ⚠️  2回連続 FAIL 改善なし。ループを打ち切ります。")
                    break
                # 1回なら correct で再挑戦
                print(f"  → correct で再修正を試みます。")
            else:
                no_improve_count = 0

            if iteration == args.max_iter:
                print(f"\n  ⚠️  最大ループ数（{args.max_iter}）に達しました。残存 WARN/FAIL は許容して続行します。")
                break
        else:
            print(f"  → 最低保証 {args.min_iter} 回未満のため、収束・PASS 判定をスキップして続行します。")

        prev_fail = fail

        # ── correct ────────────────────────────────────
        if not run_step("correct.py", [py, "correct.py"]):
            break

    # ── 最終サマリー ────────────────────────────────────
    final = read_report()
    print(f"\n{'='*60}")
    print(f"  ループ完了 — 最終監査結果: {bar(final)}")
    print(f"{'='*60}")

    if args.no_publish:
        print("\n  --no-publish 指定のため publish.py はスキップします。")
        return

    # ── publish ─────────────────────────────────────────
    print()
    run_step("publish.py", [py, "publish.py"])


if __name__ == "__main__":
    main()
