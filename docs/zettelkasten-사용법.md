# 제텔카스텐(독일식 메모법) 사용법

`narratological` 시스템에 추가된 **제텔카스텐(Zettelkasten)** 메모 기능 안내서입니다.
제텔카스텐은 독일 사회학자 니클라스 루만(Niklas Luhmann)이 사용한 메모법으로,
**원자적 메모(하나의 메모 = 하나의 생각)** 들을 **고유 ID** 로 식별하고
서로 **연결(링크)** 하여 지식의 그물망을 만드는 방법입니다.

## 핵심 원칙

| 원칙 | 설명 |
|------|------|
| **원자성(Atomicity)** | 하나의 메모에는 하나의 생각만 담습니다. |
| **고유 ID** | 모든 메모는 충돌 없는 타임스탬프 기반 ID(`20260618T123000`)를 가집니다. |
| **연결(Linking)** | 메모끼리 단방향 링크로 연결하며, 역링크(backlinks)는 자동 계산됩니다. |
| **태그(Tags)** | 주제별로 메모를 묶습니다. |

## 노트 유형 (Note Types)

루만 방식의 세 가지 메모 유형을 지원합니다.

| 유형 | 값 | 설명 | 사용 시점 |
|------|-----|------|-----------|
| 영구노트 | `permanent` | 자신의 언어로 완결된 핵심 아이디어 | 생각을 영구 보관할 때 |
| 문헌노트 | `literature` | 자료를 읽으며 정리한 메모 | 책·논문을 읽을 때 |
| 임시노트 | `fleeting` | 빠르게 적는 일시적 메모(기본값) | 떠오른 생각을 즉시 포착할 때 |

## 내러티브 연결 (Study 연결)

각 메모는 `study_ref` 필드로 기존 내러티브 연구(study)나 공리(axiom)에 연결할 수 있습니다.
이를 통해 개인 메모 그물망이 시스템의 공식 지식 베이스와 이어집니다.

- 형식: `study_id` 또는 `study_id/axiom_id`
- 예: `aristotle` 또는 `aristotle/A0`

`show` 명령이나 `/notes/{id}/study-ref` 엔드포인트는 이 참조를 실제 연구·공리 요약으로
풀어서 보여줍니다.

## 저장 위치

메모는 단일 JSON 파일에 저장됩니다. 위치는 다음 순서로 결정됩니다.

1. 환경변수 `NARRATOLOGICAL_NOTES` (설정된 경우)
2. 기본 경로 `~/.narratological/zettelkasten.json` (자동 생성)

```bash
# 메모 저장 위치를 직접 지정하려면:
export NARRATOLOGICAL_NOTES="$HOME/my-notes/zk.json"
```

## CLI 사용법

```bash
# 1. 영구노트 작성 (study/axiom 연결 포함)
narratological note new \
  --title "미메시스는 선택적이다" \
  -b "예술은 본질을 모방한다." \
  --type permanent \
  -t 미학 \
  --study-ref aristotle/A0

# 2. 문헌노트 작성
narratological note new \
  --title "카타르시스는 사전 설정이 필요하다" \
  -b "감정 해방에는 긴장 축적이 선행된다." \
  --type literature \
  -t 감정

# 3. 메모 목록 (유형/태그 필터)
narratological note list
narratological note list --type permanent
narratological note list --tag 미학

# 4. 두 메모 연결 (관계 유형 지정 가능)
narratological note link <id1> <id2> --type elaborates --context "구체화"

# 5. 메모 상세 보기 (링크·역링크·study 연결 요약 표시)
narratological note show <id1>

# 6. 역링크 조회
narratological note backlinks <id2>

# 7. 검색 (제목·본문·태그)
narratological note search 카타르시스

# 8. 그래프 보기 (노드/엣지 수, 링크 트리, 고립 메모)
narratological note graph

# 9. 메모 삭제 (이 메모를 가리키던 링크도 함께 정리)
narratological note delete <id>
```

### 링크 관계 유형 (`--type`)

`reference`(기본), `follows`, `supports`, `contradicts`, `elaborates`

## API 사용법

API 서버 실행: `uv run uvicorn narratological_api.main:app --reload`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/notes/` | 메모 목록 (`?tag=`, `?note_type=` 필터) |
| `POST` | `/notes/` | 메모 생성 |
| `GET` | `/notes/{id}` | 메모 단건 조회 |
| `PUT` | `/notes/{id}` | 메모 수정(제공된 필드만 변경) |
| `DELETE` | `/notes/{id}` | 메모 삭제 |
| `POST` | `/notes/{id}/links` | 링크 추가 |
| `DELETE` | `/notes/{id}/links/{target_id}` | 링크 제거 |
| `GET` | `/notes/{id}/backlinks` | 역링크 조회 |
| `GET` | `/notes/{id}/study-ref` | 내러티브 연결(study/axiom) 풀어 보기 |
| `GET` | `/notes/search?q=` | 검색 |
| `GET` | `/notes/graph` | 노드/엣지 그래프 + 고립 메모 |
| `GET` | `/notes/tags` | 전체 태그 목록 |

```bash
# 메모 생성 예시
curl -X POST localhost:8000/notes/ \
  -H "Content-Type: application/json" \
  -d '{"title":"미메시스는 선택적이다","body":"예술은 본질을 모방한다.","note_type":"permanent","tags":["미학"],"study_ref":"aristotle/A0"}'
```

대화형 문서는 서버 실행 후 `/docs`(Swagger UI)에서 확인할 수 있습니다.

## 권장 워크플로

1. 떠오른 생각은 **임시노트**로 빠르게 포착합니다.
2. 자료를 읽으며 **문헌노트**를 남깁니다.
3. 정리된 핵심 아이디어는 자신의 언어로 **영구노트**로 옮기고, 관련 메모와 **링크**합니다.
4. 내러티브 이론과 닿아 있는 메모는 `--study-ref`로 **연결**해 지식 베이스와 통합합니다.
5. `graph`로 전체 연결 상태를 점검하고, **고립 메모**를 다른 메모와 이어 줍니다.
