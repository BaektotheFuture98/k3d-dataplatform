# k3d/K3s Study Curriculum Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** k3d/K3s를 우선 학습하는 24장 한국어 교재와 설정 참고 자료를 제공한다.

**Architecture:** 주 학습 경로는 `docs/study/chapters/`에 배치한다. 기존 도구별 문서는
참고 자료로 유지하고 새 목차로 연결한다. 일반 원리와 과거 실행 기록을 구분한다.

**Tech Stack:** Markdown, Mermaid, shell/Python 설명용 코드, 오프라인 검증.

**Spec:** `docs/superpowers/specs/2026-11-14-study-curriculum-design.md`

## Global Constraints

- 문서만 수정한다. 클러스터 변경, 업무 DAG 실행, Secret 출력, 배포·push는 하지 않는다.
- 기존 미커밋 파일을 보존한다.
- 본문 실습은 조회 중심이고, DAG 실행은 별도 선택 실습으로 표시한다.
- 각 장: 필요성 → 동작 원리 → 프로젝트 파일 → 조회 실습/예상 결과 → 확인 문제/해설.

## Review Focus

- K3s 기본값을 현재 환경에서 확인한 사실로 오해하지 않는가.
- Kubernetes/Airflow API server·scheduler 및 두 상태 저장소를 구분하는가.
- 명령어가 상태를 변경하면 별도로 표시하고 예시 출력을 관측 결과로 오해하지 않는가.
- local-path/PVC를 백업이나 노드 장애 복구로 설명하지 않는가.
- 기존 참고 문서에서 시작해도 새로운 순서와 확인 기준일을 찾을 수 있는가.

### Task 1: 본문 및 진입점

**Files:** `docs/study/README.md`, `docs/study/chapters/01-*.md`–`24-*.md`.

- [x] 1–6장: 노드 컨테이너, 제어 평면, 런타임의 경계를 설명한다.
- [x] 7–17장: 실행·네트워크·저장소·권한·운영을 현재 manifest와 연결한다.
- [x] 18–24장: 두 태스크 DAG와 플랫폼 전체 경로로 개념을 확인한다.
- [x] 전체 목차, 장 사이 이동, 구간별 이해 확인 기준을 작성한다.

### Task 2: 기존 자료 연결

**Files:** `docs/study/*/*.md` 중 기존 도구별 자료.

- [x] 참고 자료임을 표시하고 관련 본문 장으로 연결한다.
- [x] 작성 당시 상태와 새 검증 여부를 구분하고 일회성 PR 표현을 정리한다.

### Task 3: 검증과 검토

- [x] 모든 로컬 링크와 24장 목차·필수 구성·장 사이 이동을 확인한다.
- [x] shell 블록을 `zsh -n`, Python 블록을 `ast.parse`로 검증한다. 코드는 실행하지 않는다.
- [x] 공식 문서와 manifest를 대조하고 읽기/변경 실습 구분을 검토한다.
- [x] 별도 검토 후 필요한 수정을 반영하고 최종 검증 결과를 보고한다.

## 실행 기록

사용자의 “진행해”에 따라 같은 세션에서 작성한다. 변경 전부터 `docs/`와 배포 관련
파일에 미커밋 작업이 있어 현재 작업 디렉터리에서 문서만 편집한다. 별도 checkout,
커밋, 테스트용 배포는 하지 않는다. 코드 변경이 없어 제품 테스트를 추가하지 않는다.


## 완료 및 검증 기록

- 24장 본문(6부), 전체 목차, 장 사이 이동, 구간별 통과 기준을 작성했다.
- 기존 도구별 문서 22개를 설정 참고 자료로 연결하고 과거 관측임을 표시했다.
- 오프라인 검사: Markdown 47개, 로컬 링크 228개, shell 61개·Python 6개·YAML 4개
  코드 블록의 문법과 장별 필수 구성을 확인했다. Mermaid 5개는 개수·코드 경계만
  확인했고 실제 렌더링 검증은 하지 않았다.
- 독립 검토에서 발견한 19장 업로드 조건 분기를 수정했다. 모의 kubectl로
  정상 확인·기존 파일 존재·Pod 조회 실패 세 경로의 복사 실행 여부를 검증했다.
- 기존 참고 자료의 `<POD_NAME>` 셸 문법 문제를 실제 이름 변수 예시로 수정했다.
- `git diff --check` 통과. 신규 문서는 별도로 링크·문법을 검사했다.
- Airflow를 import한 DAG 실행이나 live 클러스터 검증은 하지 않았다.
- 검토 결과와 수정은 문서에만 반영했으며 배포 설정과 기존 미커밋 작업을 보존했다.

- 게시 전 확인: 원격 저장소에 없는 로컬 파일 링크 6개를 명시적 경로로 바꾸고,
  학습 자료가 없는 GitHub 사본에서도 이 차이를 알 수 있도록 안내했다.
