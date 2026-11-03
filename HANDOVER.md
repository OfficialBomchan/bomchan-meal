# 봄찬밀(봄찬 점심 체크) 인수인계

이 문서는 **봄찬밀 앱만** 다룹니다. 봄찬ops·현장관리앱 등 다른 서비스는 별도 문서(해당 저장소의 HANDOVER.md)를 보세요.
같은 EC2 서버에 여러 서비스가 같이 떠 있으니, **다른 서비스 파일·서비스는 절대 건드리지 마세요.**

- 주소: https://bomchan.asia/meal/
- 용도: 점심 식수(먹음/안먹음) 체크 + 패널티 + 식대 정산 + 구성원 관리
- 코드: https://github.com/OfficialBomchan/bomchan-meal (⚠ 아래 "배포" 항목 꼭 읽을 것 — 자동배포 아님)

## 처음 맡으면 이 순서로

1. 이 문서 전체를 읽는다
2. `main.py`, `index.html`를 한 번 쭉 읽는다 (단일 파일 구조라 금방 봄)
3. 서버에 SSH로 들어가서 서비스 상태를 확인해본다 (아래 "서버" 항목)
4. 작은 수정을 하나 해보고 배포까지 직접 해본다

## 구조

- **백엔드**: `main.py` — FastAPI, 단일 파일. Postgres(운영)/SQLite(로컬 기본값) 겸용 `Conn` 클래스로 추상화돼 있음
- **프론트엔드**: `index.html` — 단일 HTML 파일, 빌드 과정 없음. 수정하면 그대로 서버에 올리면 끝
- **공휴일**: `kr_holidays.py` — `HOLIDAYS` 딕셔너리에 날짜 하드코딩. **2028년 이후분이 비어있으니 연말에 채워야 함**
- 로컬 저장소: `C:\Users\user\Downloads\bomchan-meal\` (Windows PC 기준). GitHub 레포와 연결돼 있지만, **지금 이 폴더에 2026-11-03 기준 커밋 안 된 수정사항(index.html, main.py)이 남아있음** — 인계 시 `git status`로 확인하고 커밋·푸시부터 할 것

## 서버

```bash
ssh -i ~/.ssh/ec2_claude_key ubuntu@13.209.127.200
```

- 앱 경로: `/home/ubuntu/bomchan-meal/` (main.py, index.html, kr_holidays.py, venv/)
- 환경변수: `/etc/bomchan-meal/env` (DATABASE_URL 등 — 비밀값이라 여기 말고 어디에도 적지 말 것)
- systemd 서비스: `bomchan-meal.service`, 포트 8799 (127.0.0.1만 바인딩, 외부 노출은 Apache가 담당)
  ```bash
  sudo systemctl status bomchan-meal
  sudo systemctl restart bomchan-meal
  journalctl -u bomchan-meal -f        # 실시간 로그
  ```
- Apache 리버스프록시 설정: `/etc/apache2/sites-enabled/bomchan-asia-le-ssl.conf` 안의 `/meal/` 블록
  ```
  RedirectMatch 301 ^/meal$ /meal/
  ProxyPass /meal/ http://127.0.0.1:8799/
  ProxyPassReverse /meal/ http://127.0.0.1:8799/
  ```
  이 블록 건드릴 일은 거의 없음. 건드렸으면 `sudo apache2ctl configtest` 먼저 돌려보고 `reload`.
- **같은 서버에 다른 서비스도 많음** (bomchan-ops-v2 등). 포트·서비스 이름 정확히 확인하고 작업할 것.

## DB (Postgres, 서버 로컬)

```bash
sudo -u postgres psql bomchan_meal
```

테이블:
- `members(id, name, active)` — 구성원 명단. `active=0`이 퇴사자(소프트 삭제, 기록은 남김)
- `meals(member, d, status)` — PK(member, d). status는 `먹음`/`안먹음`만 저장(미정은 행 자체가 없음)
- `penalties(member, d)` — 당일 08:00까지 미정이면 자동 적립. 한 번 찍히면 안 지워짐
- `logs(id, at, member, d, old, new, reason)` — 지난 날짜·08:00 이후 변경 이력(사유 포함)
- `meta(k, v)` — `start`(추적 시작일), `admin_pin`, `price`(1식 단가) 등 설정값
- `done(d)` — 패널티 계산이 끝난 날짜 표시(멱등성용)

## 배포

```bash
scp -i ~/.ssh/ec2_claude_key index.html main.py ubuntu@13.209.127.200:/home/ubuntu/bomchan-meal/
# main.py를 바꿨으면:
ssh -i ~/.ssh/ec2_claude_key ubuntu@13.209.127.200 "sudo systemctl restart bomchan-meal"
# index.html만 바꿨으면 재시작 불필요 (정적 파일이라 바로 반영)
```

⚠ **`kr_holidays.py` 파일 안 주석에 "GitHub에 올리면 자동 배포된다"고 적혀있는데, 확인해보니 현재 그런 자동화는 없습니다.** GitHub Actions도, 서버 쪽 git pull 훅도 없음 — 서버 디렉토리 자체가 git 저장소가 아닙니다. 지금은 **위 scp 방식이 유일한 배포 경로**입니다. 자동배포를 실제로 만들 게 아니라면 저 주석을 정정하거나, 자동배포를 새로 구축해야 합니다.

재시작 시 30초쯤 접속이 끊기니, **업무시간 배포는 피할 것** (재시작 사이에 들어온 요청이 그냥 날아간 전례 있음).

## 주의해야 할 것들 (실제로 문제됐던 것들)

- **`meta.start`(추적 시작일) 이전 날짜는 앱에서 절대 수정 불가.** PUT `/api/meal`이 `start <= date < today`가 아니면 무조건 거부함. 과거 데이터를 소급 입력해야 하면(정산 대조 등) DB에 직접 INSERT해야 하고, 이 경우 `start`도 같이 당겨야 그 날짜가 정상적으로 관리됨. (2026-11-03, 10월 정산표 대조 중 10/1이 이 때문에 막혀서 직접 처리함 — `C:\Users\user\Downloads\bomchan-meal` 작업 이력 참고)
- **패널티는 "그 날짜가 처음 지나갈 때" 당시의 활성 구성원 기준으로만 계산되고, 그 뒤로 다시 계산 안 됨.** 신입을 중간에 추가하면 그 이전 날짜들은 영영 패널티 대상에서 빠짐 (마이그레이션 직후 날짜들에서 실제로 발생 — `active_names()`가 당시 비어있던 `members` 테이블을 봤기 때문). 이런 날짜는 화면에 "수정"이라고만 뜨고 패널티 표시가 안 돼서 놓치기 쉬움.
- **퇴사자(active=0)는 소프트 삭제만.** `rmMember()`가 `active`를 0으로 바꿀 뿐 `meals`·`penalties` 기록은 그대로 남음 — 정산 때문에 일부러 이렇게 설계됨. DB에서 직접 지우지 말 것.
- **단가(`price`)를 바꾸면 전체 월 과거 데이터 금액도 전부 재계산되어 보임.** `식수 × 현재 단가`라서, 월별로 단가가 달랐던 걸 반영하려면 코드 수정이 필요함(지금은 지원 안 함).
- **공휴일(`kr_holidays.py`)은 연말에 다음 해 치를 채워야 함.** 비어있으면 그냥 평일로 취급돼서 패널티가 잘못 쌓임.
- 관리자 PIN은 `meta.admin_pin`에 평문 저장(기본값 0000). 구성원 추가/삭제할 때만 씀. 중요 비밀값은 아니지만, 바꾸고 싶으면 DB에서 직접 UPDATE.

## 최근 변경 이력 (2026-11)

- Render(무료 Postgres 30일 만료) → EC2로 전체 이전 (2026-10-27)
- 구성원 관리(추가/퇴사/복귀) 기능 추가, PIN 보호
- 식대 관리 화면에 월별 구성원별 식수·금액 표 추가
- 날짜 클릭 방식을 "미정→먹음→안먹음 3단 순환"에서 "클릭하면 먹음/안먹음 바로 선택하는 모달"로 변경
- 10월 정산표(대동푸드) 대조해서 날짜별 누락분 10식 보정 완료 (141식 일치 확인)

## 다음 담당자가 바로 알아야 할 것

- 이 레포는 봄찬ops와 별도 레포(`OfficialBomchan/bomchan-meal`)이고, 서버 배포는 수동 scp 뿐입니다
- 로컬 작업 폴더(`C:\Users\user\Downloads\bomchan-meal`)에 아직 안 올린 커밋이 있을 수 있으니 `git status`부터 확인하세요
- 뭔가 고칠 땐 **배포 전에 담당자/대표에게 먼저 확인** — 전사가 매일 쓰는 실운영 앱입니다
