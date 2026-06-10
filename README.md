# My Office Reservation

이 프로젝트는 Django를 기반으로 만들어진 사무실 예약 시스템입니다.

## 프로젝트 설명
사무실 내 자원(좌석, 회의실 등)의 예약 현황을 관리하고 사용자가 직접 예약할 수 있는 웹 애플리케이션입니다.

## 설치 방법

1. 프로젝트 디렉토리로 이동합니다.
2. 가상 환경을 생성하고 활성화합니다.
   ```bash
   python -m venv venv
   # Windows의 경우
   .\venv\Scripts\activate
   # macOS/Linux의 경우
   source venv/bin/activate
   ```
3. 필요한 패키지를 설치합니다.
   ```bash
   pip install -r requirements.txt
   ```
4. 환경 변수 파일을 설정합니다. `.env.example` 파일을 복사하여 `.env` 파일을 만들고 알맞게 값을 입력합니다.
5. 데이터베이스 마이그레이션을 진행합니다.
   ```bash
   python manage.py migrate
   ```

## 실행 방법

로컬 개발 서버를 실행하려면 다음 명령어를 입력합니다.

```bash
python manage.py runserver
```

명령어 실행 후 브라우저에서 `http://127.0.0.1:8000`으로 접속하여 애플리케이션을 확인할 수 있습니다.
