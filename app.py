import streamlit as st
import pandas as pd
import plotly.express as px
import re
from datetime import datetime

# ----------------------------------------------------
# 1. 페이지 테마 및 레이아웃 설정
# ----------------------------------------------------
st.set_page_config(
    page_title="조정부 운동인증 챌린지",
    page_icon="🚣",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------------------------------------------
# 2. 구글 스프레드시트 연동 (웹에 게시된 CSV 링크)
# ----------------------------------------------------
CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQKSCkdKmmNi07nmmO5RN6vDmt_dobOqdCpluVAoP-91dyu36nyuMjuXJXMXrzQDquOq9seEpHtN5_6/pub?gid=995447885&single=true&output=csv"

def parse_time_to_seconds(time_str):
    if pd.isna(time_str): return None
    try:
        parts = str(time_str).strip().split(':')
        if len(parts) == 2: return int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 1: return float(parts[0])
    except:
        return None
    return None

def format_seconds_to_pace(seconds):
    if pd.isna(seconds) or seconds is None or seconds <= 0: return "-"
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m:02d}:{s:04.1f}"

def extract_drive_image_urls(raw_text):
    if pd.isna(raw_text): return []
    urls = [u.strip() for u in str(raw_text).split(',') if u.strip()]
    direct_urls = []
    for url in urls:
        match_id = re.search(r'id=([a-zA-Z0-9_-]+)', url)
        match_d = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
        
        file_id = None
        if match_id: file_id = match_id.group(1)
        elif match_d: file_id = match_d.group(1)
            
        if file_id:
            direct_urls.append(f"https://lh3.googleusercontent.com/d/{file_id}")
    return direct_urls

