import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import calendar
import re

st.set_page_config(page_title="NinjaTrader Backtest Analyzer", layout="wide")

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    .metric-card {
        background: #1e1e2f;
        border-radius: 12px;
        padding: 18px 20px;
        text-align: center;
        border: 1px solid #2d2d44;
    }
    .metric-label {
        color: #8a8aa3;
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
    }
    .metric-value {
        color: #ffffff;
        font-size: 1.55rem;
        font-weight: 700;
    }
    .metric-value.green { color: #00c853; }
    .metric-value.red   { color: #ff5252; }
    .summary-card {
        background: #1e1e2f;
        border-radius: 12px;
        padding: 20px 24px;
        border: 1px solid #2d2d44;
    }
    .summary-row {
        display: flex;
        justify-content: space-between;
        padding: 8px 0;
        border-bottom: 1px solid #2d2d44;
    }
    .summary-row:last-child { border-bottom: none; }
    .summary-key { color: #8a8aa3; font-size: 0.88rem; }
    .summary-val { color: #ffffff; font-size: 0.88rem; font-weight: 600; }
    .tooltip-wrap { position: relative; cursor: help; }
    .tooltip-wrap .tooltip-text {
        visibility: hidden;
        background: #2d2d44;
        color: #fff;
        text-align: center;
        border-radius: 6px;
        padding: 5px 10px;
        position: absolute;
        z-index: 10;
        bottom: 125%;
        left: 50%;
        transform: translateX(-50%);
        white-space: nowrap;
        font-size: 0.78rem;
        font-weight: 500;
        box-shadow: 0 2px 8px rgba(0,0,0,0.4);
    }
    .tooltip-wrap:hover .tooltip-text { visibility: visible; }

    /* Monthly returns table */
    .monthly-table { border-collapse: collapse; width: 100%; font-size: 0.82rem; }
    .monthly-table th {
        background: #1e1e2f;
        color: #8a8aa3;
        padding: 8px 6px;
        text-align: center;
        font-weight: 600;
        border: 1px solid #2d2d44;
    }
    .monthly-table td {
        padding: 7px 6px;
        text-align: center;
        border: 1px solid #2d2d44;
        font-weight: 500;
    }
    .monthly-table .pos { background: #0d3320; color: #00c853; }
    .monthly-table .neg { background: #3b1010; color: #ff5252; }
    .monthly-table .zero { background: #1a1a2e; color: #8a8aa3; }
    .monthly-table .year-cell {
        background: #1e1e2f;
        color: #ffffff;
        font-weight: 700;
        text-align: left;
        padding-left: 12px;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def parse_profit(val):
    """Parse NinjaTrader profit strings like '$558.00' or '($119.00)'."""
    if pd.isna(val):
        return 0.0
    s = str(val).strip()
    negative = "(" in s
    s = re.sub(r"[$(,)]", "", s)
    try:
        v = float(s)
    except ValueError:
        return 0.0
    return -v if negative else v


def load_csv(uploaded_file):
    """Read a NinjaTrader backtest CSV and return a cleaned DataFrame."""
    df = pd.read_csv(uploaded_file)
    # Drop fully-empty trailing column (NinjaTrader CSVs have a trailing comma)
    df = df.loc[:, ~df.columns.str.match(r"^Unnamed")]
    df.columns = df.columns.str.strip()

    df["PnL"] = df["Profit"].apply(parse_profit)
    df["ExitTime"] = pd.to_datetime(df["Exit time"], format="mixed", dayfirst=False)
    df["EntryTime"] = pd.to_datetime(df["Entry time"], format="mixed", dayfirst=False)
    return df


def compute_metrics(df, starting_capital=100_000):
    """Return a dict of key performance metrics from a trades DataFrame."""
    trades = df.sort_values("ExitTime").reset_index(drop=True)
    cum = trades["PnL"].cumsum()
    total_pnl = cum.iloc[-1] if len(cum) else 0.0

    # Drawdown series (dollar)
    peak = cum.cummax()
    dd = cum - peak
    max_dd = dd.min() if len(dd) else 0.0

    # Drawdown series (% of equity = capital + cumulative P&L)
    equity = starting_capital + cum
    equity_peak = equity.cummax()
    dd_pct = (equity - equity_peak) / equity_peak * 100
    max_dd_pct = dd_pct.min() if len(dd_pct) else 0.0

    # CAGR
    start = trades["ExitTime"].iloc[0]
    end = trades["ExitTime"].iloc[-1]
    years = max((end - start).days / 365.25, 1 / 365.25)
    cagr = ((starting_capital + total_pnl) / starting_capital) ** (1 / years) - 1

    # Win rate
    n_trades = len(trades)
    wins = (trades["PnL"] > 0).sum()
    win_rate = wins / n_trades if n_trades else 0

    # Profit factor
    gross_profit = trades.loc[trades["PnL"] > 0, "PnL"].sum()
    gross_loss = abs(trades.loc[trades["PnL"] < 0, "PnL"].sum())
    profit_factor = gross_profit / gross_loss if gross_loss else float("inf")

    # Win months
    monthly = trades.set_index("ExitTime")["PnL"].resample("ME").sum()
    win_months_pct = (monthly > 0).sum() / len(monthly) if len(monthly) else 0

    return {
        "total_pnl": total_pnl,
        "starting_capital": starting_capital,
        "cagr": cagr,
        "max_dd": max_dd,
        "max_dd_pct": max_dd_pct,
        "n_trades": n_trades,
        "wins": wins,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "win_months_pct": win_months_pct,
        "months_profitable": int((monthly > 0).sum()) if len(monthly) else 0,
        "total_months": len(monthly),
        "cum_series": cum,
        "dd_series": dd,
        "dd_pct_series": dd_pct,
        "exit_times": trades["ExitTime"],
    }


def monthly_returns_table(df, starting_capital):
    """Build a pivot DataFrame of monthly returns as % of starting capital."""
    trades = df.sort_values("ExitTime").copy()
    trades["Year"] = trades["ExitTime"].dt.year
    trades["Month"] = trades["ExitTime"].dt.month
    pivot = trades.groupby(["Year", "Month"])["PnL"].sum().unstack(fill_value=0)
    # Ensure all 12 months present
    for m in range(1, 13):
        if m not in pivot.columns:
            pivot[m] = 0.0
    pivot = pivot[sorted(pivot.columns)]
    pivot["YTD"] = pivot.sum(axis=1)
    # Convert to % of starting capital
    pivot_pct = pivot / starting_capital * 100
    return pivot, pivot_pct


def render_monthly_html(pivot_pct, pivot_dollar):
    """Convert monthly returns pivot to a styled HTML table with % and $ tooltip."""
    month_names = [calendar.month_abbr[m].upper() for m in range(1, 13)] + ["YTD"]
    header = "<tr><th>YEAR</th>" + "".join(f"<th>{m}</th>" for m in month_names) + "</tr>"
    rows = []
    for year in pivot_pct.index:
        pct_row = pivot_pct.loc[year]
        dlr_row = pivot_dollar.loc[year]
        cells = f'<td class="year-cell">{year}</td>'
        for pct_val, dlr_val in zip(pct_row, dlr_row):
            if pct_val > 0:
                cls = "pos"
            elif pct_val < 0:
                cls = "neg"
            else:
                cls = "zero"
            cells += f'<td class="{cls}" title="${dlr_val:,.0f}">{pct_val:+.1f}%</td>'
        rows.append(f"<tr>{cells}</tr>")
    return f'<table class="monthly-table">{header}{"".join(rows)}</table>'


def metric_card(label, value, color="", tooltip=""):
    cls = f" {color}" if color else ""
    if tooltip:
        return f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="tooltip-wrap">
                <div class="metric-value{cls}">{value}</div>
                <span class="tooltip-text">{tooltip}</span>
            </div>
        </div>"""
    return f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value{cls}">{value}</div>
    </div>"""


# ---------------------------------------------------------------------------
# App layout
# ---------------------------------------------------------------------------
st.markdown("## NinjaTrader Backtest Analyzer")

uploaded_files = st.file_uploader(
    "Upload NinjaTrader backtest CSV(s)",
    type=["csv"],
    accept_multiple_files=True,
)

if not uploaded_files:
    st.info("Upload one or more NinjaTrader backtest CSVs to get started.")
    st.stop()

# Parse all uploads and collect capital inputs
all_dfs = {}
capital_map = {}
for f in uploaded_files:
    df = load_csv(f)
    strat_name = df["Strategy"].iloc[0] if "Strategy" in df.columns else f.name.replace(".csv", "")
    label = f"{strat_name} ({f.name})"
    all_dfs[label] = df
    capital_map[label] = st.number_input(
        f"Initial Capital — {strat_name}",
        min_value=0,
        value=100_000,
        step=5_000,
        key=f"cap_{f.name}",
    )

# Sidebar — strategy selection
st.sidebar.header("Strategy Selection")
selected = st.sidebar.multiselect(
    "Include strategies:",
    options=list(all_dfs.keys()),
    default=list(all_dfs.keys()),
)

if not selected:
    st.warning("Select at least one strategy.")
    st.stop()

# Combine selected
combined = pd.concat([all_dfs[s] for s in selected], ignore_index=True)
combined = combined.sort_values("ExitTime").reset_index(drop=True)
total_capital = sum(capital_map[s] for s in selected)

# Start date filter
st.sidebar.header("Date Filter")
min_date = combined["ExitTime"].min().date()
max_date = combined["ExitTime"].max().date()
start_date = st.sidebar.date_input(
    "Performance start date",
    value=min_date,
    min_value=min_date,
    max_value=max_date,
)
combined = combined[combined["ExitTime"] >= pd.Timestamp(start_date)].reset_index(drop=True)

if combined.empty:
    st.warning("No trades after the selected start date.")
    st.stop()

# Chart options
st.sidebar.header("Chart Options")
show_individual = st.sidebar.checkbox("Show individual equity curves", value=False)

m = compute_metrics(combined, starting_capital=total_capital)

# Pre-compute individual strategy curves (date-filtered) for overlay
individual_curves = {}
if show_individual and len(selected) > 1:
    for s in selected:
        sdf = all_dfs[s].copy()
        sdf = sdf[sdf["ExitTime"] >= pd.Timestamp(start_date)].sort_values("ExitTime").reset_index(drop=True)
        if not sdf.empty:
            cap = capital_map[s]
            cum = sdf["PnL"].cumsum()
            individual_curves[s] = {
                "exit_times": sdf["ExitTime"],
                "cum_pct": cum / cap * 100,
                "cum_dollar": cum,
            }

# ---------------------------------------------------------------------------
# Metric cards row
# ---------------------------------------------------------------------------
cols = st.columns(6)
cards = [
    ("Annual Return (CAGR)", f"{m['cagr']:.1%}", "green" if m["cagr"] >= 0 else "red", ""),
    ("Max Drawdown", f"{m['max_dd_pct']:.1f}%", "red", f"${m['max_dd']:,.0f}"),
    ("Num Trades", f"{m['n_trades']:,}", "", ""),
    ("Win Rate", f"{m['win_rate']:.1%}", "green" if m["win_rate"] >= 0.5 else "red", ""),
    ("Win Months", f"{m['win_months_pct']:.0%}", "green" if m["win_months_pct"] >= 0.5 else "red", ""),
    ("Profit Factor", f"{m['profit_factor']:.2f}" if m["profit_factor"] != float("inf") else "∞", "green", ""),
]
for col, (label, value, color, tip) in zip(cols, cards):
    col.markdown(metric_card(label, value, color, tooltip=tip), unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Monthly Returns Table
# ---------------------------------------------------------------------------
st.markdown("#### Monthly Returns")
pivot_dollar, pivot_pct = monthly_returns_table(combined, total_capital)
st.markdown(render_monthly_html(pivot_pct, pivot_dollar), unsafe_allow_html=True)

st.markdown('<br><div style="text-align:center;color:#8a8aa3;font-size:0.82rem;font-weight:600;letter-spacing:0.5px;">HYPOTHETICAL PERFORMANCE</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Main content: Equity curve + Summary | Drawdown
# ---------------------------------------------------------------------------
chart_col, summary_col = st.columns([3, 1])

with chart_col:
    # Equity curve (% return with $ in hover)
    cum_pct = m["cum_series"] / total_capital * 100
    fig_eq = go.Figure()

    # Individual strategy curves (behind combined)
    palette = ["#42a5f5", "#ab47bc", "#ffa726", "#ef5350", "#26c6da", "#d4e157"]
    for i, (label, curve) in enumerate(individual_curves.items()):
        color = palette[i % len(palette)]
        short_name = label.split(" (")[0]
        fig_eq.add_trace(go.Scatter(
            x=curve["exit_times"],
            y=curve["cum_pct"],
            line=dict(color=color, width=1.5, dash="dot"),
            name=short_name,
            customdata=curve["cum_dollar"],
            hovertemplate=f"{short_name}<br>%{{y:.1f}}%<br>${{%{{customdata:,.0f}}}}<extra></extra>",
            opacity=0.7,
        ))

    fig_eq.add_trace(go.Scatter(
        x=m["exit_times"],
        y=cum_pct,
        fill="tozeroy",
        fillgradient=dict(
            type="vertical",
            colorscale=[[0, "rgba(0,200,83,0)"], [1, "rgba(0,200,83,0.35)"]],
        ),
        line=dict(color="#00c853", width=2),
        name="Combined",
        customdata=m["cum_series"],
        hovertemplate="Combined<br>%{y:.1f}%<br>$%{customdata:,.0f}<extra></extra>",
    ))
    fig_eq.update_layout(
        title="Equity Curve",
        template="plotly_dark",
        paper_bgcolor="#0e0e1a",
        plot_bgcolor="#0e0e1a",
        yaxis_title="Return (%)",
        xaxis_title="",
        height=370,
        margin=dict(l=60, r=20, t=45, b=30),
        yaxis=dict(ticksuffix="%", gridcolor="#1e1e2f"),
        xaxis=dict(gridcolor="#1e1e2f"),
        showlegend=bool(individual_curves),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
    )
    st.plotly_chart(fig_eq, use_container_width=True)

    # Drawdown chart (% with $ in hover)
    fig_dd = go.Figure()
    fig_dd.add_trace(go.Scatter(
        x=m["exit_times"],
        y=m["dd_pct_series"],
        fill="tozeroy",
        fillgradient=dict(
            type="vertical",
            colorscale=[[0, "rgba(255,82,82,0.35)"], [1, "rgba(255,82,82,0)"]],
        ),
        line=dict(color="#ff5252", width=1.5),
        name="Drawdown",
        customdata=m["dd_series"],
        hovertemplate="%{y:.1f}%<br>$%{customdata:,.0f}<extra></extra>",
    ))
    fig_dd.update_layout(
        title="Drawdown",
        template="plotly_dark",
        paper_bgcolor="#0e0e1a",
        plot_bgcolor="#0e0e1a",
        yaxis_title="Drawdown (%)",
        xaxis_title="",
        height=250,
        margin=dict(l=60, r=20, t=45, b=30),
        yaxis=dict(ticksuffix="%", gridcolor="#1e1e2f"),
        xaxis=dict(gridcolor="#1e1e2f"),
    )
    st.plotly_chart(fig_dd, use_container_width=True)

with summary_col:
    suggested_capital = total_capital + abs(m["max_dd"]) * 2
    total_return_pct = m["total_pnl"] / total_capital * 100
    summary_items = [
        ("Number of Trades", f"{m['n_trades']:,}"),
        ("Initial Capital", f"${total_capital:,.0f}"),
        ("Suggested Min Capital", f"${suggested_capital:,.0f}"),
        ("Win Rate", f"{m['win_rate']:.1%}"),
        ("Profitable Trades", f"{m['wins']:,}"),
        ("Months Profitable", f"{m['months_profitable']} / {m['total_months']}"),
        ("Total Net Profit", f"{total_return_pct:+.1f}% (${m['total_pnl']:,.0f})"),
        ("Max Drawdown", f"{m['max_dd_pct']:.1f}% (${m['max_dd']:,.0f})"),
        ("Profit Factor", f"{m['profit_factor']:.2f}" if m["profit_factor"] != float("inf") else "∞"),
    ]
    rows_html = "".join(
        f'<div class="summary-row"><span class="summary-key">{k}</span><span class="summary-val">{v}</span></div>'
        for k, v in summary_items
    )
    st.markdown(f'<div class="summary-card"><h4 style="color:#fff;margin:0 0 12px 0;">Summary Statistics</h4>{rows_html}</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Disclosures
# ---------------------------------------------------------------------------
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("""
<div style="background:#1a1a2e;border:1px solid #2d2d44;border-radius:10px;padding:20px 24px;font-size:0.78rem;color:#8a8aa3;line-height:1.6;">
<strong style="color:#ff5252;">PAST PERFORMANCE IS NOT INDICATIVE OF FUTURE RESULTS.</strong><br><br>

<strong style="color:#ccc;">HYPOTHETICAL PERFORMANCE DISCLAIMER</strong><br>
The results shown are based on simulated or hypothetical performance results that have certain inherent limitations.
Unlike the results shown in an actual performance record, these results do not represent actual trading.
Because these trades have not actually been executed, these results may have under- or over-compensated for the impact, if any, of certain market factors such as lack of liquidity.
Simulated or hypothetical trading programs in general are also subject to the fact that they are designed with the benefit of hindsight.
No representation is being made that any account will or is likely to achieve profits or losses similar to those shown.<br><br>

<strong style="color:#ccc;">ADDITIONAL RISK DISCLOSURE</strong><br>
Futures and forex trading contains substantial risk and is not for every investor. An investor could potentially lose all or more than the initial investment.
Risk capital is money that can be lost without jeopardizing ones financial security or lifestyle. Only risk capital should be used for trading and only those with sufficient risk capital should consider trading.
Commission and fees may vary from broker to broker. The performance results displayed herein do not necessarily account for all commissions, fees, or slippage that may be incurred in live trading.<br><br>

<strong style="color:#ccc;">BACKTEST LIMITATIONS</strong><br>
Backtested results are generated by the retroactive application of a trading strategy to historical data.
Results are hypothetical, were not achieved in real-time trading, and do not guarantee future performance.
Backtests do not account for all risks associated with live trading including, but not limited to, execution delays, slippage, market impact, and changes in market microstructure.
</div>
""", unsafe_allow_html=True)
