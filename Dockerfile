# 기본 Python 3.11 이미지 사용
FROM python:3.11-slim

# 작업 디렉토리 생성 및 이동
WORKDIR /app

# requirements.txt 복사 및 설치
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY . .

# Streamlit 앱 실행 (포트 8501)
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
