"""Render the calculated model results as a self-contained, readable HTML report."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


SOURCE = Path("model_output/risk_trend_model_results.json")
OUTPUT_DIR = Path("model_output")
# Shown as both the browser-tab title and the page heading.
REPORT_TITLE = "风险趋势日度结果"

SIGNAL_FILTERS = ["无", "局部底左侧信号", "局部底右侧信号", "局部顶左侧信号", "局部顶右侧信号"]
# 展示顺序；数据里出现的其他类别会按首次出现顺序接在后面，不会被丢掉。
CATEGORY_ORDER = ["宽基指数", "商品期货", "申万一级行业"]
RESULT_COLUMNS = [
    "日期", "代码", "简称", "类别", "总市值(亿元)", "成交额(亿元)", "收盘价", "当日涨跌幅(%)",
    "风险度", "综合动量", "TMP", "JAX", "综合评分", "局部顶底提示建议",
]


def text(value: Any) -> str:
    return "" if value is None else html.escape(str(value))


def number(value: Any, decimals: int = 2) -> str:
    return "—" if value is None else f"{float(value):,.{decimals}f}"


def score_class(value: Any) -> str:
    if value is None:
        return ""
    return "score-high" if value >= 65 else "score-low" if value < 35 else ""


def risk_class(value: Any) -> str:
    if value is None:
        return ""
    return "risk-high" if value > 85 else "risk-low" if value < 20 else ""


def direction_class(value: str) -> str:
    return "up" if value == "上涨" else "down" if value == "下跌" else ""


def signal_group(value: str) -> str:
    """Group signal 1/2 repetitions under the same selectable signal type."""
    if value in {"无", ""}:
        return "无"
    return value[:-1] if value.endswith(("1", "2")) else value


def result_cells(row: dict[str, Any]) -> list[tuple[str, str]]:
    """(css class, rendered value) per column, in RESULT_COLUMNS order."""
    return [
        ("", text(row["日期"])),
        ("code", text(row["代码"])),
        ("", text(row["简称"])),
        ("cat", text(row["类别"])),
        ("num", number(row["总市值(亿元)"])),
        ("num", number(row["成交额(亿元)"])),
        ("num", number(row["收盘价"], 4)),
        ("num", number(row["当日涨跌幅(%)"])),
        (f"num {risk_class(row['风险度'])}", number(row["风险度"])),
        ("num", number(row["综合动量"])),
        (direction_class(row["TMP"]), text(row["TMP"])),
        (direction_class(row["JAX"]), text(row["JAX"])),
        (f"num {score_class(row['综合评分'])}", number(row["综合评分"])),
        ("signal", text(row["局部顶底提示建议"])),
    ]


def result_row(row: dict[str, Any]) -> str:
    group = signal_group(row["局部顶底提示建议"])
    body = "".join(
        f"<td data-result-column='{index}'"
        + (f" class='{css.strip()}'" if css.strip() else "")
        + f">{value}</td>"
        for index, (css, value) in enumerate(result_cells(row))
    )
    return (f"<tr data-date='{text(row['日期'])}' data-name='{text(row['简称'])}' "
            f"data-category='{text(row['类别'])}' data-signal-group='{text(group)}'>"
            f"{body}</tr>")


def audit_row(row: dict[str, Any]) -> str:
    columns = [
        text(row["日期"]), text(row["代码"]), text(row["简称"]), text(row["类别"]),
        number(row["TR"]), number(row["TREND"]), number(row["TMP_SLOPE"], 4), number(row["JAX_SLOPE"], 4),
        number(row["TMP_PCT"], 4), number(row["JAX_PCT"], 4), number(row["短期动量"]), number(row["中期动量"]),
        number(row["综合动量"]), number(row["综合评分"]), text(row["原始信号连续天数"]), text(row["局部顶底提示建议"]),
    ]
    num_indices = {4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14}
    cells = ("<td{}>{}</td>".format(" class='num'" if index in num_indices else "", value)
             for index, value in enumerate(columns))
    return "<tr>" + "".join(cells) + "</tr>"


def coverage_row(row: dict[str, Any]) -> str:
    return "<tr>" + "".join([
        f"<td>{text(row['代码'])}</td>", f"<td>{text(row['简称'])}</td>", f"<td>{text(row['类别'])}</td>",
        f"<td>{text(row['Wind最早有效日'])}</td>", f"<td>{text(row['Wind最后有效日'])}</td>",
        f"<td class='num'>{number(row['历史有效日数'], 0)}</td>", f"<td class='num'>{number(row['交付区间有效日数'], 0)}</td>",
    ]) + "</tr>"


def main() -> None:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    records = data["records"]
    audit = data["audit_records"]
    coverage = data["coverage"]
    metadata = data["metadata"]
    records_html = "\n".join(result_row(row) for row in records)
    audit_html = "\n".join(audit_row(row) for row in audit)
    coverage_html = "\n".join(coverage_row(row) for row in coverage)
    metadata_html = "\n".join(f"<li><strong>{html.escape(key)}：</strong>{html.escape(str(value))}</li>" for key, value in metadata.items())
    available_dates = sorted({row["日期"] for row in records})
    # Name the files after the delivered range so a new run never overwrites an
    # earlier trading day's report.
    span = f"{available_dates[0].replace('-', '')}_{available_dates[-1].replace('-', '')}"
    target = OUTPUT_DIR / f"风险趋势日度择时模型结果_{span}.html"
    clean_target = OUTPUT_DIR / f"风险趋势日度择时模型结果_{span}_简版.html"
    date_options_html = "\n".join(
        f"<label><input type='checkbox' data-date-filter='{html.escape(date)}' checked> {html.escape(date)}</label>"
        for date in available_dates
    )
    # dict.fromkeys 保留 records 的顺序（已按日期、代码排序），简称因此按代码升序，
    # 宽基与申万行业各自聚拢，比按字符编码排序更好定位。
    available_names = list(dict.fromkeys(row["简称"] for row in records))
    name_options_html = "\n".join(
        f"<label><input type='checkbox' data-name-filter='{html.escape(name)}' checked> {html.escape(name)}</label>"
        for name in available_names
    )
    seen_categories = list(dict.fromkeys(row["类别"] for row in records))
    available_categories = ([c for c in CATEGORY_ORDER if c in seen_categories]
                            + [c for c in seen_categories if c not in CATEGORY_ORDER])
    category_options_html = "\n".join(
        f"<label><input type='checkbox' data-category-filter='{html.escape(name)}' checked> {html.escape(name)}</label>"
        for name in available_categories
    )
    # 表头由 RESULT_COLUMNS 生成，列数与 result_cells 不一致时直接报错而非静默错位
    if records and len(result_cells(records[0])) != len(RESULT_COLUMNS):
        raise RuntimeError("result_cells 与 RESULT_COLUMNS 列数不一致")
    header_cells_html = "".join(
        f"<th data-result-column='{index}'>{html.escape(label)}</th>"
        for index, label in enumerate(RESULT_COLUMNS)
    )
    signal_options_html = "\n".join(
        f"<label><input type='checkbox' data-signal-filter='{html.escape(signal)}' checked> {html.escape(signal)}</label>"
        for signal in SIGNAL_FILTERS
    )
    column_options_html = "\n".join(
        f"<label><input type='checkbox' data-column-toggle='{index}' checked> {html.escape(label)}</label>"
        for index, label in enumerate(RESULT_COLUMNS)
    )

    # The 简版 keeps the heading but drops the data-source note from the subtitle.
    header_section = (f"<header><h1>{REPORT_TITLE}</h1><div class='subtitle'>"
                      f"{html.escape(metadata['结果区间'])}｜基于 Wind 日度行情全历史计算</div></header>")
    header_clean = (f"<header><h1>{REPORT_TITLE}</h1><div class='subtitle'>"
                    f"{html.escape(metadata['结果区间'])}</div></header>")

    # Sections the 简版 drops.  They are built once and substituted into the
    # document, so removing them is a lookup rather than a byte-exact re-match
    # of markup duplicated in two places.
    note_section = (f"<section class='note'><strong>口径与数据说明</strong><ul>{metadata_html}"
                    "<li><strong>字段缺失：</strong>中证转债（000832.CSI）与 SHFE黄金（AU.SHF）的总市值字段在 Wind 中"
                    "未提供，按“—”展示；其他结果字段均已返回。</li></ul></section>")
    audit_section = ("<details><summary>查看计算审计字段（TR、TREND、TMP/JAX SLOPE、分位数与连续天数）</summary>"
                     "<div class='table-wrap'><table><thead><tr><th>日期</th><th>代码</th><th>简称</th><th>类别</th>"
                     "<th>TR</th><th>TREND</th><th>TMP_SLOPE</th><th>JAX_SLOPE</th><th>TMP_PCT</th><th>JAX_PCT</th>"
                     "<th>短期动量</th><th>中期动量</th><th>综合动量</th><th>综合评分</th><th>原始信号连续天数</th>"
                     f"<th>局部顶底提示建议</th></tr></thead><tbody>{audit_html}</tbody></table></div></details>")
    coverage_section = ("<details><summary>查看数据覆盖（每个指数从 Wind 最早有效日开始计算）</summary>"
                        "<div class='table-wrap'><table><thead><tr><th>代码</th><th>简称</th><th>类别</th>"
                        "<th>Wind最早有效日</th><th>Wind最后有效日</th><th>历史有效日数</th><th>交付区间有效日数</th>"
                        f"</tr></thead><tbody>{coverage_html}</tbody></table></div></details>")
    footer_section = ("<footer>生成方式：WindPy 历史日线 + 《技术面指标完整构建流程与逻辑（通用版）》口径。"
                      "评分显示保留两位小数，计算保留原始精度。</footer>")

    document = f"""<!doctype html>
