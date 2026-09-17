import streamlit as st
import pandas as pd
import plotly.express as px
import re
from datetime import datetime

# 1. 페이지 테마 및 레이아웃 설정
st.set_page_config(
    page_title="조정부 Rowing Data Lab",
    page_icon="🚣",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. 구글 스프레드시트 연동
SHEET_ID = "1TE_KyMv0jZg7KBY34UIkKSaCu7arUVDO1w8RY09n4Xc"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=995447885"

# 시간 문자열(MM:SS 또는 MM:SS.S)을 초(sec)로 변환하는 함수
def parse_time_to_seconds(time_str):
    if pd.isna(time_str):
        return None
    try:
        parts = str(time_str).strip().split(':')
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 1:
            return float(parts[0])
    except:
        return None
    return None

# 초(sec) 단위를 MM:SS.S 페이스 표기로 역변환하는 함수
def format_seconds_to_pace(seconds):
    if pd.isna(seconds) or seconds is None or seconds <= 0:
        return "-"
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m:02d}:{s:04.1f}"

# 구글 드라이브 뷰 링크를 Streamlit 이미지 로딩용 직접 URL로 변환하는 함수
def extract_drive_image_urls(raw_text):
    if pd.isna(raw_text):
        return []
    urls = [u.strip() for u in str(raw_text).split(',') if u.strip()]
    direct_urls = []
    for url in urls:
        # id= 추출
        match_id = re.search(r'id=([a-zA-Z0-9_-]+)', url)
        # /d/ID/ 추출
        match_d = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
        
        file_id = None
        if match_id:
            file_id = match_id.group(1)
        elif match_d:
            file_id = match_d.group(1)
            
        if file_id:
            direct_urls.append(f"https://lh3.googleusercontent.com/d/{file_id}")
    return direct_urls

