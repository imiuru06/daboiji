"""Operator-facing guide + activity log for the Studio dashboard.

The dashboard answers four things a human operator asks while Claude Code
drives the pipeline:

  1. ACTIONS   — what the MCP/pipeline can actually do (high level)
  2. activity  — what was done in this work session: a timeline with
                 before -> after for each step
  3. PROMPTS   — prompt recipes, especially for *linking multiple media* into
                 one coherent video
  4. capabilities — the low-level primitives (elements/effects/transitions)

ACTIONS and PROMPTS are curated knowledge; the activity log is appended to as
operations run (via the ``log_activity`` MCP tool or ``POST /api/activity``)
and stored next to the projects in the shared store, so the browser dashboard
reflects exactly what the agent did.
"""
from __future__ import annotations

import json
import os
import time

# --------------------------------------------------------------------------
# 1. What the pipeline can do (high level)
# --------------------------------------------------------------------------
HIGH_LEVEL_ACTIONS = [
    {"action": "generate",
     "summary": "프롬프트로 영상 생성(t2v) / 이미지로 애니메이션(i2v)",
     "tools": ["generate_video", "list_video_providers"],
     "compute": "외부 GPU (Veo 웹앱 / Colab)"},
    {"action": "dewatermark",
     "summary": "정적 워터마크(Gemini ✦, shutterstock 등) 프레임별 제거 + 오디오 보존",
     "tools": ["remove_watermark", "lama_health"],
     "compute": "외부 GPU (Colab LaMa 서버)"},
    {"action": "compose / edit",
     "summary": "타임라인에 텍스트·효과·카메라·전환·오디오를 합성",
     "tools": ["create_project", "add_text", "add_media", "add_effect",
               "set_camera", "add_audio", "update_clip", "list_clips"],
     "compute": "낮음 (VM에서 가능)"},
    {"action": "render / preview",
     "summary": "타임라인 → MP4 인코딩, 또는 1프레임 미리보기",
     "tools": ["render_project", "render_range", "preview_frame"],
     "compute": "CPU (AI 세션 샌드박스 권장)"},
    {"action": "deliver",
     "summary": "결과 전달: 채팅 첨부 / git push / Studio 갤러리",
     "tools": ["SendUserFile", "POST /api/projects/{id}/media"],
     "compute": "낮음"},
]

# --------------------------------------------------------------------------
# 3. Prompt cookbook — focus on linking multiple media into one video
# --------------------------------------------------------------------------
PROMPT_COOKBOOK = [
    {"title": "단일 시네마틱 샷 (t2v 기본)",
     "formula": "[피사체] + [동작] + [카메라/렌즈] + [조명/시간대] + [무드] + [품질]",
     "example": ("glossy red sports car drifting on a wet city street at night, "
                 "low tracking shot, neon reflections, anamorphic lens flare, "
                 "cinematic, photorealistic, 4K"),
     "tips": ["8초·16:9 권장", "오디오 필요하면 Veo 3 계열"]},

    {"title": "여러 클립을 잇는 시퀀스 (연속성) ★",
     "why": "여러 미디어를 한 영상으로 연결할 때 컷이 튀지 않게 — 핵심",
     "rules": [
         "같은 피사체·색감·조명 토큰을 모든 클립에 고정 "
         "(예: 'the SAME red sports car, golden hour, teal-orange grade')",
         "각 클립을 '중립 프레임'으로 시작·끝내기 → 크로스페이드가 자연스러움",
         "카메라 이동 방향 잇기 (A가 좌→우로 끝나면 B도 좌→우로 시작)",
         "i2v 체이닝: A의 마지막 프레임을 추출 → B의 시작 이미지로 사용",
     ],
     "example_set": [
         "1) establishing — red sports car parked on a coastal overlook, golden "
         "hour, wide aerial, slow push-in",
         "2) action — the SAME red sports car driving toward camera on the same "
         "coastal road, golden hour, low tracking shot",
         "3) detail — close-up of the SAME car's front wheel on wet asphalt, "
         "golden hour, shallow depth of field",
     ]},

    {"title": "합성용 B-roll / 배경 (텍스트·로고 아래 깔기)",
     "rules": [
         "여백(negative space)을 비워 달라고 요청 → 그 위에 타이틀 얹기",
         "느리고 루프 가능한 모션 → 길이 늘이기·반복이 쉬움",
         "단색/그라데이션 배경 → 키잉·블렌드가 쉬움",
     ],
     "example": ("slow drifting clouds over a deep blue gradient sky, lots of "
                 "empty space on the left for text, seamless loop, soft "
                 "cinematic lighting")},

    {"title": "전환(트랜지션) 친화 클립",
     "rules": [
         "시작/끝을 어둡게(페이드) 또는 같은 구도로 → 컷 연결이 매끄러움",
         "휩 팬으로 끝내고 다음 클립을 휩 팬으로 시작 → 자연스러운 휩 전환",
     ],
     "example": "... ending with a fast whip-pan to the right into motion blur"},

    {"title": "편집 지시 (나에게 자연어로)",
     "example": ("이 3개 클립을 순서대로 이어서, 첫 2.5초에 타이틀 'SUNSET DRIVE', "
                 "크로스페이드 0.5초, 따뜻한 색감, 끝에 로고, 총 10초로 만들어줘")},
]


# --------------------------------------------------------------------------
# 2. Activity log (timeline with before -> after), stored in the shared store
# --------------------------------------------------------------------------
def _store_root() -> str:
    from ..service import STORE
    return getattr(STORE, "root", ".")


def _activity_path() -> str:
    return os.path.join(_store_root(), "_activity.json")


def read_activity() -> list:
    p = _activity_path()
    if os.path.isfile(p):
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except Exception:  # noqa: BLE001
            return []
    return []


def append_activity(event: dict) -> dict:
    event = dict(event)
    event.setdefault("time", time.strftime("%Y-%m-%d %H:%M:%S"))
    events = read_activity()
    events.append(event)
    p = _activity_path()
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=1)
    return event


# Shown (clearly labelled) when the real log is empty, so the timeline panel
# demonstrates the before -> after format.
SAMPLE_ACTIVITY = [
    {"time": "예시", "action": "generate", "summary": "Veo로 해안도로 스포츠카 생성",
     "inputs": ["prompt: red sports car, coastal highway, sunset"],
     "outputs": ["veo_src.mp4 (1280x720, 10s, audio)"], "sample": True},
    {"time": "예시", "action": "dewatermark", "summary": "우하단 ✦ 워터마크 LaMa 제거",
     "inputs": ["veo_src.mp4", "region [1132,568,60,62]"],
     "outputs": ["veo_clean.mp4"], "sample": True},
    {"time": "예시", "action": "compose/render", "summary": "타이틀·그레이드·비네팅 + 오디오",
     "inputs": ["veo_clean.mp4"], "outputs": ["SUNSET_DRIVE.mp4 (2.8MB)"], "sample": True},
]


def dashboard_data() -> dict:
    from .. import capabilities as engine_capabilities
    activity = read_activity()
    return {
        "actions": HIGH_LEVEL_ACTIONS,
        "prompts": PROMPT_COOKBOOK,
        "capabilities": engine_capabilities(),
        "activity": activity if activity else SAMPLE_ACTIVITY,
        "activity_is_sample": not activity,
    }
