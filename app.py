"""우리 동네 범죄는 어떤 모양인가: 지역별 범죄 발생 통계를 '건수'가 아니라 '구성 비율'로 보는 Streamlit 앱.

GitHub 저장소에 이 파일, requirements.txt, crime.csv를 같은 폴더로 올리고
Community Cloud의 Main file path에 app.py(하위 폴더에 두었다면 그 경로)를 적습니다.
내 컴퓨터에서 실행: python -m streamlit run app.py

지역별 인구 같은 모수(분모)를 모르기 때문에 발생 건수를 지역끼리 직접 비교하지 않고,
'그 지역 범죄 중 각 유형이 차지하는 비율'을 전국 평균과 견줍니다.
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# app.py가 있는 폴더. 배포 서버의 작업 폴더와 다를 수 있어 파일은 이 폴더 기준으로 찾습니다.
HERE = Path(__file__).parent
BLUE, ORANGE = "#0072B2", "#D55E00"      # 내 지역 / 비교 대상(색맹 친화 조합)
SIDO_SHORT = {"경기도": "경기", "강원도": "강원", "세종시": "세종"}   # 시도 이름을 짧게 통일
MAIN_CATS = ["지능범죄", "기타범죄", "교통범죄", "폭력범죄", "절도범죄", "특별경제범죄", "풍속범죄", "강력범죄"]
DRILL_CATS = ["폭력범죄", "지능범죄", "강력범죄", "풍속범죄"]           # 중분류가 둘 이상인 대분류
SMALL_TOTAL = 1000                       # 이보다 건수가 적은 지역은 비율이 크게 흔들립니다

st.set_page_config(page_title="우리 동네 범죄 구성", layout="wide")


# 결과를 기억해 두어 위젯을 바꿔도 CSV를 다시 읽지 않습니다.
@st.cache_data
def load_data():
    """와이드 표(행=범죄 유형, 열=지역)를 세로 표로 바꾸고, 외국 발생분은 뺍니다."""
    raw = pd.read_csv(HERE / "crime.csv")
    raw = raw.drop(columns=[c for c in raw.columns if c.startswith("외국 ")])   # 국내 사례만 다룹니다
    long = raw.melt(id_vars=["범죄대분류", "범죄중분류"], var_name="지역", value_name="건수")
    long = long.rename(columns={"범죄대분류": "대분류", "범죄중분류": "중분류"})
    parts = long["지역"].str.split(" ", n=1, expand=True)
    long["시도"] = parts[0].replace(SIDO_SHORT)
    long["시군구"] = parts[1].fillna(long["시도"])            # '세종시'처럼 시군구가 없으면 시도 이름
    long["지역"] = long["시도"].where(long["시군구"] == long["시도"], long["시도"] + " " + long["시군구"])
    return long


st.title("우리 동네 범죄는 어떤 모양인가: 건수 말고 '구성'으로 보면?")
st.caption("출처: 경찰청 범죄 발생 지역별 통계(파일 기준일 2025-12-31) · 단위: 건, 비율은 %")
st.info("지역별 인구 같은 모수를 알 수 없어 건수를 지역끼리 비교하지 않습니다. "
        "대신 **그 지역에서 일어난 범죄 중 각 유형이 차지하는 비율**을 전국 평균과 견줍니다. "
        "국내 시군구만 다루며 외국 발생분은 제외했습니다. 경기·경남 등의 일부 시는 구를 합산한 값입니다.")

try:
    long = load_data()
except FileNotFoundError:
    st.error("app.py와 같은 폴더에 crime.csv를 올려 주세요.")
    st.stop()

# 지역 표(시도·시군구)와 지역×대분류 표를 만듭니다.
meta = long[["지역", "시도", "시군구"]].drop_duplicates().reset_index(drop=True)
by_cat = long.pivot_table(index="지역", columns="대분류", values="건수", aggfunc="sum")
cat_order = by_cat.sum().sort_values(ascending=False).index.tolist()      # 전국에서 많은 유형 순
by_cat = by_cat[cat_order]
total = by_cat.sum(axis=1)                                   # 지역별 총 발생 건수
share = by_cat.div(total, axis=0) * 100                      # 지역 안에서 각 유형의 비율(%)
nat_share = by_cat.sum() / by_cat.sum().sum() * 100          # 전국(국내) 비율(%)
ratio = share.div(nat_share)                                 # 전국 대비 배율(1.0 = 전국 평균과 같음)


def pick_region(title, default_sido, default_gu):
    """시도를 고르면 그 시도의 시군구만 고를 수 있게 합니다. 고른 지역 이름을 돌려줍니다."""
    sidos = list(dict.fromkeys(meta["시도"]))
    sido = st.sidebar.selectbox(f"{title} · 시도", sidos, index=sidos.index(default_sido))
    gus = meta.loc[meta["시도"] == sido, "시군구"].tolist()
    gu = st.sidebar.selectbox(f"{title} · 시군구", gus, index=gus.index(default_gu) if default_gu in gus else 0)
    return meta.loc[(meta["시도"] == sido) & (meta["시군구"] == gu), "지역"].iloc[0]


st.sidebar.header("조회 조건")
region_a = pick_region("내 지역", "서울", "강남구")
mode = st.sidebar.radio("비교 대상", ["전국 평균", "다른 지역"])
region_b = pick_region("비교 지역", "서울", "중구") if mode == "다른 지역" else None
cats = st.sidebar.multiselect("표시할 범죄 대분류", cat_order, default=[c for c in MAIN_CATS if c in cat_order])

if not cats:
    st.warning("범죄 대분류를 하나 이상 선택하세요.")
    st.stop()
if region_b == region_a:
    st.warning("내 지역과 같은 지역입니다. 비교 지역을 바꿔 주세요.")
    st.stop()
if total[region_a] == 0 or (region_b and total[region_b] == 0):
    st.warning("선택한 지역에 집계된 건수가 없습니다.")
    st.stop()

# 비교 대상(전국 평균 또는 다른 지역)의 이름과 비율을 정합니다.
other_name = region_b or "전국 평균"
other_share = share.loc[region_b] if region_b else nat_share
cmap = {region_a: BLUE, other_name: ORANGE}
sido_a = meta.loc[meta["지역"] == region_a, "시도"].iloc[0]

# ── 요약 카드 ──────────────────────────────────────────────
st.subheader(f"{region_a}의 범죄 구성" + (f" vs {region_b}" if region_b else " vs 전국 평균"))
if total[region_a] < SMALL_TOTAL:
    st.warning(f"{region_a}은(는) 총 {int(total[region_a]):,}건으로 적은 편이라 비율이 조금만 달라져도 크게 흔들립니다.")
top_cat = share.loc[region_a].idxmax()
hi_cat = ratio.loc[region_a, cats].idxmax()
c1, c2, c3 = st.columns(3)
c1.metric(f"{region_a} 총 발생 건수", f"{int(total[region_a]):,} 건")
c2.metric("가장 큰 비중의 유형", f"{top_cat} {share.loc[region_a, top_cat]:.1f}%")
c3.metric("전국 대비 가장 두드러진 유형", f"{hi_cat} {ratio.loc[region_a, hi_cat]:.1f}배")
st.caption("비율은 그 지역 전체 범죄 건수 중 해당 유형이 차지하는 몫입니다. 배율은 지역 비율 ÷ 전국 비율이며, 1.0이면 전국 평균과 같습니다.")

targets = [(region_a, share.loc[region_a], by_cat.loc[region_a]),
           (other_name, other_share, by_cat.loc[region_b] if region_b else by_cat.sum())]

# ── 차트 1·2: 구성 비율, 전국 대비 배율 ───────────────────────
rows = [{"대상": name, "대분류": c, "비율(%)": s[c], "건수": n[c]} for name, s, n in targets for c in cats]
comp = pd.DataFrame(rows)
fig_share = px.bar(comp, x="비율(%)", y="대분류", color="대상", orientation="h", barmode="group",
                   color_discrete_map=cmap, category_orders={"대분류": cats},
                   hover_data={"건수": ":,.0f", "비율(%)": ":.1f"})
fig_share.update_yaxes(title=None)    # category_orders를 주면 px가 가로 막대 순서를 이미 위에서부터 맞춥니다
fig_share.update_layout(legend=dict(title_text="", orientation="h", yanchor="bottom", y=1.02, x=0),
                        margin=dict(t=40, b=10))

ratio_rows = [{"대상": name, "대분류": c, "배율": ratio.loc[name, c]}
              for name in [region_a] + ([region_b] if region_b else []) for c in cats]
fig_ratio = px.bar(pd.DataFrame(ratio_rows), x="대분류", y="배율", color="대상", barmode="group",
                   color_discrete_map=cmap, category_orders={"대분류": cats}, text_auto=".1f")
fig_ratio.add_hline(y=1, line_dash="dash", line_color="gray")
fig_ratio.update_xaxes(title=None, tickangle=-30)
fig_ratio.update_yaxes(title="전국 대비 배율 (점선 = 전국 평균 1.0)", rangemode="tozero")
fig_ratio.update_layout(legend=dict(title_text="", orientation="h", yanchor="bottom", y=1.02, x=0),
                        margin=dict(t=40, b=10))

left, right = st.columns(2)
with left:
    st.markdown("**범죄 유형별 비율 (%)**")
    st.plotly_chart(fig_share, width="stretch")
with right:
    st.markdown("**전국 평균의 몇 배인가**")
    st.plotly_chart(fig_ratio, width="stretch")

# ── 차트 3: 대분류 안의 중분류 ────────────────────────────────
st.divider()
left, right = st.columns(2)
with left:
    drill = st.selectbox("자세히 볼 범죄 대분류", DRILL_CATS)
    st.markdown(f"**{drill} 안에서는 무엇이 많은가 (%)**")
    sub_names = long.loc[long["대분류"] == drill, "중분류"].drop_duplicates().tolist()
    sub_rows, empty_names = [], []
    for name, region in [(region_a, region_a), (other_name, region_b)]:
        d = long[long["대분류"] == drill]
        d = d[d["지역"] == region] if region else d
        counts = d.groupby("중분류")["건수"].sum().reindex(sub_names)
        if counts.sum() == 0:
            empty_names.append(name)
            continue
        sub_rows += [{"대상": name, "중분류": s, "비율(%)": counts[s] / counts.sum() * 100, "건수": counts[s]}
                     for s in sub_names]
    if sub_rows:
        fig_sub = px.bar(pd.DataFrame(sub_rows), x="비율(%)", y="중분류", color="대상", orientation="h",
                         barmode="group", color_discrete_map=cmap, category_orders={"중분류": sub_names},
                         hover_data={"건수": ":,.0f", "비율(%)": ":.1f"})
        fig_sub.update_yaxes(title=None)
        fig_sub.update_layout(legend=dict(title_text="", orientation="h", yanchor="bottom", y=1.02, x=0),
                              margin=dict(t=40, b=10))
        st.plotly_chart(fig_sub, width="stretch")
    if empty_names:
        st.caption(f"{', '.join(empty_names)}: {drill} 사건이 0건이라 비율을 계산할 수 없습니다.")

# ── 순위: 어떤 유형의 비율이 높은 지역인가 ─────────────────────
with right:
    rank_cat = st.selectbox("비율 순위를 볼 범죄 대분류", cat_order, index=cat_order.index("절도범죄"))
    min_n = st.slider("총 발생 건수가 이 값 이상인 지역만", 500, 10000, 2000, step=500)
    st.markdown(f"**{rank_cat} 비율이 높은 지역 TOP 10**")
    eligible = total[total >= min_n].index
    if len(eligible) == 0:
        st.warning("조건에 맞는 지역이 없습니다. 기준 건수를 낮춰 보세요.")
    else:
        top = share.loc[eligible, rank_cat].nlargest(10).rename("비율(%)").reset_index()
        top["총 건수"] = total[top["지역"]].values
        fig_rank = px.bar(top, x="비율(%)", y="지역", orientation="h", hover_data={"총 건수": ":,.0f"},
                          color_discrete_sequence=[BLUE])
        fig_rank.add_vline(x=nat_share[rank_cat], line_dash="dash", line_color="gray")
        fig_rank.update_xaxes(title=f"비율(%) · 점선 = 전국 평균 {nat_share[rank_cat]:.1f}%")
        fig_rank.update_yaxes(autorange="reversed", title=None)
        fig_rank.update_layout(margin=dict(t=40, b=10))
        st.plotly_chart(fig_rank, width="stretch")
        st.caption("건수가 적은 지역은 비율이 쉽게 흔들려, 기준 건수 미만인 지역은 순위에서 뺍니다.")

# ── 히트맵: 같은 시도 안의 시군구 비교 ─────────────────────────
st.divider()
st.subheader(f"{sido_a} 시군구별 전국 대비 배율")
in_sido = meta.loc[meta["시도"] == sido_a, "지역"]
in_sido = total[in_sido].sort_values(ascending=False).index                    # 건수 많은 지역이 위
labels = meta.set_index("지역").loc[in_sido, "시군구"].tolist()
z = ratio.loc[in_sido, cats]
heat = go.Figure(go.Heatmap(
    z=z.values, x=cats, y=labels, zmin=0, zmax=2, zmid=1,
    colorscale=[[0, BLUE], [0.5, "#F7F7F7"], [1, ORANGE]],
    texttemplate="%{z:.1f}",
    customdata=by_cat.loc[in_sido, cats].values,
    hovertemplate="%{y} · %{x}<br>전국 대비 %{z:.2f}배<br>%{customdata:,}건<extra></extra>",
    colorbar=dict(title="배율")))
heat.update_yaxes(autorange="reversed")
heat.update_layout(height=140 + 30 * len(labels), margin=dict(t=10, b=10))
st.plotly_chart(heat, width="stretch")
st.caption("주황은 전국보다 그 유형의 비율이 높고, 파랑은 낮다는 뜻입니다(색은 0~2배까지 표시, 숫자는 실제 배율). "
           "총 건수가 적은 시군구는 배율이 크게 흔들릴 수 있습니다.")

# ── 표와 내려받기 ──────────────────────────────────────────
st.subheader("현재 선택한 지역의 범죄 유형별 수치")
table = pd.DataFrame([{"대상": name, "대분류": c, "건수": int(n[c]), "비율(%)": round(s[c], 1),
                       "전국 비율(%)": round(nat_share[c], 1),
                       "전국 대비 배율": round(s[c] / nat_share[c], 2)}
                      for name, s, n in targets for c in cat_order])
st.dataframe(table, hide_index=True, width="stretch")
st.download_button("현재 선택 CSV 저장", data=table.to_csv(index=False).encode("utf-8-sig"),
                   file_name="crime_profile.csv", mime="text/csv")
st.caption("이 자료만으로 지역의 안전 정도를 비교하거나 범죄 원인을 단정하지 않습니다. "
           "비율이 높다는 것은 그 지역 범죄 중 해당 유형의 몫이 크다는 뜻이며, 건수가 많거나 위험하다는 뜻이 아닙니다.")
