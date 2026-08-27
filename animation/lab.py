import base64
import html
import json
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import streamlit as st

from animation.staff_specs import build_staff_lab_specs


EMPLOYEE_ASSETS = {
    "유키": "project_manager",
    "희정": "employee_258c2afdab634c0482e657eddaeddeca",
    "레오": "employee_6b1b55c815ab4954b4ee8f677485ce17",
    "마츠리": "employee_037752c7b73248eb9a92e42924cfa81c",
    "레비": "employee_9369af7654824819a7f462d39bd60d0b",
    "미코": "employee_45548ccdc9e14ed3bbcfd99aedcb311f",
}

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SPRITE_DIRECTORY = PROJECT_ROOT / "static" / "sprites"
PROMPT_GUIDE_FILE = PROJECT_ROOT / "픽셀_캐릭터_애니메이션_제작_조건문.txt"
YUKI_PIXEL_DRAFT_FILE = (
    PROJECT_ROOT / "static" / "animation" / "yuki" / "yuki_pixel_master.png"
)
YUKI_ACTION_SPRITES = {
    "대기": {
        "path": PROJECT_ROOT / "static" / "animation" / "yuki" / "yuki_idle_4f.png",
        "fps": 2,
        "alignment": {
            "content_height": 677,
            "baseline": 762,
            "body_centers": (251.5, 239.5, 225.5, 211.5),
            "content_boxes": (
                (58, 85, 381, 677),
                (45, 85, 381, 677),
                (32, 85, 381, 677),
                (18, 85, 382, 677),
            ),
        },
    },
    "생각 중": {
        "path": PROJECT_ROOT / "static" / "animation" / "yuki" / "yuki_thinking_4f.png",
        "fps": 3,
        "alignment": {
            "content_height": 649,
            "baseline": 719,
            "body_centers": (258.5, 247.0, 240.0, 205.0),
            "content_boxes": (
                (70, 70, 373, 649),
                (61, 71, 368, 648),
                (54, 70, 368, 649),
                (18, 70, 369, 649),
            ),
        },
    },
    "작업 중": {
        "path": PROJECT_ROOT / "static" / "animation" / "yuki" / "yuki_working_4f.png",
        "fps": 4,
        "alignment": {
            "content_height": 644,
            "baseline": 676,
            "body_centers": (279.0, 265.0, 264.0, 278.0),
            "content_boxes": (
                (93, 32, 368, 644),
                (86, 32, 358, 644),
                (86, 32, 358, 644),
                (92, 32, 368, 644),
            ),
        },
    },
    "대화 중": {
        "path": PROJECT_ROOT / "static" / "animation" / "yuki" / "yuki_talking_4f.png",
        "fps": 4,
        "alignment": {
            "content_height": 662,
            "baseline": 765,
            "body_centers": (256.5, 243.5, 230.0, 218.5),
            "content_boxes": (
                (73, 104, 365, 661),
                (60, 104, 366, 661),
                (47, 104, 366, 661),
                (36, 103, 364, 662),
            ),
        },
    },
    "자료 전달": {
        "path": PROJECT_ROOT / "static" / "animation" / "yuki" / "yuki_handoff_4f.png",
        "fps": 4,
        "alignment": {
            "content_height": 683,
            "baseline": 799,
            "body_centers": (228.0, 214.0, 213.0, 197.5),
            "content_boxes": (
                (40, 116, 372, 683),
                (29, 116, 366, 683),
                (8, 116, 386, 683),
                (0, 116, 378, 683),
            ),
        },
    },
    "업무 완료": {
        "path": PROJECT_ROOT / "static" / "animation" / "yuki" / "yuki_complete_4f.png",
        "fps": 3,
        "alignment": {
            "frame_sequence": (0, 1, 1, 1),
            "loop": False,
            "content_height": 677,
            "baseline": 783,
            "body_centers": (260.3, 227.6, 199.6, 192.4),
            "content_boxes": (
                (75, 107, 369, 676),
                (42, 106, 372, 677),
                (14, 106, 373, 677),
                (4, 106, 377, 677),
            ),
        },
    },
    "오류·재작업": {
        "path": PROJECT_ROOT / "static" / "animation" / "yuki" / "yuki_rework_4f.png",
        "fps": 4,
        "alignment": {
            "content_height": 695,
            "baseline": 814,
            "body_centers": (245.1, 224.5, 195.5, 175.5),
            "content_boxes": (
                (57, 119, 361, 695),
                (38, 119, 376, 695),
                (9, 119, 378, 695),
                (0, 119, 366, 695),
            ),
        },
    },
}
BUILTIN_ACTION_SPRITES = {
    "유키": YUKI_ACTION_SPRITES,
    **build_staff_lab_specs(PROJECT_ROOT),
}

