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

Linux 서버의 `/srv` 경로에 배포용으로 복제하려면 `/srv`에 쓰기 권한이 필요합니다.

```bash
sudo git clone <repository_url> /srv/my-office-reservation
sudo chown -R $USER:$USER /srv/my-office-reservation
cd /srv/my-office-reservation
```

SSH 저장소(`git@github.com:...`)를 사용하는 경우 `sudo git clone`은 root 사용자의 SSH 키를 찾기 때문에 실패할 수 있습니다. 이때는 먼저 폴더를 만들고 현재 사용자에게 권한을 준 뒤, 일반 사용자 권한으로 복제합니다.

```bash
sudo mkdir -p /srv/my-office-reservation
sudo chown -R $USER:$USER /srv/my-office-reservation
git clone git@github.com:<user>/<repository>.git /srv/my-office-reservation
cd /srv/my-office-reservation
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

1. PostgreSQL 서버가 실행 중인지 먼저 확인합니다.
   - Windows: 서비스 목록에서 PostgreSQL 서비스가 실행 중인지 확인합니다.
   - Linux/macOS: `sudo systemctl status postgresql` 또는 `brew services list` 등의 명령으로 상태를 확인합니다.
2. 접속 방법은 두 가지가 있습니다.
   - `psql` CLI 사용: 터미널에서 아래와 같이 접속합니다.
     ```bash
     psql -U postgres
     ```
     접속 후 비밀번호를 입력하고, 데이터베이스를 생성합니다.
   - pgAdmin 사용: pgAdmin을 실행한 뒤, "Servers" → "Add New Server"로 PostgreSQL 서버를 등록합니다.
     - Host name/address: `127.0.0.1`
     - Port: `5432`
     - Maintenance database: `postgres`
     - Username: `postgres`
     - Password: 설치 시 설정한 비밀번호
3. 아래 SQL 명령어를 실행하여 데이터베이스와 사용자를 생성하고 권한을 부여합니다.
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

### 데이터베이스 접속 방법
프로젝트는 PostgreSQL을 사용하므로, 아래 두 가지 방법으로 데이터베이스에 접속할 수 있습니다.

#### 1) PostgreSQL CLI로 접속
```bash
psql -U catechism_user -d catechism_db -h 127.0.0.1
```
비밀번호를 입력하면 `psql` 셸에 들어갑니다.

#### 데이터베이스 백업/복원
아래 명령어로 데이터베이스를 백업하고 복원할 수 있습니다.

##### PostgreSQL 백업/복원
```bash
# 백업
pg_dump -U catechism_user -h 127.0.0.1 -d catechism_db -Fc -f catechism_db.backup

# 복원
pg_restore -U catechism_user -h 127.0.0.1 -d catechism_db catechism_db.backup
```

##### PostgreSQL 데이터를 다른 PC로 옮기기
PostgreSQL은 `db.sqlite3`처럼 프로젝트 폴더 안의 파일 하나를 복사하는 방식이 아닙니다. 원본 PC에서 `pg_dump`로 백업 파일을 만들고, 대상 PC의 PostgreSQL에 `pg_restore`로 복원해야 합니다.

1. 원본 PC에서 백업합니다.
   ```bash
   pg_dump -U catechism_user -h 127.0.0.1 -d catechism_db -Fc -f catechism_db.backup
   ```
2. `catechism_db.backup` 파일을 USB, 공유 폴더, SCP 등으로 대상 PC에 복사합니다.
3. 대상 PC에서 Django/Gunicorn 등 DB에 접속 중인 서버를 멈춥니다.
   ```bash
   sudo systemctl stop catechism
   # 서비스 이름이 다르면 catechism 대신 실제 서비스 이름을 사용합니다.
   ```
4. 대상 DB를 삭제하고 빈 DB를 다시 만듭니다. 이 단계는 기존 데이터를 지우므로, 필요하면 먼저 대상 PC의 DB를 별도로 백업하세요.
   ```bash
   dropdb -U catechism_user -h 127.0.0.1 catechism_db
   sudo -u postgres createdb -O catechism_user catechism_db
   ```
   `catechism_user`에게 DB 생성 권한이 없으면 `createdb -U catechism_user ...` 명령은 `permission denied to create database`로 실패합니다. 그 경우 위처럼 `sudo -u postgres createdb -O catechism_user catechism_db`를 사용합니다.
5. 복원합니다.
   ```bash
   pg_restore -U catechism_user -h 127.0.0.1 -d catechism_db catechism_db.backup
   ```
6. 복원 후 데이터 개수를 확인합니다.
   ```bash
   python manage.py shell -c "from reservations.models import Room, Reservation; print(Room.objects.count(), Reservation.objects.count())"
   ```
7. 서버를 다시 시작합니다.
   ```bash
   sudo systemctl start catechism
   ```

##### `pg_restore` 중복 키 오류 해결
복원 중 아래와 같은 오류가 나오면, 빈 DB가 아닌 곳에 백업을 다시 복원한 것입니다.

```text
ERROR: duplicate key value violates unique constraint
Key (content_type_id, codename)=(1, add_logentry) already exists.
Key (id)=(1) already exists.
Key (name)=(C102) already exists.
```

이 경우 일부 테이블만 복원되고 일부는 실패할 수 있으므로, 대상 DB를 완전히 비운 뒤 다시 복원하는 것이 가장 안전합니다.

```bash
# DB를 사용 중인 웹 서버가 있다면 먼저 중지
sudo systemctl stop catechism

