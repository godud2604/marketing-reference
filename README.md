# 마케팅 레퍼런스 앱

## 사용법

### 1. 가상환경 설정

#### macOS/Linux
```bash
# 가상환경 생성
python3 -m venv venv

# 가상환경 활성화
source venv/bin/activate
```

#### Windows
```bash
# 가상환경 생성
python -m venv venv

# 가상환경 활성화
venv\Scripts\activate
```

### 2. 패키지 설치
```bash
pip install -r requirements.txt
```

### 3. Streamlit 앱 실행
```bash
streamlit run app.py
```

앱이 실행되면 브라우저가 자동으로 열리며, 기본적으로 `http://localhost:8501`에서 접속할 수 있습니다.

### 가상환경 종료
```bash
deactivate
```
