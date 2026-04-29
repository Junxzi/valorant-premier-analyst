"""Render aggregated DataFrames as a Japanese-language Markdown report."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

PLAYER_HEADER = (
    "| player | tag | agent | games | avg_kills | avg_deaths | "
    "avg_assists | avg_score | kd_ratio |"
)
PLAYER_SEPARATOR = (
    "|---|---|---|---:|---:|---:|---:|---:|---:|"
)

MAP_HEADER = "| map | games | avg_match_length_min |"
MAP_SEPARATOR = "|---|---:|---:|"


def _fmt_int(value: object) -> str:
    if value is None or pd.isna(value):
        return "-"
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return str(value)


def _fmt_float(value: object, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "-"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def _fmt_str(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "-"
    text = str(value).strip()
    return text if text else "-"


def _player_rows(df: pd.DataFrame) -> list[str]:
    rows: list[str] = []
    for _, row in df.iterrows():
        rows.append(
            "| {name} | {tag} | {agent} | {games} | {ak} | {ad} | "
            "{aa} | {asc} | {kd} |".format(
                name=_fmt_str(row.get("name")),
                tag=_fmt_str(row.get("tag")),
                agent=_fmt_str(row.get("agent")),
                games=_fmt_int(row.get("games")),
                ak=_fmt_float(row.get("avg_kills")),
                ad=_fmt_float(row.get("avg_deaths")),
                aa=_fmt_float(row.get("avg_assists")),
                asc=_fmt_float(row.get("avg_score"), digits=1),
                kd=_fmt_float(row.get("kd_ratio")),
            )
        )
    return rows


def _map_rows(df: pd.DataFrame) -> list[str]:
    rows: list[str] = []
    for _, row in df.iterrows():
        rows.append(
            "| {m} | {g} | {l} |".format(
                m=_fmt_str(row.get("map_name")),
                g=_fmt_int(row.get("games")),
                l=_fmt_float(row.get("avg_match_length_min"), digits=1),
            )
        )
    return rows


def build_markdown_report(
    player_summary_df: pd.DataFrame,
    map_summary_df: pd.DataFrame | None = None,
) -> str:
    """Build the Markdown body string for the analysis report."""
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines: list[str] = []
    lines.append("# Valorant Premier Analyst Report")
    lines.append("")
    lines.append(f"_生成日時: {generated_at}_")
    lines.append("")

    lines.append("## 個人成績サマリー")
    lines.append("")
    if player_summary_df is None or player_summary_df.empty:
        lines.append(
            "> プレイヤーデータがありません。`fetch` コマンドで試合履歴を取得してください。"
        )
    else:
        lines.append(PLAYER_HEADER)
        lines.append(PLAYER_SEPARATOR)
        lines.extend(_player_rows(player_summary_df))
    lines.append("")

    lines.append("## マップ別サマリー")
    lines.append("")
    if map_summary_df is None or map_summary_df.empty:
        lines.append("> マップ別データがありません（または未集計）。")
    else:
        lines.append(MAP_HEADER)
        lines.append(MAP_SEPARATOR)
        lines.extend(_map_rows(map_summary_df))
    lines.append("")

    lines.append("## 初期コメント")
    lines.append("")
    lines.append("- 現時点ではスコアボード由来の基本分析のみです。")
    lines.append("- 今後、ラウンド別・攻守別分析を追加予定です。")
    lines.append("- 勝敗・First Blood・経済状況などの指標は順次拡張していきます。")
    lines.append("- LLMによる自然言語レポート生成は将来のTODOです。")
    lines.append("")

    return "\n".join(lines)


def save_markdown_report(report_text: str, output_path: Path) -> None:
    """Persist a Markdown report to disk, creating parent directories if needed."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_text, encoding="utf-8")
