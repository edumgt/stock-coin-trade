# AWS 공개 데모 배포 절차

> **2026-09-28 폐기.** 비용을 줄이려고 공개 데모를 Lightsail 한 대로 옮기고 이 문서의 CloudFormation 스택을 지웠다. 지금 운영은 [Lightsail 운영](lightsail.md), 이전 과정은 [이전 기록](../evidence/lightsail-migration-2026-09-28.md)을 따른다. 아래는 EC2 구성을 다시 올릴 때를 위한 기록이다.

[ADR-0003](../adr/0003-aws-demo-topology.md)의 구성을 처음 올리는 순서다. 명령은 `ap-northeast-2`를 예로 든다.

## 1. 스택 만들기

```bash
ami=$(aws ssm get-parameter --region ap-northeast-2 --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 --query Parameter.Value --output text)
aws cloudformation deploy --region ap-northeast-2 --stack-name stockdesk \
  --template-file infra/cloudformation/stockdesk.yaml --capabilities CAPABILITY_IAM \
  --parameter-overrides BudgetEmail=<메일> MonthlyBudgetUsd=35 InstanceType=t3.small \
    AmiId="$ami" SiteAddress=<공개 주소>
aws cloudformation describe-stacks --stack-name stockdesk --query 'Stacks[0].Outputs'
```

- **AMI는 고정한다.** `AmiId`에 SSM "최신" 경로를 넣으면 스택을 업데이트할 때마다 최신 이미지로 다시 풀려 하나뿐인 서버가 교체될 수 있다. 이미 있는 스택을 업데이트할 때는 실행 중인 인스턴스의 ImageId를 넘긴다(`aws ec2 describe-instances --instance-ids <InstanceId> --query 'Reservations[0].Instances[0].ImageId'`).
- 업데이트 전에는 `--no-execute-changeset`으로 변경 세트를 만들고, `Host`·`DataVolume`·`PublicAddress`·`InstanceRole`·`DeployRole`이 교체되지 않는지 확인한 뒤 실행한다.
- `SiteAddress`는 GitHub `SITE_ADDRESS` 변수와 같은 값이다. 도메인을 바꾸면 둘 다 바꾼다.
- 템플릿은 ASCII만 쓴다(CloudFormation이 저장할 때 한글 등은 `??`로 깨진다. 테스트가 막는다).

- 계정에 GitHub OIDC 공급자가 이미 있으면 다음을 추가한다: `CreateGitHubOidcProvider=false ExistingGitHubOidcProviderArn=<ARN>`
- 예산은 인스턴스 크기에 맞춘다. 서울 온디맨드 기준(2026-09-25 가격 API) t3.small은 EBS 50 GiB·공인 IPv4를 더해 월 약 $28, t3.medium은 약 $46이다. t3.medium이면 `MonthlyBudgetUsd=50`으로 올린다.
- 적용 전에 변경 내용을 보려면 `--no-execute-changeset`으로 변경 세트만 만든다.

## 2. 비밀값(SSM Parameter Store, SecureString)

파라미터 이름의 마지막 부분이 환경변수 이름이 된다. 예: `/stock-coin-trade/prod/secret-key` → `SECRET_KEY`

| 이름 | 내용 |
|---|---|
| `secret-key` | 32자 이상 무작위 값 |
| `admin-email` | 관리자 주소(`admin@admin.com` 불가) |
| `mariadb-user`, `mariadb-password`, `mariadb-root-password` | MariaDB 계정 |
| `quant-db-name`, `quant-db-user`, `quant-db-password` | PostgreSQL 계정 |
| `anthropic-api-key` | AI 리서치를 켤 때만 |
| `ai-enabled`, `ai-monthly-budget-usd`, `ai-invite-pepper` | AI를 켤 때: `true`, 월 예산(USD), 32자 이상 무작위 값 |

```bash
aws ssm put-parameter --type SecureString --name /stock-coin-trade/prod/secret-key --value "$(openssl rand -base64 48)"
```

## 3. 도메인

1. 스택 출력 `PublicIp`로 A 레코드를 만든다.
   - 도메인이 없으면 `SITE_ADDRESS`에 `<IP의 점을 대시로>.sslip.io`(예: `3-35-1-2.sslip.io`)를 쓴다. 이 이름은 그 IP로 풀리므로 A 레코드 없이 Caddy가 인증서를 받는다. 나중에 도메인을 사면 변수만 바꾸고 다시 배포한다.
