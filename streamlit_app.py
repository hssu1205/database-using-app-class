import streamlit as st
from streamlit_drawable_canvas import st_canvas
import firebase_admin
from firebase_admin import credentials, firestore, storage
from datetime import datetime
from PIL import Image
import io
import pyrebase
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

# 페이지 설정
st.set_page_config(
    page_title="학생 정서 모니터링",
    page_icon="😊",
    layout="wide"
)

# Firebase Admin SDK 초기화
@st.cache_resource
def initialize_firebase_admin():
    if not firebase_admin._apps:
        firebase_config = {
            "type": st.secrets["firebase"]["type"],
            "project_id": st.secrets["firebase"]["project_id"],
            "private_key_id": st.secrets["firebase"]["private_key_id"],
            "private_key": st.secrets["firebase"]["private_key"],
            "client_email": st.secrets["firebase"]["client_email"],
            "client_id": st.secrets["firebase"]["client_id"],
            "auth_uri": st.secrets["firebase"]["auth_uri"],
            "token_uri": st.secrets["firebase"]["token_uri"],
            "auth_provider_x509_cert_url": st.secrets["firebase"]["auth_provider_x509_cert_url"],
            "client_x509_cert_url": st.secrets["firebase"]["client_x509_cert_url"],
            "universe_domain": st.secrets["firebase"]["universe_domain"]
        }
        
        cred = credentials.Certificate(firebase_config)
        firebase_admin.initialize_app(cred, {
            'storageBucket': st.secrets["firebase"]["storage_bucket"]
        })
    
    return firestore.client()

# Pyrebase 초기화 (Authentication용)
@st.cache_resource
def initialize_pyrebase():
    config = {
        "apiKey": st.secrets["firebase"]["api_key"],
        "authDomain": st.secrets["firebase"]["auth_domain"],
        "databaseURL": st.secrets["firebase"]["database_url"],
        "projectId": st.secrets["firebase"]["project_id"],
        "storageBucket": st.secrets["firebase"]["storage_bucket"],
    }
    return pyrebase.initialize_app(config)

# Firebase 초기화
db = initialize_firebase_admin()
firebase = initialize_pyrebase()
auth = firebase.auth()

# 세션 상태 초기화
if 'mode' not in st.session_state:
    st.session_state.mode = None
if 'teacher_logged_in' not in st.session_state:
    st.session_state.teacher_logged_in = False
if 'user' not in st.session_state:
    st.session_state.user = None

