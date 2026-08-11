# Completion Verifier — Project Handoff

작성일: 2026-08-11
상태: command/file 수직 프로토타입, Codex 실행 주장 훅, ProofGate 플러그인 프로토타입 구현 완료

## 1. 목표

Completion Verifier는 AI 코딩 에이전트의 완료 주장을 검증 가능한 증거와 대조하는 오픈소스 CLI다.

핵심 문장:

> 에이전트가 완료라고 주장했지만 증거가 없으면 CLI와 CI에서 거절한다.

Completion Verifier는 테스트 러너나 멀티에이전트 오케스트레이터가 아니다. 사용자가 정의한 완료 조건과 실제 관찰 증거 사이를 판정하는 verification gate다.

## 2. 문제 근거

기존 세션 분석 스냅샷:

- 분석 세션: 2,965개
- 도구 사용 세션: 2,324개
- 사용자 정정·반박 감지 세션: 269개
- 추출·컨텍스트 한계 감지 세션: 227개
- Claude 직접 검증 언급: 7.3%
- Codex 직접 검증 언급: 8.1%
- 실행 기록은 있으나 검증이 명시되지 않은 세션: 약 2,088개

반복된 실패 유형:

- 이전 캐시나 기존 파일을 새 결과로 오인
- 외부 작업의 PID나 `running` 상태만 보고 성공으로 판단
- worker가 실제 상태를 바꾸지 않았는데 완료 처리
- 파일 생성 여부를 실제 서비스 성공으로 확대 해석
- 테스트 성공을 사용자 목표 달성과 동일시
- 브라우저·앱·외부 서비스의 최종 상태를 확인하지 않고 완료 주장
- 검증되지 않은 항목을 명시하지 않아 다음 세션이 같은 확인을 반복

## 3. Seer에서 얻은 설계 패턴

참고 사례: `w00ing/seer-skill`

Seer는 코딩 에이전트가 macOS UI를 수정한 뒤 실제 화면을 보지 못하는 공백을 캡처, baseline, diff, JSON 결과로 해결한다.

Completion Verifier가 가져올 원칙:

- 좁고 반복적인 에이전트 실패를 한 문장으로 설명한다.
- 사람이 아니라 에이전트도 읽을 수 있는 결정적 출력 계약을 제공한다.
- 실행 성공과 목표 성공을 분리한다.
- 증거가 없으면 자동 승인하지 않는다.
- 로컬 우선이며 결과와 보고서를 재현 가능하게 남긴다.
- 사람의 승인 경계를 명시한다.

## 4. 판정 모델

- `PASS`: 모든 필수 완료 조건이 신선한 증거로 직접 확인됨
- `FAIL`: 검증을 실행했고 하나 이상의 필수 조건이 실패함
- `UNPROVEN`: 필수 검증이 실행되지 않았거나 증거가 부족·오래됨
- `BLOCKED`: 권한, 인증, 외부 의존성 또는 환경 문제로 검증할 수 없음

`FAIL`과 `UNPROVEN`을 엄격히 분리하는 것이 핵심 차별점이다.

예시 출력:

```text
release-ready: UNPROVEN

✓ tests      PASS       pytest: 84 passed
✓ artifact   PASS       dist/app.tar.gz, 2.1 MB
? service    UNPROVEN   HTTP verification was not run

Agent completion claim rejected: 1 claim remains unproven.
```

## 5. v0.1 범위

포함:

- `completion-verifier.yml` 및 JSON Schema
- `file`, `command`, `git`, `http` verifier
- `PASS/FAIL/UNPROVEN/BLOCKED`
- JSON·Markdown receipt
- 비밀정보 형태 기본 redaction
- `--strict` CI 종료 코드
- GitHub Actions 예제
- Claude Code·Codex·Hermes용 최소 통합 문서
- Python·Node·서비스·생성 파일 예제
- verifier 단위 테스트

제외:

- LLM-as-judge
- 자동 수정과 자동 재시도
- 대시보드
- 외부 배포 직접 실행
- 결제·게시·삭제 승인 시스템
- 완전한 UI 의미 검증
- 멀티에이전트 오케스트레이터

## 6. 첫 번째 수직 흐름

다음 흐름은 2026-08-11에 구현하고 직접 검증했다.

1. `completion-verifier.yml`에 완료 조건 정의
2. `command`와 `file` verifier 실행
3. 증거가 없는 조건을 `UNPROVEN`으로 판정
4. JSON 및 Markdown receipt 생성
5. `--strict`가 CI를 실패시킴

초기 CLI 예시:

```text
completion-verifier init
completion-verifier run
completion-verifier report
completion-verifier run --strict
```

## 7. Receipt 최소 필드