2. Caddy는 첫 요청 때 인증서를 받는다. 80·443이 열려 있어야 한다.

## 4. GitHub

워크플로는 `.github/workflows/deploy.yml`이고 수동 실행(`workflow_dispatch`)만 받는다.

1. 저장소 Settings → Environments에서 `production`을 만든다. 승인자(required reviewers) 지정은 선택이다.
2. 같은 환경에 변수를 넣는다. 모두 비밀값이 아닌 식별자다.
   - `AWS_REGION`, `AWS_DEPLOY_ROLE_ARN`, `EC2_INSTANCE_ID`, `RELEASE_BUCKET`, `LOG_GROUP`: 스택 출력값
   - `SITE_ADDRESS`: 도메인
3. Actions → Deploy → Run workflow로 배포한다.

## 5. 배포 후

Session Manager로 접속해 관리자 계정과 AI 초대 코드를 만든다.

```bash
aws ssm start-session --target <InstanceId>
sudo docker compose -p stockdesk exec python-backend flask --app app create-admin
sudo docker compose -p stockdesk exec python-backend flask --app app create-invite --label <이름> --max-requests 20
```

공용 웹 데모를 제공할 때는 새 백엔드 컨테이너에서 `flask --app app create-demo`를 별도로 실행한다. 지정된 공개 체험 계정을 일반 회원으로 만들며, 같은 데모는 그대로 두고 기존 일반 회원·관리자 주소와 충돌하면 거부한다. 생성 후에만 로그인·가입 화면에 안내가 나타난다. 계정 보호와 검증 범위는 [공용 데모 기록](../evidence/public-demo-2026-09-27.md)을 따른다.

공시 레이더는 수집을 시작한 날부터의 공시만 가진다. 종목 조회의 "최근 30일"이 비어 보이지 않게, 새 서버에서는 최근 30일 영업일을 한 번 채운다(같은 공시는 다시 넣지 않는다).

```bash
sudo docker exec stockdesk-worker-1 python -c "
from datetime import date, timedelta
from dart_radar import collect
d = date.today() - timedelta(days=30)
while d < date.today():
    if d.weekday() < 5:
        print(collect(full=True, day=d), flush=True)
    d += timedelta(days=1)
"
```

- 2026-09-27 실측: 영업일 17일, 6,721건을 채웠다. DART 호출은 119회였다. 판정 모델 판정은 535회(규칙으로 못 가른 약 8%)였다.
- 판정 모델 비용은 명령 바와 같은 월 예산 원장에서 빠진다.

## 6. DB 백업과 복구 확인

`scripts/ec2/`의 두 스크립트는 릴리스 묶음에 함께 실려 호스트의 `/opt/stockdesk/releases/<sha>/scripts/ec2/`에 있다. SSM Run Command나 Session Manager에서 root로 실행한다.

```bash
export AWS_REGION=ap-northeast-2
# 두 DB를 덤프하고 덤프 전후 행 수(counts.tsv)를 기록한다. 모두 성공해야 s3://<ReleaseBucket>/backups/<UTC 시각>/에 올린다(21일 뒤 만료, 이전 버전은 7일 뒤 삭제: 약 30일째에 삭제 예정. S3 삭제는 비동기라 하루 이틀 늦을 수 있다. 복구 스크립트는 현재 버전만 쓰므로 복구 가능 기간은 약 21일)
bash scripts/ec2/backup-db.sh <ReleaseBucket>
# 임시 컨테이너(같은 이미지)에 복구하고 테이블별 행 수를 백업의 counts.tsv와 대조한다(덤프 중 안 바뀐 테이블은 정확히 일치)
bash scripts/ec2/restore-check.sh s3://<ReleaseBucket>/backups/<UTC 시각>
```