# ================== 메인 화면 (모드 선택) ==================
def show_main_page():
    st.title("🏫 학생 정서 모니터링 시스템")
    st.write("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.write("")
        st.write("")
        
        # 학생 입장 버튼
        if st.button("👨‍🎓 학생 입장", use_container_width=True, type="primary", key="student_btn"):
            st.session_state.mode = "student"
            st.rerun()
        
        st.write("")
        
        # 교사 입장 버튼
        if st.button("👨‍🏫 교사 입장", use_container_width=True, key="teacher_btn"):
            st.session_state.mode = "teacher_login"
            st.rerun()

# ================== 학생 모드 ==================
def show_student_mode():
    # 뒤로가기 버튼
    if st.button("⬅️ 뒤로가기"):
        st.session_state.mode = None
        st.rerun()
    
    st.title("😊 학생 정서 모니터링")
    st.write("오늘의 기분을 체크하고 그림으로 표현해주세요!")

    # 컨테이너로 UI 구성
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📝 기본 정보")
        student_name = st.text_input("이름을 입력하세요", placeholder="홍길동")
        
        st.subheader("😊 오늘의 감정 상태")
        emotions = {
            "😊 매우 좋음": "매우 좋음",
            "🙂 좋음": "좋음",
            "😐 보통": "보통",
            "😔 안 좋음": "안 좋음",
            "😢 매우 안 좋음": "매우 안 좋음"
        }
        
        selected_emotion = st.radio(
            "현재 기분을 선택하세요:",
            options=list(emotions.keys()),
            index=2
        )

    with col2:
        st.subheader("🎨 감정 표현 그리기")
        st.write("현재 기분을 그림으로 표현해보세요")
        
        # 그리기 캔버스
        canvas_result = st_canvas(
            fill_color="rgba(255, 255, 255, 0)",
            stroke_width=3,
            stroke_color="#000000",
            background_color="#FFFFFF",
            width=400,
            height=400,
            drawing_mode="freedraw",
            key="canvas",
        )

    # 제출 버튼
    st.divider()
    col_button1, col_button2, col_button3 = st.columns([1, 1, 1])

    with col_button2:
        submit_button = st.button("✅ 제출하기", type="primary", use_container_width=True)

    # 데이터 제출 처리
    if submit_button:
        if not student_name:
            st.error("⚠️ 이름을 입력해주세요!")
        elif canvas_result.image_data is None:
            st.error("⚠️ 그림을 그려주세요!")
        else:
            try:
                with st.spinner("데이터를 저장하는 중..."):
                    # 현재 시간
                    timestamp = datetime.now()
                    
                    # 이미지를 PIL Image로 변환
                    img = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
                    
                    # RGBA를 RGB로 변환 (JPG는 투명도를 지원하지 않음)
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    rgb_img.paste(img, mask=img.split()[3])  # 알파 채널을 마스크로 사용
                    
                    # 이미지를 바이트로 변환
                    img_byte_arr = io.BytesIO()
                    rgb_img.save(img_byte_arr, format='JPEG', quality=95)
                    img_byte_arr.seek(0)
                    
                    # Storage에 이미지 업로드
                    bucket = storage.bucket()
                    blob_name = f"drawings/{student_name}_{timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
                    blob = bucket.blob(blob_name)
                    blob.upload_from_file(img_byte_arr, content_type='image/jpeg')
                    
                    # 이미지 URL 생성 (공개 URL)
                    blob.make_public()
                    image_url = blob.public_url
                    
                    # Firestore에 데이터 저장
                    doc_ref = db.collection('student_emotions').add({
                        'student_name': student_name,
                        'emotion': emotions[selected_emotion],
                        'emotion_icon': selected_emotion,
                        'drawing_url': image_url,
                        'drawing_path': blob_name,
                        'timestamp': timestamp,
                        'date': timestamp.strftime('%Y-%m-%d'),
                        'time': timestamp.strftime('%H:%M:%S')
                    })
                    
                    st.success(f"✅ {student_name}님의 정서 데이터가 성공적으로 저장되었습니다!")
                    st.balloons()
                    
                    # 저장된 정보 표시
                    st.info(f"""
                    **저장된 정보:**
                    - 이름: {student_name}
                    - 감정 상태: {selected_emotion}
                    - 저장 시간: {timestamp.strftime('%Y년 %m월 %d일 %H:%M:%S')}
                    """)
                    
            except Exception as e:
                st.error(f"❌ 오류가 발생했습니다: {str(e)}")

    # 푸터
    st.divider()
    st.caption("💡 제출 후 페이지를 새로고침하여 다시 작성할 수 있습니다.")

# ================== 교사 로그인 화면 ==================
def show_teacher_login():
    # 뒤로가기 버튼
    if st.button("⬅️ 뒤로가기"):
        st.session_state.mode = None
        st.rerun()
    
    st.title("👨‍🏫 교사 로그인")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.write("---")
        email = st.text_input("이메일", placeholder="teacher@example.com")
        password = st.text_input("비밀번호", type="password")
        
        st.write("")
        
        if st.button("🔐 로그인", use_container_width=True, type="primary"):
            if not email or not password:
                st.error("⚠️ 이메일과 비밀번호를 모두 입력해주세요!")
            else:
                try:
                    with st.spinner("로그인 중..."):
                        # Firebase Authentication으로 로그인
                        user = auth.sign_in_with_email_and_password(email, password)
                        st.session_state.user = user
                        st.session_state.teacher_logged_in = True
                        st.session_state.mode = "teacher_dashboard"
                        st.success("✅ 로그인 성공!")
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ 로그인 실패: 이메일 또는 비밀번호를 확인해주세요.")

# ================== 교사 대시보드 ==================
def show_teacher_dashboard():
    # 로그아웃 버튼
    col1, col2 = st.columns([6, 1])
    with col2:
        if st.button("🚪 로그아웃"):
            st.session_state.teacher_logged_in = False
            st.session_state.user = None
            st.session_state.mode = None
            st.rerun()
    
    st.title("📊 교사 대시보드")
    st.write("---")
    
    # Firestore에서 데이터 가져오기
    try:
        docs = db.collection('student_emotions').order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
        
        data_list = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            data_list.append(data)
        
        if not data_list:
            st.info("📭 아직 제출된 데이터가 없습니다.")
            return
        
        # 데이터프레임 생성
        df = pd.DataFrame(data_list)
        
        # 두 개의 컬럼으로 나누기
        col_left, col_right = st.columns([1, 1])
        
        # ===== 왼쪽: 감정 통계 막대그래프 =====
        with col_left:
            st.subheader("📊 학생 감정 상태 통계")
            
            # 감정별 카운트
            emotion_counts = df['emotion'].value_counts().reset_index()
            emotion_counts.columns = ['감정', '학생 수']
            
            # 감정 순서 정의
            emotion_order = ['매우 좋음', '좋음', '보통', '안 좋음', '매우 안 좋음']
            emotion_counts['감정'] = pd.Categorical(emotion_counts['감정'], categories=emotion_order, ordered=True)
            emotion_counts = emotion_counts.sort_values('감정')
            
            # 색상 매핑
            color_map = {
                '매우 좋음': '#2ecc71',
                '좋음': '#3498db',
                '보통': '#f39c12',
                '안 좋음': '#e67e22',
                '매우 안 좋음': '#e74c3c'
            }
            
            colors = [color_map.get(emotion, '#95a5a6') for emotion in emotion_counts['감정']]
            
            # Plotly 막대그래프
            fig = go.Figure(data=[
                go.Bar(
                    x=emotion_counts['감정'],
                    y=emotion_counts['학생 수'],
                    marker_color=colors,
                    text=emotion_counts['학생 수'],
                    textposition='auto',
                )
            ])
            
            fig.update_layout(
                xaxis_title="감정 상태",
                yaxis_title="학생 수",
                height=400,
                showlegend=False
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # 통계 정보
            st.write("**📈 통계 요약**")
            total_students = len(df)
            st.metric("총 제출 수", total_students)
            
            if total_students > 0:
                positive_count = len(df[df['emotion'].isin(['매우 좋음', '좋음'])])
                positive_ratio = (positive_count / total_students) * 100
                st.metric("긍정적 감정 비율", f"{positive_ratio:.1f}%")
        
        # ===== 오른쪽: 학생 그림 갤러리 =====
        with col_right:
            st.subheader("🎨 학생 그림 갤러리")
            
            # 최근 그림들만 표시 (최대 9개)
            display_count = min(9, len(df))
            
            # 3x3 그리드로 표시
            for i in range(0, display_count, 3):
                cols = st.columns(3)
                for j in range(3):
                    idx = i + j
                    if idx < display_count:
                        with cols[j]:
                            row = df.iloc[idx]
                            st.image(row['drawing_url'], use_container_width=True)
                            st.caption(f"**{row['student_name']}** - {row['emotion_icon']}")
                            st.caption(f"{row['date']} {row['time']}")
            
            # 더 많은 데이터가 있으면 표시
            if len(df) > 9:
                st.info(f"💡 총 {len(df)}개 중 최근 9개를 표시하고 있습니다.")
        
        # 전체 데이터 테이블
        st.write("---")
        st.subheader("📋 전체 제출 데이터")
        
        # 표시할 컬럼 선택
        display_df = df[['student_name', 'emotion', 'date', 'time']].copy()
        display_df.columns = ['학생 이름', '감정 상태', '날짜', '시간']
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
    except Exception as e:
        st.error(f"❌ 데이터를 불러오는 중 오류가 발생했습니다: {str(e)}")

# ================== 메인 라우터 ==================
if st.session_state.mode is None:
    show_main_page()
elif st.session_state.mode == "student":
    show_student_mode()
elif st.session_state.mode == "teacher_login":
    show_teacher_login()
elif st.session_state.mode == "teacher_dashboard" and st.session_state.teacher_logged_in:
    show_teacher_dashboard()
else:
    # 잘못된 접근
    st.session_state.mode = None
    st.rerun()