# DB 삭제
dropdb -U catechism_user -h 127.0.0.1 catechism_db

# catechism_user가 DB 생성 권한이 없을 때는 postgres 계정으로 생성
sudo -u postgres createdb -O catechism_user catechism_db

# 복원
pg_restore -U catechism_user -h 127.0.0.1 -d catechism_db catechism_db.backup
```

`dropdb`가 `database "catechism_db" is being accessed by other users`로 실패하면 아직 DB에 접속 중인 세션이 있는 것입니다. 웹 서버를 멈추거나, 필요하면 PostgreSQL 관리자로 접속해 세션을 끊을 수 있습니다.

```bash
sudo -u postgres psql
```

```sql
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'catechism_db'
  AND pid <> pg_backend_pid();

\q
```

그 뒤 `dropdb`, `createdb`, `pg_restore`를 다시 실행합니다.

##### SQLite 백업/복원 (로컬 개발 환경 기준)
```bash
# 백업
copy db.sqlite3 db.sqlite3.bak
# 또는 Linux/macOS: cp db.sqlite3 db.sqlite3.bak

# 복원
copy db.sqlite3.bak db.sqlite3
# 또는 Linux/macOS: cp db.sqlite3.bak db.sqlite3
```

> 복원 전에는 Django 서버를 중지한 상태로 진행하는 것이 안전합니다.

유용한 명령어:
```sql
\dt                -- 테이블 목록 확인
\d reservations_room -- 특정 테이블 구조 확인
SELECT * FROM reservations_room;  -- 데이터 조회
\q                 -- 종료
```

#### 2) Django 관리 명령으로 접속
Django 설정이 정상이라면 프로젝트 루트에서 아래 명령으로도 접속할 수 있습니다.
```bash
python manage.py dbshell
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

## 부팅 시 자동 실행 설정 (Linux)
리눅스 서버가 부팅될 때 Django 앱이 자동으로 실행되도록 하려면 `systemd` 서비스를 등록하면 됩니다.

### 1. 서비스 파일 생성
```bash
sudo nano /etc/systemd/system/my-office-reservation.service
```

아래 내용을 넣습니다.
```ini
[Unit]
Description=My Office Reservation Django App
After=network.target

[Service]
User=kwlee
WorkingDirectory=/srv/my-office-reservation
Environment=PATH=/srv/my-office-reservation/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=/srv/my-office-reservation/.venv/bin/python /srv/my-office-reservation/manage.py runserver 0.0.0.0:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

> `User=kwlee`는 실제 로그인 사용자명으로 바꿔주세요. 프로젝트 경로도 실제 위치에 맞게 수정하세요.

### 2. 서비스 등록
```bash
sudo systemctl daemon-reload
sudo systemctl enable my-office-reservation.service
sudo systemctl start my-office-reservation.service
```

### 3. 상태 확인
```bash
sudo systemctl status my-office-reservation.service
```

### 4. 재시작/중지
```bash
sudo systemctl restart my-office-reservation.service
sudo systemctl stop my-office-reservation.service
```

> `runserver`는 개발/테스트 용도입니다. 실제 운영 환경에서는 보통 `gunicorn` + `nginx` 조합을 권장합니다.

---

## 가상환경 초기화 방법
가상환경이 꼬였거나 패키지 설치 상태를 깨끗하게 다시 시작하고 싶다면 아래 순서로 초기화하면 됩니다.

### 1. 기존 가상환경 삭제
* **Linux / macOS**:
  ```bash
  rm -rf .venv
  ```
* **Windows (PowerShell)**:
  ```powershell
  Remove-Item -Recurse -Force .venv
  ```

### 2. 새 가상환경 생성
* **Linux / macOS**:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```
* **Windows (PowerShell)**:
  ```powershell
  python -m venv .venv
  .venv\Scripts\Activate.ps1
  ```

### 3. 의존성 재설치
```bash
pip install -r requirements.txt
```

### 4. 필요 시 pip 캐시 정리
```bash
pip cache purge
```

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