- 호스트 역할은 `backups/*`의 객체 읽기·쓰기만 가능하고 버킷 목록은 볼 수 없다. 그래서 복구 확인은 파일 이름으로 하나씩 받는다.
- `counts.tsv`는 맨 마지막에 올라간다. 이 파일이 없는 백업은 업로드가 중간에 끊긴 것이므로 쓰지 않는다.
- 복구 확인용 임시 컨테이너와 볼륨(운영 DB 사본)은 끝나면 지운다. 남았는지 보려면 `docker volume ls -qf dangling=true`.
- 실제로 되살릴 때는 서비스를 멈춘 뒤 같은 덤프를 `mariadb`/`pg_restore --clean`으로 운영 컨테이너에 넣는다. 리허설 기록: [정비 2026-09-26](../evidence/maintenance-2026-09-26.md).
- 정기 실행: `deploy.sh`가 설치하는 systemd 타이머 `stockdesk-backup.timer`가 매일 19:30 UTC(04:30 KST)에 돈다. 스크립트는 `/opt/stockdesk/bin`에 복사돼 있어 옛 릴리스 폴더에 의존하지 않는다.

## 7. 가동·백업 감시 (AWS)

- 스택의 `MonitorFunction`(Lambda)이 5분마다 공개 주소 세 곳(`/health`, `/api/disclosures`, `/privacy.html`)을 부르고, 가장 최근 백업(`backups/*/counts.tsv`)의 나이를 CloudWatch 지표 `Stockdesk/SiteUp`·`BackupAgeHours`로 남긴다.
- 경보 두 개가 `BudgetEmail`로 메일을 보낸다(경보·복구 때 한 번씩).
  - `SiteDownAlarm`: 연속된 10분 두 구간에 각각 실패한 확인이 한 번 이상 있을 때
  - `BackupStaleAlarm`: 백업이 27시간 넘게 없음
  - 감시 자체가 멈춰 지표가 없어도 경보가 된다.
- 처음 만든 뒤 `BudgetEmail`로 온 "AWS Notification - Subscription Confirmation" 메일의 링크를 48시간 안에 눌러야 한다. 놓치면 `aws sns subscribe --topic-arn <AlertTopic> --protocol email --notification-endpoint <메일>`로 다시 보낸다.
- 시험
  - `aws lambda invoke --cli-binary-format raw-in-base64-out --function-name <MonitorFunction> --payload '{}' out.json`
  - 실패 경로는 같은 명령에 `--payload '{"site":"example.com"}'`(지표를 쓰지 않는다)로 본다.
  - 메일은 `aws cloudwatch set-alarm-state --alarm-name <이름> --state-value ALARM --state-reason test`로 확인한다.
- 비용: Lambda·규칙·지표 2개·경보 2개·SNS 메일은 무료 한도 안이고, S3 목록 조회만 월 약 $0.04다.
- GitHub `Uptime` 워크플로는 수동 점검용이다. 이 저장소는 포크라 GitHub 예약 실행이 돌지 않는다.

## 되돌리기

- **자동**: `deploy.sh`는 새 릴리스의 `/health`가 150초 안에 통과하지 않으면 직전 릴리스를 다시 올린다. 정상 배포가 끝나면 쓰지 않는 이미지를 지우지만, 지금 도는 릴리스의 이미지는 남으므로 다음 배포의 자동 롤백 대상은 그대로다.
- **수동(더 옛 릴리스로)**: 같은 커밋 SHA로 Deploy 워크플로를 다시 돌리면 안 된다. 이미지를 다시 빌드해 같은 태그로 올리는데, ECR 태그는 변경 불가(IMMUTABLE)라 push가 실패한다. 대신 호스트에 남아 있는 옛 릴리스 폴더의 `deploy.sh`를 SSM(root)으로 실행한다. 이미지는 ECR에 저장소마다 20개씩 남아 있어 compose가 다시 받는다.

  ```bash
  old=<되돌릴 커밋 SHA>
  AWS_REGION=ap-northeast-2 ECR_REGISTRY=<계정>.dkr.ecr.ap-northeast-2.amazonaws.com LOG_GROUP=<LogGroup> \
    SITE_ADDRESS=<주소> BACKUP_BUCKET=<ReleaseBucket> \
    bash /opt/stockdesk/releases/$old/scripts/ec2/deploy.sh /opt/stockdesk/releases/$old $old
  ```

  - 호스트를 새로 만들어 폴더가 없으면, 워크플로처럼 `s3://<ReleaseBucket>/releases/$old.tgz`(90일 보관)를 받아 풀고 실행한다.
- **스택 삭제 시**: 데이터 볼륨은 스냅샷으로, 로그 그룹과 S3 버킷은 그대로 남는다.