@st.cache_data(ttl=30)  # 30초마다 데이터 자동 새로고침
def load_data():
    raw_df = pd.read_csv(CSV_URL)
    
    # 구글 폼 열 이름 자동 매핑 (타임스탬프 포함)
    col_map = {}
    for col in raw_df.columns:
        c = col.replace(" ", "")
        if "날짜" in c or "타임스탬프" in c: col_map[col] = "날짜"
        elif "이름" in c: col_map[col] = "이름"
        elif "구분" in c: col_map[col] = "구분"
        elif "운동종류" in c: col_map[col] = "운동종류"
        elif "거리" in c: col_map[col] = "총거리"
        elif "시간" in c: col_map[col] = "소요시간"
        elif "페이스" in c: col_map[col] = "평균페이스"
        elif "SPM" in c or "레이트" in c: col_map[col] = "SPM"
        elif "드래그" in c: col_map[col] = "드래그팩터"
        elif "사진" in c: col_map[col] = "사진링크"
        elif "메모" in c or "특이사항" in c: col_map[col] = "메모"
        
    df = raw_df.rename(columns=col_map)
    
    # 한국어 타임스탬프(오후/오전) 파싱 지원
    def parse_korean_date(val):
        if pd.isna(val):
            return pd.NaT
        s = str(val).strip().replace("오후", "PM").replace("오전", "AM")
        return pd.to_datetime(s, errors='coerce')

    df['날짜'] = df['날짜'].apply(parse_korean_date)
    df = df.dropna(subset=['날짜', '이름'])
    
    df['총거리'] = pd.to_numeric(df['총거리'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    
    if '평균페이스' in df.columns:
        df['페이스(초)'] = df['평균페이스'].apply(parse_time_to_seconds)
    else:
        df['평균페이스'] = "-"
        df['페이스(초)'] = None

    if '소요시간' in df.columns:
        df['운동시간(분)'] = df['소요시간'].apply(parse_time_to_seconds).apply(lambda x: x / 60 if x else None)
    else:
        df['운동시간(분)'] = None
    
    if '사진링크' not in df.columns:
        df['사진링크'] = ""
    if '메모' not in df.columns:
        df['메모'] = ""
    if '구분' not in df.columns:
        df['구분'] = "기존"
        
    return df

# 데이터 로딩
try:
    df = load_data()
except Exception as e:
    st.error("스프레드시트 데이터를 읽어오는 중 오류가 발생했습니다. 구글 시트 공유 권한을 확인해주세요.")
    st.stop()

# ----------------------------------------------------
# 3. 사이드바 컨트롤러 (필터 시스템)
# ----------------------------------------------------
st.sidebar.title("🎛️ 필터 및 기간 설정")

# 1) 기간 설정 (자유로운 날짜 범위 지정)
if not df.empty:
    min_date = df['날짜'].min().date()
    max_date = df['날짜'].max().date()
else:
    min_date = datetime.today().date()
    max_date = datetime.today().date()

date_range = st.sidebar.date_input(
    "조회 기간",
    value=[min_date, max_date],
    min_value=min_date,
    max_value=max_date
)

# 시작일과 종료일 안전 추출
if len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date = date_range[0]
    end_date = date_range[0]

# 2) 챌린지 목표 거리 입력
target_meters = st.sidebar.number_input(
    "누적 챌린지 목표 거리 (m)",
    value=50000,
    step=5000
)

# 3) 신입/기존 및 부원 선택
all_groups = list(df['구분'].dropna().unique()) if '구분' in df.columns else []
selected_groups = st.sidebar.multiselect("구분 필터", options=all_groups, default=all_groups)

member_options = ["전체 부원"] + sorted(list(df['이름'].unique()))
selected_member = st.sidebar.selectbox("부원 개별 조회", member_options)

# 데이터 필터링 적용
filtered_df = df[
    (df['날짜'].dt.date >= start_date) & 
    (df['날짜'].dt.date <= end_date)
]
if selected_groups and '구분' in filtered_df.columns:
    filtered_df = filtered_df[filtered_df['구분'].isin(selected_groups)]
if selected_member != "전체 부원":
    filtered_df = filtered_df[filtered_df['이름'] == selected_member]

# ----------------------------------------------------
# 4. 상단 KPI 대시보드 지표
# ----------------------------------------------------
st.title("🚣 조정부 Data Lab & Memory Archive")
st.caption(f"조회 기간: **{start_date} ~ {end_date}**")

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("총 훈련 세션", f"{len(filtered_df):,} 회")
kpi2.metric("기간 총 훈련 거리", f"{filtered_df['총거리'].sum():,.0f} m")
avg_sec = filtered_df['페이스(초)'].dropna().mean()
kpi3.metric("평균 500m 스플릿", format_seconds_to_pace(avg_sec))
kpi4.metric("참여 인원", f"{filtered_df['이름'].nunique()} 명")

st.divider()

# ----------------------------------------------------
# 5. 누적 거리 챌린지 (순위 및 프로그레스 바)
# ----------------------------------------------------
st.subheader(f"🎯 {target_meters:,}m 누적 챌린지 현황")

# 기간 내 부원별 합산
cum_summary = df[
    (df['날짜'].dt.date >= start_date) & 
    (df['날짜'].dt.date <= end_date)
].groupby('이름')['총거리'].sum().reset_index()

cum_summary['달성률(%)'] = (cum_summary['총거리'] / target_meters * 100).round(1)
cum_summary['남은거리(m)'] = (target_meters - cum_summary['총거리']).apply(lambda x: max(0, x))
cum_summary['상태'] = cum_summary['총거리'].apply(lambda x: "🎖️ 완주" if x >= target_meters else "🚣 진행 중")
cum_summary = cum_summary.sort_values(by='총거리', ascending=False).reset_index(drop=True)

# 상위 3명 포디움 하이라이트
if not cum_summary.empty:
    top_n = min(len(cum_summary), 3)
    cols = st.columns(top_n)
    for i in range(top_n):
        row = cum_summary.iloc[i]
        cols[i].metric(
            label=f"🏆 {i+1}위: {row['이름']}",
            value=f"{row['총거리']:,.0f} m",
            delta=f"달성률 {row['달성률(%)']}% ({row['상태']})"
        )

# 부원별 진행도 프로그레스 바 리스트
with st.expander("📊 전체 부원별 챌린지 진행도 열람", expanded=True):
    for _, row in cum_summary.iterrows():
        p_col1, p_col2 = st.columns([1, 4])
        with p_col1:
            st.write(f"**{row['이름']}** ({row['상태']})")
            st.caption(f"{row['총거리']:,.0f}m / 남은 거리: {row['남은거리(m)']:,.0f}m")
        with p_col2:
            prog_val = min(float(row['달성률(%)'] / 100), 1.0)
            st.progress(prog_val)

st.divider()

# ----------------------------------------------------
# 6. 기량 분석 차트 (페이스 향상 추이 & 누적 레이스)
# ----------------------------------------------------
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.subheader("⚡ 500m 스플릿 페이스 변화 (위로 갈수록 빠름)")
    pace_df = filtered_df.dropna(subset=['페이스(초)']).sort_values('날짜')
    if not pace_df.empty:
        fig_pace = px.line(
            pace_df,
            x='날짜',
            y='페이스(초)',
            color='이름',
            markers=True,
            hover_data={'날짜': '|%Y-%m-%d', '평균페이스': True, '총거리': True, '페이스(초)': False}
        )
        # 로잉 페이스는 수치가 작을수록 빠르므로 Y축 반전
        fig_pace.update_yaxes(autorange="reversed", title="500m Split (초 단위)")
        fig_pace.update_layout(template="plotly_white", legend_title_text="부원 이름")
        st.plotly_chart(fig_pace, use_container_width=True)
    else:
        st.info("선택된 기간 내 페이스 데이터가 없습니다.")

with chart_col2:
    st.subheader("📈 일자별 누적 거리 증가 곡선")
    race_df = filtered_df.sort_values('날짜').copy()
    if not race_df.empty:
        race_df['누적거리'] = race_df.groupby('이름')['총거리'].cumsum()
        fig_race = px.line(
            race_df,
            x='날짜',
            y='누적거리',
            color='이름',
            markers=True
        )
        fig_race.add_hline(y=target_meters, line_dash="dash", line_color="red", annotation_text="목표선")
        fig_race.update_layout(template="plotly_white", legend_title_text="부원 이름")
        st.plotly_chart(fig_race, use_container_width=True)
    else:
        st.info("표시할 거리 데이터가 없습니다.")

st.divider()

# ----------------------------------------------------
# 7. 폴더형 메모리 인증 사진 아카이브
# ----------------------------------------------------
st.subheader("📷 에르고미터 메모리 인증 기록실")

photo_records = filtered_df[filtered_df['사진링크'].astype(str).str.contains("http", na=False)].sort_values('날짜', ascending=False)

if photo_records.empty:
    st.caption("선택된 기간에 등록된 사진이 없습니다.")
else:
    for _, row in photo_records.iterrows():
        title_str = f"[{row['날짜'].strftime('%Y-%m-%d')}] {row['이름']} - {row.get('운동종류', '운동')} | {row['총거리']:,.0f}m"
        with st.expander(title_str, expanded=False):
            st.write(f"**메모 / 스플릿 상세**: {row['메모'] if row['메모'] else '기록 없음'}")
            
            # 구글 드라이브 링크 파싱
            img_urls = extract_drive_image_urls(row['사진링크'])
            if img_urls:
                img_cols = st.columns(min(len(img_urls), 4))
                for idx, img_url in enumerate(img_urls):
                    with img_cols[idx % 4]:
                        st.image(img_url, caption=f"메모리 {idx+1}", use_container_width=True)
            else:
                st.caption("사진 변환 링크를 가져올 수 없습니다. 드라이브 폴더 공유 권한을 확인해주세요.")
