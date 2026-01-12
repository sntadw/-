import streamlit as st
import akshare as ak
import pandas as pd
from datetime import datetime
import time
import requests

st.set_page_config(page_title="A股涨停监控+潜在候选", layout="wide")
st.title("🇨🇳 A股涨停板监控 & 当天潜在涨停检测（资金分析版） - 在线版（支持2秒刷新+筛选）")

# 侧边栏设置
st.sidebar.header("通用设置")
auto_refresh = st.sidebar.checkbox("自动刷新（交易时段推荐）", value=True)
refresh_interval = st.sidebar.slider("刷新间隔（秒，建议10+防限流/卡顿，2秒可试）", 2, 120, 10)  # 支持2秒

st.sidebar.header("潜在涨停筛选条件（可调）")
min_rise = st.sidebar.slider("最低涨幅 (%)", 0.0, 9.9, 4.0)
max_rise = st.sidebar.slider("最高涨幅 (%) 未涨停", 0.0, 9.9, 9.5)
min_main_inflow = st.sidebar.number_input("最低主力净流入-净额 (万)", 0, 50000, 3000) * 10000
min_turnover = st.sidebar.slider("最低换手率 (%)", 0.0, 50.0, 5.0)
max_market_cap = st.sidebar.number_input("最高流通市值 (亿)", 10, 1000, 150) * 100000000

# 新增：全局搜索筛选（适用于涨停板和潜在候选）
st.sidebar.header("实时筛选搜索")
search_keyword = st.sidebar.text_input("搜索代码/名称/行业（模糊匹配，支持多个关键词空格分隔）", "")

server_chan_key = st.sidebar.text_input("Server酱Key（微信推送新涨停/候选，可留空）", type="password")
st.sidebar.caption("Server酱申请: https://sct.ftqq.com/")

# 存储状态
if 'last_potential_codes' not in st.session_state:
    st.session_state.last_potential_codes = set()
if 'last_zt_codes' not in st.session_state:
    st.session_state.last_zt_codes = set()

today = datetime.now().strftime("%Y%m%d")
placeholder = st.empty()

def send_weixin(msg):
    if server_chan_key:
        url = f"https://sctapi.ftqq.com/{server_chan_key}.send"
        try:
            requests.post(url, data={'title': '涨停警报!', 'desp': msg})
        except:
            pass

# 筛选函数（支持代码、名称、行业多关键词模糊搜索）
def filter_df(df, keyword):
    if not keyword.strip():
        return df
    keywords = keyword.lower().split()
    mask = pd.Series([True] * len(df))
    for kw in keywords:
        mask &= (
            df['代码'].astype(str).str.contains(kw, case=False) |
            df['名称'].str.contains(kw, case=False) |
            df.get('所属行业', pd.Series(['']*len(df))).str.contains(kw, case=False)
        )
    return df[mask]

while True:
    with placeholder.container():
        st.subheader(f"更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (北京时间)")

        col1, col2 = st.columns(2)

        with col1:
            st.header("📈 今日涨停板（实时）")
            try:
                zt_df = ak.stock_zt_pool_em(date=today)
                if not zt_df.empty:
                    zt_df = zt_df.sort_values(by='涨停时间', ascending=True) if '涨停时间' in zt_df.columns else zt_df
                    # 应用筛选
                    zt_df_filtered = filter_df(zt_df, search_keyword)
                    st.dataframe(zt_df_filtered[['代码', '名称', '最新价', '涨停价', '涨停时间', '换手率', '连板数', '所属行业']], use_container_width=True)

                    current_zt_codes = set(zt_df['代码'])
                    new_zt = current_zt_codes - st.session_state.last_zt_codes
                    if new_zt:
                        new_zt_stocks = zt_df[zt_df['代码'].isin(new_zt)]
                        st.success(f"⚡ 新涨停 {len(new_zt)} 个！")
                        st.dataframe(new_zt_stocks[['代码', '名称', '涨停时间', '连板数', '所属行业']])
                        send_weixin(f"新涨停 {len(new_zt)} 个:\n{new_zt_stocks.to_string()}")
                    st.session_state.last_zt_codes = current_zt_codes
                else:
                    st.info("暂无涨停（非交易日或开盘前）")
            except Exception as e:
                st.error(f"涨停数据错误: {e}")

        with col2:
            st.header("⚡ 潜在涨停候选（主力资金实时筛选）")
            try:
                spot_df = ak.stock_zh_a_spot_em()
                potential_df = spot_df[
                    (spot_df['涨跌幅'] >= min_rise) &
                    (spot_df['涨跌幅'] <= max_rise) &
                    (spot_df['主力净流入-净额'] >= min_main_inflow) &
                    (spot_df['换手率'] >= min_turnover) &
                    (spot_df['流通市值'] <= max_market_cap)
                ].copy()

                if not potential_df.empty:
                    potential_df = potential_df.sort_values(by='主力净流入-净额', ascending=False)
                    # 应用筛选
                    potential_df_filtered = filter_df(potential_df, search_keyword)
                    display_cols = ['代码', '名称', '最新价', '涨跌幅', '换手率', '主力净流入-净额', '流通市值', '所属行业']
                    st.dataframe(potential_df_filtered[display_cols].head(50), use_container_width=True)  # 前50条，支持滚动

                    current_codes = set(potential_df['代码'])
                    new_codes = current_codes - st.session_state.last_potential_codes
                    if new_codes:
                        new_stocks = potential_df[potential_df['代码'].isin(new_codes)]
                        st.success(f"🔔 新潜在候选 {len(new_codes)} 个！")
                        st.dataframe(filter_df(new_stocks, search_keyword)[display_cols].head(20))
                        send_weixin(f"新潜在候选 {len(new_codes)} 个:\n{new_stocks.to_string()}")
                    st.session_state.last_potential_codes = current_codes
                else:
                    st.info("当前无满足条件候选（可调整阈值）")
            except Exception as e:
                st.error(f"实时数据错误: {e}")

        st.caption("⚠️ 2秒刷新在交易高峰可能卡顿或限流，建议10-30秒。仅供参考，非投资建议！")

    if not auto_refresh:
        st.stop()
    time.sleep(refresh_interval)
    st.rerun()
