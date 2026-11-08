# Backlog

Hermes Fleet(상위 폴더 하네스)이 처리하는 작업 티켓입니다. 파일 하나가 티켓 하나이며 YAML frontmatter + 마크다운 본문 형식입니다.

- 상태 전이: proposed →(사람 `hermes-fleet approve <repo> <ID>`)→ todo →(데몬)→ in-progress →(QA PASS)→ review →(일일 자동 머지)→ done
- QA FAIL 또는 오류 시 blocked (사람이 티켓을 고쳐 todo로 되돌림)
- 산출물: hermes/workspace/<ID>/ (prd.md, design.md, dev-report.md, qa-report.md, summary.md)
