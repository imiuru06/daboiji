# 다봐요 — JSON 저장소 관리 체계 (Store Schema)

모든 상태는 **`DABWAYO_STORE`** 디렉터리 하나에 JSON으로 모입니다. MCP 서버(에이전트)와
Studio(사람)가 같은 곳을 보며, 렌더 결과물(바이너리)은 **`DABWAYO_OUTPUT`** 에 둡니다.

## 디렉터리 레이아웃
```
$DABWAYO_STORE/
├── <project_id>.json        # 프로젝트 spec (타임라인). service.ProjectStore 가 관리 (원자적 저장)
├── _activity.json           # 작업 타임라인 로그 (대시보드 ②). 밑줄(_) = 프로젝트 목록서 제외
└── assets/
    └── <asset_id>.json      # 에셋 레코드 (미디어 + 출처/계보). assets.py 가 관리

$DABWAYO_OUTPUT/              # 렌더/프리뷰 바이너리 (mp4, png) — Studio가 /files/ 로 서빙
```
> 규칙: **밑줄 `_`로 시작하는 파일은 "메타"** 로 취급되어 프로젝트 목록에서 빠집니다.
> `index`는 파일이 아니라 `assets.build_index()` 로 **그때그때 생성**되는 매니페스트입니다.

## 식별자(ID) 규칙
| 종류 | 형식 | 예 |
|---|---|---|
| 프로젝트 | hex 12자 | `cd6a35962a5f` |
| 에셋 | `ast_` + hex 10자 | `ast_ab12cd34ef` |

---

## 스키마

### 1) 프로젝트 (`<project_id>.json`)
```jsonc
{
  "name": "SUNSET DRIVE",
  "width": 1280, "height": 720, "fps": 24,
  "background": "#05070d",
  "duration": 10.0,                  // 선택
  "tracks": [ { "kind": "video", "name": "...", "clips": [ /* 클립 spec */ ] } ],
  "effects": [ /* 마스터 효과 */ ],
  "camera": { /* pan/zoom/rotation */ }
}
```

### 2) 에셋 (`assets/<asset_id>.json`)
```jsonc
{
  "id": "ast_ab12cd34ef",
  "kind": "video",                   // video | image | audio
  "role": "raw",                     // raw|dewatermarked|edited|broll|final|upload|other
  "path": "/abs/path/clip.mp4",      // 바이너리 위치
  "source": {                        // 출처(provenance)
    "action": "generate",            // generate|dewatermark|render|compose|upload
    "provider": "veo",               // veo|lama|engine|local|...
    "prompt": "red sports car ...",
    "parent": "ast_0000000000",      // 파생 원본 → 미디어 연결 그래프
    "params": { "num_frames": 48 }
  },
  "media": { "width":1280,"height":720,"fps":24,"frames":240,"duration":10.0,"has_audio":true },
  "projects": ["cd6a35962a5f"],      // 사용 중인 프로젝트
  "tags": [],
  "created": "2026-06-23 09:10:00"
}
```
**계보(lineage):** `source.parent` 를 따라가면 한 미디어가 어떻게 만들어졌는지 추적됩니다.
```
raw(Veo t2v)  ──▶  dewatermarked(LaMa)  ──▶  edited(engine)  ──▶  final
   ast_001            ast_002 (parent=001)     ast_003(parent=002)   ast_004(parent=003)
```

### 3) 활동 로그 (`_activity.json`) — 배열
```jsonc
[
  { "time":"2026-06-23 09:10:00", "action":"generate",
    "summary":"Veo 생성", "inputs":["prompt: ..."], "outputs":["ast_001"], "notes":"" }
]
```

### 4) 매니페스트 (`assets.build_index()` / `GET /api/index`) — 동적 생성
```jsonc
{
  "updated":"...", "store_root":"...",
  "counts": { "projects": 2, "assets": 5 },
  "projects": [ { "id","name","resolution","fps","tracks" } ],
  "assets":   [ { "id","kind","role","duration","parent","provider","projects","created" } ]
}
```

---

## 접근 방법
| 작업 | MCP 툴 | Studio REST |
|---|---|---|
| 프로젝트 CRUD | `create_project`, `get_project`, `update_project` | `/api/projects...` |
| 에셋 등록/조회 | `register_asset`, `list_assets`, `get_asset` | `/api/assets`, `/api/assets/{id}` |
| 매니페스트 | `store_index` | `/api/index` |
| 활동 로그 | `log_activity`, `studio_status` | `/api/activity`, `/api/dashboard` |

`generate_video` / `remove_watermark` 는 결과를 **자동으로 에셋 등록**하고 부모(parent)를 연결합니다.

## 불변식 (Invariants)
- 쓰기는 **원자적**(`*.tmp` → `os.replace`).
- 프로젝트 목록은 `_*` 파일을 제외.
- 바이너리는 `DABWAYO_OUTPUT`, 메타는 `DABWAYO_STORE` — 분리.
- 에셋은 자기 출처를 항상 `source` 에 보관(재현·추적 가능).
