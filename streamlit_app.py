import streamlit as st
from streamlit_drawable_canvas import st_canvas
import firebase_admin
from firebase_admin import credentials, firestore, storage
from datetime import datetime
from PIL import Image
import io

# Firebase 초기화
@st.cache_resource
def initialize_firebase():
    if not firebase_admin._apps:
        # secrets.toml에서 Firebase 자격 증명 읽기
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

# Firestore 클라이언트 초기화
db = initialize_firebase()

# 페이지 설정
st.set_page_config(
    page_title="학생 정서 모니터링",
    page_icon="😊",
    layout="wide"
)

# 제목
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
            st.write("자세한 오류:", e)

# 푸터
st.divider()
st.caption("💡 제출 후 페이지를 새로고침하여 다시 작성할 수 있습니다.")