<html lang='zh-CN'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>{REPORT_TITLE}</title>
<style>
  :root {{ --navy:#17365d; --blue:#d9eaf7; --line:#d9e1f2; --up:#c00000; --down:#008000; --muted:#5b6573; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:#f5f7fa; color:#172033; font-family:"Microsoft YaHei","PingFang SC",Arial,sans-serif; font-size:13px; }}
  .page {{ max-width:1800px; margin:0 auto; padding:28px; }}
  header {{ background:var(--navy); color:#fff; padding:24px 28px; border-radius:8px 8px 0 0; }}
  h1 {{ margin:0; font-size:25px; }} .subtitle {{ margin-top:8px; opacity:.84; }}
  .summary {{ display:flex; gap:14px; flex-wrap:wrap; padding:16px 0; }}
  .card {{ background:#fff; min-width:160px; padding:13px 17px; border-left:4px solid #2f75b5; box-shadow:0 1px 3px #dfe4ed; }}
  .card strong {{ display:block; font-size:21px; color:#17365d; }} .card span {{ color:var(--muted); }}
  .note {{ background:#fff; padding:16px 20px; margin-bottom:16px; border:1px solid var(--line); }}
  .toolbar {{ background:#fff; border:1px solid var(--line); border-bottom:0; padding:11px 16px; display:flex; align-items:center; flex-wrap:wrap; gap:12px; color:#17365d; font-weight:600; }}
  .filter-picker,.column-picker {{ position:relative; }} .filter-picker summary,.column-picker summary {{ cursor:pointer; border:1px solid #9dc3e6; border-radius:3px; padding:6px 9px; background:#fff; list-style:none; }} .filter-picker summary::-webkit-details-marker,.column-picker summary::-webkit-details-marker {{ display:none; }}
  .filter-picker[open] summary,.column-picker[open] summary {{ border-bottom-left-radius:0; border-bottom-right-radius:0; background:#d9eaf7; }} .filter-list,.column-list {{ position:absolute; z-index:3; top:31px; width:220px; max-height:310px; overflow-y:auto; padding:9px 11px; border:1px solid #9dc3e6; background:#fff; box-shadow:0 3px 10px #bac5d3; }} .filter-list {{ left:0; }} .column-list {{ right:0; }} .filter-list label,.column-list label {{ display:block; padding:4px 0; color:#172033; font-weight:400; }} .filter-actions {{ display:flex; gap:8px; padding-bottom:7px; margin-bottom:5px; border-bottom:1px solid #d9e1f2; }} .filter-actions button {{ cursor:pointer; border:1px solid #9dc3e6; border-radius:3px; padding:3px 7px; background:#f7fbff; color:#17365d; font:inherit; font-size:12px; }} .column-hidden {{ display:none; }}
  .sort-pick {{ display:flex; align-items:center; gap:6px; }} .sort-pick select {{ cursor:pointer; border:1px solid #9dc3e6; border-radius:3px; padding:5px 7px; background:#fff; color:#17365d; font:inherit; }}
  .cat {{ color:#1f4e78; }}
  #visible-count {{ color:var(--muted); font-weight:400; }}
  .note ul {{ margin:7px 0 0; padding-left:20px; line-height:1.65; }}
  h2 {{ font-size:16px; margin:0; padding:12px 16px; color:#fff; background:#1f4e78; }}
  .table-wrap {{ overflow:auto; max-height:740px; background:#fff; border:1px solid var(--line); }}
  table {{ border-collapse:collapse; width:max-content; min-width:100%; white-space:nowrap; }}
  th {{ position:sticky; top:0; z-index:1; padding:10px 9px; background:var(--blue); color:#17365d; text-align:center; border-bottom:2px solid #9dc3e6; }}
  td {{ padding:8px 9px; border-bottom:1px solid #edf1f6; }}
  tr:nth-child(even) td {{ background:#fbfdff; }} tr:hover td {{ background:#fff6d9; }}
  .num {{ text-align:right; font-variant-numeric:tabular-nums; }} .code {{ font-family:Consolas,monospace; }}
  .up {{ color:var(--up); font-weight:600; text-align:center; }} .down {{ color:var(--down); font-weight:600; text-align:center; }}
  .risk-high {{ color:#c00000; font-weight:700; }} .risk-low {{ color:#0070c0; font-weight:700; }}
  .score-high {{ color:#c00000; font-weight:700; }} .score-low {{ color:#0070c0; font-weight:700; }}
  .signal {{ color:#7f6000; font-weight:600; }} details {{ margin-top:16px; background:#fff; border:1px solid var(--line); }} summary {{ cursor:pointer; padding:12px 16px; color:#17365d; font-weight:700; }}
  footer {{ color:var(--muted); margin:18px 0 6px; font-size:12px; }}
</style>
</head>
<body><main class='page'>
{header_section}
<section class='summary'><div class='card'><strong>{len(coverage)}</strong><span>覆盖指数</span></div><div class='card'><strong>{len(set(row['日期'] for row in records))}</strong><span>交易日</span></div><div class='card'><strong>{len(records)}</strong><span>结果记录</span></div><div class='card'><strong>{sum(row['局部顶底提示建议'] != '无' for row in records)}</strong><span>触发提示</span></div></section>
{note_section}
<h2>结果明细</h2>
<div class='toolbar'><details class='filter-picker'><summary id='date-filter-summary'>日期（全部）</summary><div class='filter-list'><div class='filter-actions'><button type='button' data-filter-action='dates-all'>全选</button><button type='button' data-filter-action='dates-none'>清空</button></div>{date_options_html}</div></details><details class='filter-picker'><summary id='name-filter-summary'>简称（全部）</summary><div class='filter-list'><div class='filter-actions'><button type='button' data-filter-action='names-all'>全选</button><button type='button' data-filter-action='names-none'>清空</button></div>{name_options_html}</div></details><details class='filter-picker'><summary id='category-filter-summary'>类别（全部）</summary><div class='filter-list'><div class='filter-actions'><button type='button' data-filter-action='categories-all'>全选</button><button type='button' data-filter-action='categories-none'>清空</button></div>{category_options_html}</div></details><details class='filter-picker'><summary id='signal-filter-summary'>顶底提示（全部）</summary><div class='filter-list'><div class='filter-actions'><button type='button' data-filter-action='signals-all'>全选</button><button type='button' data-filter-action='signals-none'>清空</button></div>{signal_options_html}</div></details><label class='sort-pick'>日期排序<select id='date-sort'><option value='asc'>升序（早→晚）</option><option value='desc'>降序（晚→早）</option></select></label><details class='column-picker'><summary>显示/隐藏列</summary><div class='column-list'>{column_options_html}</div></details><span id='visible-count'></span></div>
<div class='table-wrap'><table id='result-table'><thead><tr>{header_cells_html}</tr></thead><tbody id='result-body'>{records_html}</tbody></table></div>
{audit_section}
{coverage_section}
{footer_section}
</main><script>
(() => {{
  const rows = Array.from(document.querySelectorAll('#result-body tr'));
  const count = document.getElementById('visible-count');
  const table = document.getElementById('result-table');
  const dateInputs = Array.from(document.querySelectorAll('[data-date-filter]'));
  const nameInputs = Array.from(document.querySelectorAll('[data-name-filter]'));
  const categoryInputs = Array.from(document.querySelectorAll('[data-category-filter]'));
  const signalInputs = Array.from(document.querySelectorAll('[data-signal-filter]'));
  const dateSummary = document.getElementById('date-filter-summary');
  const nameSummary = document.getElementById('name-filter-summary');
  const categorySummary = document.getElementById('category-filter-summary');
  const signalSummary = document.getElementById('signal-filter-summary');
  const body = document.getElementById('result-body');
  const sortSelect = document.getElementById('date-sort');
  // 记下初始顺序（按日期、代码升序），同日内据此保持代码升序，排序只翻转日期
  rows.forEach((row, index) => {{ row.dataset.order = index; }});
  const selectedValues = (inputs, attribute) => new Set(inputs.filter((input) => input.checked).map((input) => input.dataset[attribute]));
  const updateSummary = (summary, label, selected, total) => {{
    summary.textContent = selected === total ? `${{label}}（全部）` : `${{label}}（已选 ${{selected}}/${{total}}）`;
  }};
  const applyFilters = () => {{
    const selectedDates = selectedValues(dateInputs, 'dateFilter');
    const selectedNames = selectedValues(nameInputs, 'nameFilter');
    const selectedCategories = selectedValues(categoryInputs, 'categoryFilter');
    const selectedSignals = selectedValues(signalInputs, 'signalFilter');
    let visible = 0;
    rows.forEach((row) => {{
      const show = selectedDates.has(row.dataset.date) && selectedNames.has(row.dataset.name)
        && selectedCategories.has(row.dataset.category)
        && selectedSignals.has(row.dataset.signalGroup);
      row.hidden = !show;
      if (show) visible += 1;
    }});
    count.textContent = `显示 ${{visible}} / ${{rows.length}} 条`;
    updateSummary(dateSummary, '日期', selectedDates.size, dateInputs.length);
    updateSummary(nameSummary, '简称', selectedNames.size, nameInputs.length);
    updateSummary(categorySummary, '类别', selectedCategories.size, categoryInputs.length);
    updateSummary(signalSummary, '顶底提示', selectedSignals.size, signalInputs.length);
  }};
  dateInputs.concat(nameInputs, categoryInputs, signalInputs)
    .forEach((checkbox) => checkbox.addEventListener('change', applyFilters));
  const applySort = () => {{
    const descending = sortSelect.value === 'desc';
    const ordered = rows.slice().sort((a, b) => {{
      const byDate = a.dataset.date.localeCompare(b.dataset.date);
      if (byDate !== 0) return descending ? -byDate : byDate;
      return Number(a.dataset.order) - Number(b.dataset.order);
    }});
    // 一次性搬进 fragment 再回插，避免逐行 appendChild 触发上千次重排
    const fragment = document.createDocumentFragment();
    ordered.forEach((row) => fragment.appendChild(row));
    body.appendChild(fragment);
  }};
  sortSelect.addEventListener('change', applySort);
  document.querySelectorAll('[data-filter-action]').forEach((button) => {{
    button.addEventListener('click', () => {{
      const action = button.dataset.filterAction;
      const inputs = action.startsWith('dates') ? dateInputs
        : action.startsWith('names') ? nameInputs
        : action.startsWith('categories') ? categoryInputs : signalInputs;
      const checked = action.endsWith('all');
      inputs.forEach((input) => {{ input.checked = checked; }});
      applyFilters();
    }});
  }});
  document.querySelectorAll('[data-column-toggle]').forEach((checkbox) => {{
    checkbox.addEventListener('change', () => {{
      const column = checkbox.dataset.columnToggle;
      table.querySelectorAll(`[data-result-column="${{column}}"]`).forEach((cell) => {{
        cell.classList.toggle('column-hidden', !checkbox.checked);
      }});
    }});
  }});
  applySort();
  applyFilters();
}})();
</script></body></html>"""
    clean_document = (
        document
        .replace(header_section, header_clean)
        .replace(note_section, "")
        .replace(audit_section, "")
        .replace(coverage_section, "")
        .replace(footer_section, "")
    )
    for name, section in [("header", header_section), ("note", note_section), ("audit", audit_section),
                          ("coverage", coverage_section), ("footer", footer_section)]:
        if section in clean_document:
            raise RuntimeError(f"简版未能移除 {name} 区块")
    target.write_text(document, encoding="utf-8")
    clean_target.write_text(clean_document, encoding="utf-8")
    print(f"Rendered {len(records)} results to {target.resolve()}")
    print(f"Rendered clean report to {clean_target.resolve()}")


if __name__ == "__main__":
    main()