ACTION_LABELS = (
    "대기",
    "생각 중",
    "작업 중",
    "대화 중",
    "자료 전달",
    "업무 완료",
    "오류·재작업",
)


@st.cache_data(show_spinner=False)
def employee_reference_zip() -> bytes:
    """외부 제작 서비스에 전달할 현재 직원 이미지와 조건문을 묶습니다."""

    archive_buffer = BytesIO()
    with ZipFile(archive_buffer, "w", compression=ZIP_DEFLATED) as archive:
        for employee_name, asset_id in EMPLOYEE_ASSETS.items():
            image_path = SPRITE_DIRECTORY / f"{asset_id}.png"
            if image_path.exists():
                archive.writestr(
                    f"직원_기준_이미지/{employee_name}_현재_캐릭터_기준.png",
                    image_path.read_bytes(),
                )
        if PROMPT_GUIDE_FILE.exists():
            archive.writestr(
                PROMPT_GUIDE_FILE.name,
                PROMPT_GUIDE_FILE.read_bytes(),
            )
    return archive_buffer.getvalue()


def uploaded_file_data_url(uploaded_file) -> str:
    """업로드 파일을 브라우저 미리보기용 data URL로 변환합니다."""

    mime_type = uploaded_file.type or "image/png"
    encoded = base64.b64encode(uploaded_file.getvalue()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def render_preview_component(
    background_url: str,
    character_url: str,
    employee_name: str,
    action_label: str,
    animation_mode: str,
    frame_count: int,
    fps: int,
    scale: int,
    position_x: int,
    position_y: int,
    mirror_character: bool,
    background_brightness: int,
    frame_alignment: dict | None = None,
) -> None:
    """이미지 또는 스프라이트 시트를 독립된 브라우저 캔버스에서 재생합니다."""

    preview_data = {
        "background": background_url,
        "character": character_url,
        "employee": employee_name,
        "action": action_label,
        "mode": animation_mode,
        "frames": frame_count,
        "fps": fps,
        "scale": scale / 100,
        "x": position_x / 100,
        "y": position_y / 100,
        "mirror": mirror_character,
        "brightness": background_brightness / 100,
        "frame_alignment": frame_alignment,
        # YOUFFICE의 모든 기본 행동은 미리보기에서도 계속 반복합니다.
        # 특히 자료 전달·업무 완료가 마지막 프레임에서 멈추지 않게 합니다.
        "loop": True,
    }
    payload = json.dumps(preview_data, ensure_ascii=False).replace("</", "<\\/")

    component_html = f"""
    <!doctype html>
    <html lang="ko">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <style>
            * {{ box-sizing: border-box; }}
            html, body {{
                width: 100%;
                height: 100%;
                margin: 0;
                overflow: hidden;
                background: #090c13;
                color: #f6f7fb;
                font-family: Pretendard, "Noto Sans KR", sans-serif;
            }}
            .stage {{
                position: relative;
                width: 100%;
                aspect-ratio: 16 / 9;
                overflow: hidden;
                border: 1px solid rgba(139, 152, 255, 0.38);
                border-radius: 18px;
                background:
                    linear-gradient(45deg, #121722 25%, transparent 25%),
                    linear-gradient(-45deg, #121722 25%, transparent 25%),
                    linear-gradient(45deg, transparent 75%, #121722 75%),
                    linear-gradient(-45deg, transparent 75%, #121722 75%),
                    #0e121b;
                background-position: 0 0, 0 10px, 10px -10px, -10px 0;
                background-size: 20px 20px;
                box-shadow: inset 0 0 50px rgba(0,0,0,.36);
            }}
            #background {{
                position: absolute;
                inset: 0;
                width: 100%;
                height: 100%;
                object-fit: cover;
                filter: brightness(var(--brightness));
                image-rendering: auto;
            }}
            #sprite-canvas {{
                position: absolute;
                inset: 0;
                width: 100%;
                height: 100%;
            }}
            #animated-character {{
                position: absolute;
                left: calc(var(--x) * 100%);
                top: calc(var(--y) * 100%);
                width: calc(var(--scale) * 36%);
                max-height: 84%;
                object-fit: contain;
                transform: translate(-50%, -100%) scaleX(var(--mirror));
                transform-origin: center bottom;
                image-rendering: auto;
                filter: drop-shadow(0 14px 13px rgba(0,0,0,.45));
            }}
            .identity {{
                position: absolute;
                top: 18px;
                left: 18px;
                display: flex;
                align-items: center;
                gap: 9px;
                padding: 8px 12px;
                border: 1px solid rgba(255,255,255,.18);
                border-radius: 999px;
                background: rgba(8, 11, 19, .78);
                box-shadow: 0 6px 20px rgba(0,0,0,.26);
                backdrop-filter: blur(8px);
                font-weight: 800;
            }}
            .identity i {{
                width: 8px;
                height: 8px;
                border-radius: 50%;
                background: #60e6ad;
                box-shadow: 0 0 12px #60e6ad;
            }}
            .identity small {{ color: #aeb6c9; font-weight: 700; }}
            .controls {{
                position: absolute;
                right: 18px;
                bottom: 18px;
                display: flex;
                align-items: center;
                gap: 8px;
            }}
            button {{
                min-width: 96px;
                padding: 9px 14px;
                border: 1px solid rgba(255,255,255,.2);
                border-radius: 10px;
                background: rgba(11, 15, 24, .86);
                color: #fff;
                cursor: pointer;
                font-weight: 800;
                backdrop-filter: blur(8px);
            }}
            button:hover {{ border-color: #7d88ff; background: #222947; }}
            .frame-readout {{
                min-width: 78px;
                padding: 8px 10px;
                border-radius: 9px;
                background: rgba(11, 15, 24, .78);
                color: #b8c0d5;
                text-align: center;
                font: 700 12px monospace;
            }}
            .hint {{
                position: absolute;
                left: 18px;
                bottom: 18px;
                color: rgba(255,255,255,.72);
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <div class="stage" id="stage">
            <img id="background" alt="사무실 배경">
            <canvas id="sprite-canvas" width="1280" height="720"></canvas>
            <img id="animated-character" alt="직원 캐릭터">
            <div class="identity"><i></i><span id="employee-label"></span><small id="action-label"></small></div>
            <div class="hint" id="mode-hint"></div>
            <div class="controls">
                <span class="frame-readout" id="frame-readout">FRAME 1</span>
                <button type="button" id="restart">처음부터</button>
                <button type="button" id="toggle">일시정지</button>
            </div>
        </div>
        <script>
            const data = {payload};
            const stage = document.getElementById('stage');
            const background = document.getElementById('background');
            const animatedCharacter = document.getElementById('animated-character');
            const canvas = document.getElementById('sprite-canvas');
            const context = canvas.getContext('2d');
            const frameReadout = document.getElementById('frame-readout');
            const toggleButton = document.getElementById('toggle');
            const restartButton = document.getElementById('restart');
            const spriteMode = data.mode === '가로 스프라이트 시트' || data.mode === '세로 스프라이트 시트';
            const nativeAnimatedMode = data.mode === '애니메이션 이미지';
            let currentFrame = 0;
            let playing = true;
            let lastFrameAt = 0;
            let animationRequest = null;
            let spriteImage = null;

            stage.style.setProperty('--brightness', data.brightness);
            stage.style.setProperty('--x', data.x);
            stage.style.setProperty('--y', data.y);
            stage.style.setProperty('--scale', data.scale);
            stage.style.setProperty('--mirror', data.mirror ? -1 : 1);
            background.src = data.background;
            document.getElementById('employee-label').textContent = data.employee;
            document.getElementById('action-label').textContent = data.action;
            document.getElementById('mode-hint').textContent = spriteMode
                ? `${{data.frames}}프레임 · ${{data.fps}} FPS`
                : (nativeAnimatedMode ? 'GIF · WebP · APNG 자동 재생' : '정지 이미지 배치 확인');

            function drawSprite() {{
                if (!spriteImage || !spriteImage.complete) return;
                context.clearRect(0, 0, canvas.width, canvas.height);
                context.imageSmoothingEnabled = true;
                context.imageSmoothingQuality = 'high';
                const horizontal = data.mode === '가로 스프라이트 시트';
                const alignment = horizontal ? data.frame_alignment : null;
                const frameSequence = alignment && alignment.frame_sequence;
                const sourceFrame = (
                    frameSequence && frameSequence.length === data.frames
                        ? frameSequence[currentFrame]
                        : currentFrame
                );
                const gridRows = alignment && alignment.grid_rows
                    ? alignment.grid_rows
                    : 1;
                const rowIndex = alignment && Number.isInteger(alignment.row_index)
                    ? alignment.row_index
                    : 0;
                const rowStart = horizontal
                    ? Math.round(rowIndex * spriteImage.naturalHeight / gridRows)
                    : 0;
                const rowEnd = horizontal
                    ? Math.round((rowIndex + 1) * spriteImage.naturalHeight / gridRows)
                    : spriteImage.naturalHeight;
                const sourceWidth = horizontal ? spriteImage.naturalWidth / data.frames : spriteImage.naturalWidth;
                const sourceHeight = horizontal ? rowEnd - rowStart : spriteImage.naturalHeight / data.frames;
                const sourceX = horizontal ? sourceWidth * sourceFrame : 0;
                const sourceY = horizontal ? rowStart : sourceHeight * currentFrame;
                let drawSourceX = sourceX;
                let drawSourceY = sourceY;
                let drawSourceWidth = sourceWidth;
                let drawSourceHeight = sourceHeight;
                let targetHeight;
                let targetWidth;
                let targetX;
                let targetY;
                if (
                    alignment
                    && alignment.body_centers
                    && alignment.body_centers.length === data.frames
                ) {{
                    const targetContentHeight = canvas.height * 0.72 * data.scale;
                    const contentScale = targetContentHeight / alignment.content_height;
                    const contentBoxes = alignment.content_boxes;
                    const frameBaseline = (
                        alignment.baselines
                        && alignment.baselines.length === data.frames
                    )
                        ? alignment.baselines[sourceFrame]
                        : alignment.baseline;
                    if (contentBoxes && contentBoxes.length === data.frames) {{
                        const frameStart = Math.round(
                            sourceFrame * spriteImage.naturalWidth / data.frames
                        );
                        const frameEnd = Math.round(
                            (sourceFrame + 1) * spriteImage.naturalWidth / data.frames
                        );
                        const frameWidth = frameEnd - frameStart;
                        const [boxX, boxY, boxWidth, boxHeight] = contentBoxes[sourceFrame];
                        const padding = 3;
                        const cropX = Math.max(0, boxX - padding);
                        const cropY = Math.max(0, boxY - padding);
                        const cropRight = Math.min(frameWidth, boxX + boxWidth + padding);
                        const cropBottom = Math.min(
                            sourceHeight,
                            boxY + boxHeight + padding
                        );
                        const cropWidth = Math.max(1, cropRight - cropX);
                        const cropHeight = Math.max(1, cropBottom - cropY);
                        drawSourceX = frameStart + cropX;
                        drawSourceY = rowStart + cropY;
                        drawSourceWidth = cropWidth;
                        drawSourceHeight = cropHeight;
                        targetWidth = cropWidth * contentScale;
                        targetHeight = cropHeight * contentScale;
                        targetX = (
                            canvas.width * data.x
                            - alignment.body_centers[sourceFrame] * contentScale
                            + cropX * contentScale
                        );
                        targetY = (
                            canvas.height * data.y
                            - frameBaseline * contentScale
                            + cropY * contentScale
                        );
                    }} else {{
                        targetHeight = sourceHeight * contentScale;
                        targetWidth = sourceWidth * contentScale;
                        targetX = (
                            canvas.width * data.x
                            - alignment.body_centers[sourceFrame] * contentScale
                        );
                        targetY = canvas.height * data.y - frameBaseline * contentScale;
                    }}
                }} else {{
                    targetHeight = canvas.height * 0.72 * data.scale;
                    targetWidth = targetHeight * sourceWidth / sourceHeight;
                    targetX = canvas.width * data.x - targetWidth / 2;
                    targetY = canvas.height * data.y - targetHeight;
                }}
                context.save();
                if (data.mirror) {{
                    context.translate(canvas.width * data.x * 2, 0);
                    context.scale(-1, 1);
                }}
                context.shadowColor = 'rgba(0,0,0,.45)';
                context.shadowBlur = 18;
                context.shadowOffsetY = 12;
                context.drawImage(
                    spriteImage,
                    drawSourceX, drawSourceY, drawSourceWidth, drawSourceHeight,
                    targetX, targetY, targetWidth, targetHeight
                );
                context.restore();
                frameReadout.textContent = `FRAME ${{currentFrame + 1}}/${{data.frames}}`;
            }}

            function animate(timestamp) {{
                if (playing && timestamp - lastFrameAt >= 1000 / data.fps) {{
                    if (currentFrame < data.frames - 1) {{
                        currentFrame += 1;
                    }} else if (data.loop) {{
                        currentFrame = 0;
                    }} else {{
                        playing = false;
                        toggleButton.textContent = '재생';
                    }}
                    drawSprite();
                    lastFrameAt = timestamp;
                }}
                animationRequest = requestAnimationFrame(animate);
            }}

            if (spriteMode) {{
                animatedCharacter.hidden = true;
                spriteImage = new Image();
                spriteImage.onload = () => {{ drawSprite(); animationRequest = requestAnimationFrame(animate); }};
                spriteImage.src = data.character;
            }} else {{
                canvas.hidden = true;
                animatedCharacter.src = data.character;
                frameReadout.textContent = nativeAnimatedMode ? 'AUTO' : 'STATIC';
                if (nativeAnimatedMode) {{
                    toggleButton.disabled = true;
                    restartButton.disabled = true;
                    toggleButton.textContent = '자동 재생';
                }} else {{
                    toggleButton.disabled = true;
                    restartButton.disabled = true;
                    toggleButton.textContent = '정지 이미지';
                }}
            }}

            toggleButton.addEventListener('click', () => {{
                playing = !playing;
                if (playing && !data.loop && currentFrame >= data.frames - 1) {{
                    currentFrame = 0;
                    drawSprite();
                }}
                toggleButton.textContent = playing ? '일시정지' : '재생';
                if (playing) lastFrameAt = performance.now();
            }});
            restartButton.addEventListener('click', () => {{
                currentFrame = 0;
                playing = true;
                toggleButton.textContent = '일시정지';
                lastFrameAt = performance.now();
                drawSprite();
            }});
            window.addEventListener('beforeunload', () => {{
                if (animationRequest) cancelAnimationFrame(animationRequest);
            }});
        </script>
    </body>
    </html>
    """
    st.iframe(component_html, height=730)


def render_animation_lab() -> None:
    """YOUFFICE 본 화면과 분리된 애니메이션 미리보기 도구를 표시합니다."""

    st.markdown(
        """
        <style>
            [data-testid="stAppViewContainer"] { background: #0b0e15; }
            [data-testid="stHeader"] { background: rgba(11,14,21,.88); }
            .lab-title { margin: .2rem 0; font-size: 2rem; font-weight: 900; }
            .lab-subtitle { margin-bottom: 1.2rem; color: #8f98ad; }
            .stButton button, .stLinkButton a { border-radius: 10px; }
        </style>
        <div class="lab-title">🎞️ YOUFFICE 애니메이션 실험실</div>
        <div class="lab-subtitle">본 프로그램과 분리된 화면에서 캐릭터 동작과 배치를 시험합니다.</div>
        """,
        unsafe_allow_html=True,
    )

    st.link_button("← YOUFFICE로 돌아가기", "/", use_container_width=False)

    settings_column, preview_column = st.columns([0.28, 0.72], gap="large")
    with settings_column:
        employee_name = st.selectbox("기본 직원", tuple(EMPLOYEE_ASSETS))
        asset_id = EMPLOYEE_ASSETS[employee_name]
        use_yuki_pixel_draft = False
        if employee_name == "유키" and YUKI_PIXEL_DRAFT_FILE.exists():
            use_yuki_pixel_draft = st.checkbox(
                "새 유키 픽셀 기준 시안 사용",
                value=True,
            )
        action_label = st.selectbox("표시할 행동", ACTION_LABELS)
        builtin_action_spec = BUILTIN_ACTION_SPRITES.get(employee_name, {}).get(
            action_label
        )
        use_builtin_action_sprite = bool(
            builtin_action_spec is not None
            and builtin_action_spec["path"].exists()
        )
        if use_builtin_action_sprite:
            animation_mode = "가로 스프라이트 시트"
            builtin_frame_count = int(builtin_action_spec.get("frame_count", 4))
            st.caption(
                f"{employee_name} 직무 맞춤 동작 · "
                f"{builtin_frame_count}프레임 자동 재생"
            )
        else:
            animation_mode = st.selectbox(
                "파일 형식",
                (
                    "정지 이미지",
                    "애니메이션 이미지",
                    "가로 스프라이트 시트",
                    "세로 스프라이트 시트",
                ),
                help="GIF·애니메이션 WebP는 애니메이션 이미지를 선택하세요.",
            )
        character_upload = st.file_uploader(
            "캐릭터 파일",
            type=("png", "webp", "gif"),
            help="선택하지 않으면 현재 직원 캐릭터가 사용됩니다.",
        )
        background_upload = st.file_uploader(
            "배경 파일",
            type=("png", "jpg", "jpeg", "webp"),
            help="선택하지 않으면 직원의 현재 사무실이 사용됩니다.",
        )

        with st.expander("외부 제작용 파일 다운로드", expanded=True):
            selected_reference_path = SPRITE_DIRECTORY / f"{asset_id}.png"
            if selected_reference_path.exists():
                st.download_button(
                    f"{employee_name} 기준 이미지 다운로드",
                    data=selected_reference_path.read_bytes(),
                    file_name=f"{employee_name}_현재_캐릭터_기준.png",
                    mime="image/png",
                    use_container_width=True,
                )
            if employee_name == "유키" and YUKI_PIXEL_DRAFT_FILE.exists():
                st.download_button(
                    "유키 픽셀 기준 시안 다운로드",
                    data=YUKI_PIXEL_DRAFT_FILE.read_bytes(),
                    file_name="유키_픽셀_기준_시안.png",
                    mime="image/png",
                    use_container_width=True,
                )
            if use_builtin_action_sprite and builtin_action_spec is not None:
                builtin_action_file = builtin_action_spec["path"]
                st.download_button(
                    f"{employee_name} {action_label} 동작 시트 다운로드",
                    data=builtin_action_file.read_bytes(),
                    file_name=f"{employee_name}_{action_label.replace('·', '_')}_동작시트.png",
                    mime="image/png",
                    use_container_width=True,
                )
            st.download_button(
                "6명 기준 이미지 ZIP 다운로드",
                data=employee_reference_zip(),
                file_name="YOUFFICE_직원_기준_이미지_6명.zip",
                mime="application/zip",
                use_container_width=True,
            )
            if PROMPT_GUIDE_FILE.exists():
                st.download_button(
                    "제작 조건문 TXT 다운로드",
                    data=PROMPT_GUIDE_FILE.read_bytes(),
                    file_name=PROMPT_GUIDE_FILE.name,
                    mime="text/plain",
                    use_container_width=True,
                )
            st.caption(
                "현재 이미지는 외형 참고용입니다. 조건문으로 픽셀 기준 이미지를 먼저 만든 뒤 "
                "그 결과를 행동별 제작에 다시 사용하세요."
            )

        frame_count = 1
        fps = 8
        if use_builtin_action_sprite and builtin_action_spec is not None:
            frame_count = int(builtin_action_spec.get("frame_count", 4))
            fps = st.slider(
                "재생 속도(FPS)",
                1,
                12,
                builtin_action_spec["fps"],
                key=f"builtin_action_fps_{employee_name}_{action_label}",
            )
        elif "스프라이트 시트" in animation_mode:
            frame_count = st.slider("프레임 수", 2, 24, 8)
            fps = st.slider("재생 속도(FPS)", 1, 24, 8)
        scale = st.slider("캐릭터 크기", 20, 180, 100, format="%d%%")
        position_x = st.slider("좌우 위치", 0, 100, 67, format="%d%%")
        position_y = st.slider("상하 위치", 20, 100, 94, format="%d%%")
        background_brightness = st.slider("배경 밝기", 35, 120, 82, format="%d%%")
        mirror_character = st.checkbox("캐릭터 좌우 반전")

        if animation_mode == "애니메이션 이미지":
            st.caption("GIF·WebP 자체의 재생 속도는 원본 파일에 저장된 속도를 사용합니다.")
        elif "스프라이트 시트" in animation_mode:
            st.caption("모든 프레임은 같은 크기로 한 줄에 정렬되어 있어야 합니다.")

    character_url = f"/app/static/sprites/{asset_id}.png"
    if use_yuki_pixel_draft:
        character_url = (
            "/app/static/animation/yuki/yuki_pixel_master.png"
            f"?v={YUKI_PIXEL_DRAFT_FILE.stat().st_mtime_ns}"
        )
    if use_builtin_action_sprite and builtin_action_spec is not None:
        builtin_action_file = builtin_action_spec["path"]
        relative_action_path = builtin_action_file.relative_to(
            PROJECT_ROOT / "static"
        ).as_posix()
        character_url = (
            f"/app/static/{relative_action_path}"
            f"?v={builtin_action_file.stat().st_mtime_ns}"
        )
    background_url = f"/app/static/rooms/{asset_id}.png"
    if character_upload is not None:
        character_url = uploaded_file_data_url(character_upload)
    if background_upload is not None:
        background_url = uploaded_file_data_url(background_upload)

    with preview_column:
        st.markdown(f"#### {html.escape(employee_name)} · {html.escape(action_label)} 미리보기")
        render_preview_component(
            background_url,
            character_url,
            employee_name,
            action_label,
            animation_mode,
            frame_count,
            fps,
            scale,
            position_x,
            position_y,
            mirror_character,
            background_brightness,
            (
                builtin_action_spec["alignment"]
                if use_builtin_action_sprite
                and builtin_action_spec is not None
                and character_upload is None
                else None
            ),
        )

    with st.expander("사용 방법"):
        st.markdown(
            """
            1. 직원을 선택하면 현재 캐릭터와 사무실 배경이 표시됩니다.
            2. 새 GIF, WebP 또는 스프라이트 시트를 `캐릭터 파일`에 올립니다.
            3. 크기와 위치를 조절해 실제 사무실 화면과 어울리는지 확인합니다.
            4. 스프라이트 시트는 프레임 수와 FPS를 바꿔 자연스러운 속도를 찾습니다.

            업로드한 파일은 미리보기용으로만 사용되며 자동 저장되지 않습니다.
            """
        )
