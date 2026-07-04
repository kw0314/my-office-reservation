# My Office Reservation

이 프로젝트는 Django를 기반으로 만들어진 사무실 예약 시스템입니다.

## 프로젝트 설명
사무실 내 자원(좌석, 회의실 등)의 예약 현황을 관리하고 사용자가 직접 예약할 수 있는 웹 애플리케이션입니다.

---

## 설치 및 설정 방법

### 1. 프로젝트 복제 및 디렉토리 이동
```bash
git clone <repository_url>
cd my-office-reservation
```

### 2. 가상 환경(Virtual Environment) 설정
가상 환경을 생성하고 활성화합니다.

* **Windows의 경우 (PowerShell/CMD)**:
  ```powershell
  python -m venv .venv
  .venv\Scripts\activate
  ```
* **macOS / Linux의 경우**:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

### 3. 패키지 설치
가상 환경이 활성화된 상태에서 필요한 의존성 패키지를 설치합니다.
```bash
pip install -r requirements.txt
```

### 4. 데이터베이스(PostgreSQL) 생성
이 프로젝트는 PostgreSQL 데이터베이스를 사용합니다. 데이터베이스와 사용자를 생성해야 합니다.

1. PostgreSQL 클라이언트(`psql`) 또는 pgAdmin 등을 사용하여 데이터베이스 서버에 접속합니다.
2. 아래 SQL 명령어를 실행하여 데이터베이스와 사용자를 생성하고 권한을 부여합니다.
   ```sql
   -- 1. 데이터베이스 생성
   CREATE DATABASE catechism_db;

   -- 2. 사용자 생성 및 비밀번호 설정
   CREATE USER catechism_user WITH PASSWORD 'your_secure_password';

   -- 3. 데이터베이스 소유자 변경 (권장)
   ALTER DATABASE catechism_db OWNER TO catechism_user;

   -- 4. 스키마 권한 부여 (PostgreSQL 15 이상 버전 대응)
   \c catechism_db
   GRANT ALL ON SCHEMA public TO catechism_user;
   ```

### 5. 환경 변수(`.env`) 설정
프로젝트 루트 디렉토리에 있는 `.env.example` 파일을 복사하여 `.env` 파일을 생성합니다.

* **Windows (PowerShell)**:
  ```powershell
  Copy-Item .env.example .env
  ```
* **macOS / Linux**:
  ```bash
  cp .env.example .env
  ```

생성된 `.env` 파일을 에디터로 열고, 아래와 같이 앞서 설정한 데이터베이스 정보와 시크릿 키를 알맞게 수정합니다.

```env
# Django 설정
SECRET_KEY=임의의_길고_안전한_시크릿키_문자열
DEBUG=True
ALLOWED_HOSTS=*

# 데이터베이스(PostgreSQL) 설정
DB_NAME=catechism_db
DB_USER=catechism_user
DB_PASSWORD=your_secure_password  -- 4단계에서 설정한 사용자 비밀번호 입력
DB_HOST=127.0.0.1
DB_PORT=5432
```

### 6. 데이터베이스 마이그레이션 적용
데이터베이스 스키마와 테이블을 생성하기 위해 마이그레이션을 실행합니다.
```bash
python manage.py migrate
```

### 7. 관리자(Superuser) 계정 생성 (선택 사항)
웹 어드민 페이지(`http://localhost:8000/admin`)에 로그인하여 자원을 관리하기 위해 관리자 계정을 생성합니다.
```bash
python manage.py createsuperuser
```

---

## 실행 방법

### 1. 로컬 환경에서 실행 (동일 PC 접속만 허용)
개발 중인 PC에서만 접속하려면 기본 명령어로 실행합니다:
```bash
python manage.py runserver
```
* **접속 주소**: [http://127.0.0.1:8000](http://127.0.0.1:8000)

### 2. 외부(다른 PC, 모바일 기기 등) 접속 허용하여 실행
외부 IP 주소나 동일한 와이파이(LAN) 대역의 다른 기기에서 접속할 수 있게 하려면 호스트를 `0.0.0.0`으로 바인딩하여 실행해야 합니다:
```bash
python manage.py runserver 0.0.0.0:8000
```
* **접속 주소**: `http://<서버의_실제_IP_주소>:8000` (예: `http://192.168.0.10:8000`)

> [!NOTE]
> * **방화벽 설정**: 외부 접속이 되지 않는 경우, 실행 중인 PC의 방화벽(Windows 방화벽 등)에서 `8000` 포트가 열려 있는지 확인하세요.
> * **허용 호스트 설정 (`.env`)**: 외부 접속 시 Django가 요청을 거부하는 경우 `.env` 파일의 `ALLOWED_HOSTS` 값을 `*`로 설정하거나 실제 외부 IP 또는 도메인을 추가해 주어야 합니다. (현재 기본값은 `*`로 지정되어 있어 접속이 허용됩니다.)

---

## 데이터베이스 초기화 방법

데이터베이스를 초기화하는 방법은 두 가지 목적에 따라 나뉩니다.

### 방법 1. 테이블 구조(스키마)는 유지하고 데이터만 전부 삭제하기
테이블이나 인덱스 등은 그대로 두고 등록된 데이터(사용자, 예약 건, 리스트 등)만 모두 삭제하여 깔끔한 상태로 되돌리고 싶을 때 사용합니다. Django 가상 환경이 활성화된 상태에서 아래 명령어를 실행합니다.

```bash
python manage.py flush
```
* 이 명령어를 실행하면 "정말 모든 데이터를 삭제하겠습니까?"라는 확인 문구가 나옵니다. `yes`를 입력하면 모든 데이터가 비워지며 초기 상태로 돌아갑니다.
* 데이터가 비워진 후에는 `python manage.py createsuperuser`를 다시 실행해 관리자 계정을 새로 만드셔야 합니다.

### 방법 2. 데이터베이스 테이블을 모두 지우고 완전히 처음부터 다시 시작하기
모델 변경 과정에서 마이그레이션 꼬임 등으로 인해 테이블 구조 자체를 완전히 날리고 마이그레이션 단계부터 깨끗하게 다시 적용하고 싶을 때 사용합니다.

1. PostgreSQL 클라이언트(`psql` 또는 pgAdmin 등)에서 `catechism_db` 데이터베이스에 접속한 상태로 아래 SQL 명령어를 실행하여 `public` 스키마를 삭제 후 재 생성합니다.
   ```sql
   -- 기존 스키마 및 하위 모든 테이블 삭제
   DROP SCHEMA public CASCADE;

   -- 새 스키마 생성
   CREATE SCHEMA public;

   -- 스키마 소유권 권한 재부여
   GRANT ALL ON SCHEMA public TO catechism_user;
   GRANT ALL ON SCHEMA public TO public;
   ```
2. Django CLI에서 마이그레이션을 다시 실행하여 테이블을 처음부터 재생성합니다.
   ```bash
   python manage.py migrate
   ```
3. 관리자 계정을 생성합니다.
   ```bash
   python manage.py createsuperuser
   ```