# ----------------------------------------------------
# 데이터 로딩 및 전처리
# ----------------------------------------------------
@st.cache_data(ttl=30)
def load_data():
    raw_df = pd.read_csv(CSV_URL)
    
    expected_cols = ["날짜", "이름", "총거리", "운동종류", "사진링크", "구분", "메모"]
    actual_col_count = len(raw_df.columns)
    
    rename_dict = {}
    for i in range(min(actual_col_count, len(expected_cols))):
        rename_dict[raw_df.columns[i]] = expected_cols[i]
        
    df = raw_df.rename(columns=rename_dict)
    
    def parse_korean_date(val):
        if pd.isna(val): return pd.NaT
        s = str(val).strip().replace("오후", "PM").replace("오전", "AM")
        return pd.to_datetime(s, errors='coerce')

    df['날짜'] = df['날짜'].apply(parse_korean_date)
    df = df.dropna(subset=['날짜', '이름'])
    
    if '총거리' in df.columns:
        df['총거리'] = pd.to_numeric(df['총거리'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    else:
        df['총거리'] = 0
        
    df['평균페이스'] = "-"
    df['페이스(초)'] = None
    df['운동시간(분)'] = None
    
    if '사진링크' not in df.columns: df['사진링크'] = ""
    if '구분' not in df.columns: df['구분'] = "기존"
    if '운동종류' not in df.columns: df['운동종류'] = "운동"
    if '메모' not in df.columns: df['메모'] = ""
        
    return df

try:
    df = load_data()
except Exception as e:
    st.error(f"데이터 로딩 중 오류가 발생했습니다: {e}")
    st.stop()

# ----------------------------------------------------
# 3. 사이드바 컨트롤러 (필터 시스템)
# ----------------------------------------------------
st.sidebar.title("🎛️ 필터 및 기간 설정")

if st.sidebar.button("🔄 데이터 즉시 새로고침"):
    st.cache_data.clear()
    st.rerun()

target_meters = st.sidebar.number_input(
    "누적 챌린지 목표 거리 (m)",
    value=50000,
    step=5000
)

st.sidebar.subheader("👥 부원 그룹 선택")
group_options = ["전체", "기존", "신입"]
# 공지에 따라 기본값을 '기존'으로 설정해두면 편리합니다.
selected_group = st.sidebar.radio("조회할 그룹을 선택하세요", group_options, index=1) 

if not df.empty:
    min_date = df['날짜'].min().date()
    max_date = df['날짜'].max().date()
else:
    min_date = datetime.today().date()
    max_date = datetime.today().date()

st.sidebar.subheader("📅 날짜 설정")
date_range = st.sidebar.date_input(
    "조회 기간",
    value=[min_date, max_date]
)

if len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date = date_range[0]
    end_date = date_range[0]

member_options = ["전체 부원"] + sorted(list(df['이름'].unique()))
selected_member = st.sidebar.selectbox("부원 개별 조회 (선택)", member_options)

# 데이터 필터링 연동
mask = (df['날짜'].dt.date >= start_date) & (df['날짜'].dt.date <= end_date)

if selected_group != "전체":
    mask &= (df['구분'] == selected_group)

if selected_member != "전체 부원":
    mask &= (df['이름'] == selected_member)

filtered_df = df[mask]

# ----------------------------------------------------
# 4. 상단 KPI 대시보드 지표
# ----------------------------------------------------
st.title("🚣 조정부 운동인증 챌린지")
st.caption(f"🗓️ 조회 기간: **{start_date} ~ {end_date}** ｜ 👥 조회 그룹: **{selected_group}**")

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("인증된 훈련 횟수", f"{len(filtered_df):,}회")
kpi2.metric("총 누적 거리", f"{filtered_df['총거리'].sum():,.0f}m")

avg_dist = filtered_df['총거리'].mean() if len(filtered_df) > 0 else 0
kpi3.metric("1회 평균 거리", f"{avg_dist:,.0f}m")
kpi4.metric("참여 인원", f"{filtered_df['이름'].nunique()}명")

st.divider()

# ----------------------------------------------------
# 5. [핵심] 🎟️ 개인별 추첨권 획득 현황판
# ----------------------------------------------------
st.subheader(f"🎟️ 개인별 추첨권 획득 현황 ({selected_group})")
st.info("💡 **추첨권 규칙**: 운동 1회 인증 당 **1장** 획득 | 누적 50,000m 달성 시 **보너스 3장** 추가 지급 🎁")

if not filtered_df.empty:
    # 개인별 인증 횟수(행 개수)와 총 거리 계산
    ticket_df = filtered_df.groupby(['이름', '구분']).agg(
        참여횟수=('날짜', 'count'),
        총거리=('총거리', 'sum')
    ).reset_index()

    # 추첨권 로직 적용
    ticket_df['기본추첨권'] = ticket_df['참여횟수']
    ticket_df['보너스추첨권'] = ticket_df['총거리'].apply(lambda x: 3 if x >= target_meters else 0)
    ticket_df['총추첨권'] = ticket_df['기본추첨권'] + ticket_df['보너스추첨권']
    
    # 총 추첨권이 많은 순, 거리가 많은 순으로 정렬
    ticket_df = ticket_df.sort_values(by=['총추첨권', '총거리'], ascending=[False, False]).reset_index(drop=True)

    # 🏆 상위 3명 추첨권 포디움 하이라이트
    top_n = min(len(ticket_df), 3)
    cols = st.columns(top_n)
    for i in range(top_n):
        row = ticket_df.iloc[i]
        cols[i].metric(
            label=f"🏆 {i+1}위: {row['이름']} ({row['구분']})",
            value=f"🎟️ {row['총추첨권']} 장",
            delta=f"누적 {row['총거리']:,.0f}m 달성"
        )

    # 전체 추첨권 현황 데이터프레임 (깔끔한 표 형태)
    st.dataframe(
        ticket_df[['이름', '구분', '총추첨권', '기본추첨권', '보너스추첨권', '총거리']],
        column_config={
            "이름": "부원 이름",
            "구분": "분류",
            "총추첨권": st.column_config.NumberColumn("🎟️ 총 추첨권", help="기본과 보너스의 합계입니다."),
            "기본추첨권": st.column_config.NumberColumn("✅ 기본 (인증횟수)", help="운동 1회당 1장"),
            "보너스추첨권": st.column_config.NumberColumn("🎁 보너스 (5만m)", help="50,000m 달성 시 3장"),
            "총거리": st.column_config.NumberColumn("🏃 누적 거리 (m)", format="%d m")
        },
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    # ----------------------------------------------------
    # 6. 🎯 50,000m 누적 챌린지 프로그레스 바
    # ----------------------------------------------------
    st.subheader(f"🎯 {target_meters:,}m 보너스 달성률 현황")
    
    with st.expander("📊 50,000m 달성 진행도 및 남은 거리 보기", expanded=True):
        for _, row in ticket_df.iterrows():
            p_col1, p_col2 = st.columns([1, 4])
            달성률_퍼센트 = min(float(row['총거리'] / target_meters), 1.0)
            상태 = "🎁 보너스 3장 획득!" if row['총거리'] >= target_meters else "🚣 진행 중"
            남은거리 = max(0, target_meters - row['총거리'])

            with p_col1:
                st.write(f"**{row['이름']}**")
                st.caption(f"{상태} | 남은거리: {남은거리:,.0f}m")
            with p_col2:
                st.progress(달성률_퍼센트)
                
else:
    st.info(f"해당 기간에 기록을 등록한 {selected_group} 부원이 없습니다.")

st.divider()

# ----------------------------------------------------
# 7. 기량 분석 차트
# ----------------------------------------------------
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.subheader("⚡ 500m 스플릿 페이스 변화 (위로 갈수록 빠름)")
    pace_df = filtered_df.dropna(subset=['페이스(초)']).sort_values('날짜')
    if not pace_df.empty:
        fig_pace = px.line(
            pace_df, x='날짜', y='페이스(초)', color='이름', markers=True,
            hover_data={'날짜': '|%Y-%m-%d', '평균페이스': True, '총거리': True, '페이스(초)': False}
        )
        fig_pace.update_yaxes(autorange="reversed", title="500m Split (초 단위)")
        fig_pace.update_layout(template="plotly_white", legend_title_text="부원 이름")
        st.plotly_chart(fig_pace, use_container_width=True)
    else:
        st.info("현재 입력된 데이터에 페이스 기록이 없습니다.")

with chart_col2:
    st.subheader("📈 일자별 누적 거리 증가 곡선")
    race_df = filtered_df.sort_values('날짜').copy()
    if not race_df.empty:
        race_df['누적거리'] = race_df.groupby('이름')['총거리'].cumsum()
        fig_race = px.line(
            race_df, x='날짜', y='누적거리', color='이름', markers=True
        )
        fig_race.add_hline(y=target_meters, line_dash="dash", line_color="red", annotation_text="보너스 기준선")
        fig_race.update_layout(template="plotly_white", legend_title_text="부원 이름")
        st.plotly_chart(fig_race, use_container_width=True)
    else:
        st.info("표시할 거리 데이터가 없습니다.")

st.divider()

# ----------------------------------------------------
# 8. 폴더형 메모리 인증 사진 아카이브
# ----------------------------------------------------
st.subheader("📷 운동 인증 기록실")

photo_records = filtered_df[filtered_df['사진링크'].astype(str).str.contains("http", na=False)].sort_values('날짜', ascending=False)

if photo_records.empty:
    st.caption("선택된 기간에 등록된 인증 사진이 없습니다.")
else:
    for _, row in photo_records.iterrows():
        title_str = f"[{row['날짜'].strftime('%Y-%m-%d')}] {row['이름']} - {row.get('운동종류', '운동')} | {row['총거리']:,.0f}m"
        with st.expander(title_str, expanded=False):
            st.write(f"**메모 / 세부사항**: {row['메모'] if str(row['메모']) != 'nan' and row['메모'] else '기록 없음'}")
            
            img_urls = extract_drive_image_urls(row['사진링크'])
            if img_urls:
                img_cols = st.columns(min(len(img_urls), 4))
                for idx, img_url in enumerate(img_urls):
                    with img_cols[idx % 4]:
                        st.image(img_url, caption=f"메모리 {idx+1}", use_container_width=True)
            else:
                st.caption("사진 링크를 가져올 수 없습니다. 드라이브 폴더 권한을 확인해주세요.")