- 검증 실행 시각
- 증거 생성 시각
- 검증 대상 Git commit
- 실행 디렉터리
- 검증 명령과 종료 코드
- 결과 파일 크기·수정 시각·해시
- HTTP 상태와 확인 시각
- verifier별 판정과 설명
- 전체 판정
- redaction 적용 여부

증거의 신선도를 판단할 수 있어야 캐시와 과거 산출물을 새 결과로 오인하지 않는다.

## 8. 제안 저장소 구조

```text
completion-verifier/
├── README.md
├── LICENSE
├── pyproject.toml
├── src/completion_verifier/
│   ├── cli.py
│   ├── schema.py
│   ├── contract.py
│   ├── verdict.py
│   ├── redaction.py
│   ├── receipt.py
│   └── verifiers/
│       ├── command.py
│       ├── file.py
│       ├── git.py
│       ├── http.py
│       └── custom.py
├── schemas/
│   └── completion-verifier.schema.json
├── integrations/
│   ├── claude-code/
│   ├── codex/
│   ├── hermes/
│   └── github-actions/
├── examples/
├── tests/
└── docs/
```

이 구조는 방향이며 현재는 최소 수직 흐름에 필요한 파일만 생성했다. `git`, `http`, `custom`, integrations는 아직 없다.

## 9. OpenAI Codex for Open Source 연결

공식 프로그램은 활성 공개 저장소, 의미 있는 사용·확산 또는 생태계 중요성, 지속적인 유지관리 증거를 본다. Completion Verifier는 다음 서사를 가진다.

- 수천 개의 실제 AI 작업 세션에서 반복된 검증 공백을 근거로 시작했다.
- Codex를 포함한 여러 코딩 에이전트의 유지관리 워크플로에 직접 사용된다.
- PR 검토, CI, 릴리스 검증과 연결할 수 있다.
- 완료 주장과 증거를 분리해 오픈소스 코드 품질과 유지관리 신뢰도를 높인다.

지원 자체보다 먼저 실제 공개 사용 신호를 만든다.

- 공개 MIT 저장소
- 재현 가능한 예제와 데모
- 최소 1개 GitHub Release
- CI와 테스트
- 실제 프로젝트 적용 사례
- 외부 이슈·PR을 받을 수 있는 기여 문서
- 지속적인 릴리스·유지관리 기록

## 10. 현재 구현과 다음 작업

완료:

1. 경쟁·중복 조사와 명칭 충돌 확인
2. `completion-verifier.yml` command/file 최소 계약 및 JSON Schema
3. `init`, `run`, `report`, `run --strict` CLI
4. command/file verifier와 네 상태 판정 우선순위
5. 실행 전후 Git 상태, 명령·출력 해시, 파일 크기·mtime·해시 receipt
6. 기본 secret-shape redaction과 owner-only 원자적 JSON/Markdown receipt
7. 단위·통합 테스트 및 설치된 CLI로 네 상태 실제 검증
8. YAML 없이 켜는 Codex `PostToolUse`/`Stop` 훅 통합
9. 같은 턴의 명령 증거와 완료 답변을 대조하는 구조화된 `codex exec` 판정
10. 프로젝트별 enable/disable, 전역 훅 안전 병합·제거, 재귀·반복 차단
11. `proofgate` Codex 플러그인 manifest와 활성화·상태·비활성화 skill
12. pip 없이 동작하는 owner-only 번들 런타임 설치와 전 프로젝트 훅 모드
13. 플러그인 설치 경로가 바뀌어도 유지되는 안정 runtime 경로와 정확한 handler 제거

다음 작업:

1. 개인 또는 공개 marketplace entry를 만들고 실제 `codex plugin add` 설치 흐름을 검증한다.
2. 실제 Codex OAuth 세션에서 훅을 dogfood해 `tool_response` 변형과 오탐·누락을 수집한다.
3. 실제 외부 프로젝트 한 곳에 strict 계약도 dogfood하고 사용성을 검증한다.
4. 훅 claim receipt 및 기존 receipt용 별도 JSON Schema를 고정한다.
5. `git`과 `http` verifier 계약을 설계하고 구현한다.
6. GitHub Actions 예제와 strict required-check 흐름을 검증한다.
7. Python 3.10–3.14 및 macOS/Linux 호환성 행렬을 CI에서 확인한다.
8. 공개 전 최종 제품명과 PyPI/npm/GitHub 가용성을 다시 조사한다.

## 11. 아직 확정하지 않은 것

- 공개 패키지명과 PyPI 사용 가능 여부 (`completion-verifier`는 작업명)
- command/file 이외 verifier의 YAML 상세 문법
- 현재 run 이외의 maximum-age freshness 정책
- custom verifier 플러그인 규격
- receipt 서명 또는 변조 방지 기능
- GitHub App 여부

현재 구현은 Python 3.10 이상, 셸 없는 argv command, 명시적인 file freshness를 계약으로 고정했다. 나머지는 조사·검증 전 확정하지 않는다.
