"""Validate all canonical YOUFFICE employee animation sheets."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


STAFF = ("yuki", "heejeong", "leo", "matsuri", "levi", "miko")
ACTIONS = (
    "idle",
    "thinking",
    "working",
    "talking",
    "handoff",
    "complete",
    "rework",
)
FRAME_SIZE = 512
SUPPORTED_FRAME_COUNTS = (8, 4)
EXPECTED_HEIGHT = 468
HEIGHT_TOLERANCE = 1
EXPECTED_BASELINE = 488
EXPECTED_FOOT_CENTER = 256
FOOT_CENTER_TOLERANCE = 2


def _foot_center(frame: Image.Image, box: tuple[int, int, int, int]) -> float:
    left, top, right, bottom = box
    band_top = max(top, bottom - max(8, int((bottom - top) * 0.16)))
    alpha = frame.getchannel("A")
    pixels = alpha.load()
    x_values = [
        x
        for y in range(band_top, bottom)
        for x in range(left, right)
        if pixels[x, y] >= 96
    ]
    if not x_values:
        return (left + right) / 2
    return (min(x_values) + max(x_values)) / 2


def validate_sheet(path: Path, frame_count: int | None = None) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"파일 없음: {path}"]
    image = Image.open(path).convert("RGBA")
    if frame_count is None:
        if image.height != FRAME_SIZE or image.width % FRAME_SIZE != 0:
            return [f"프레임 수를 판별할 수 없는 크기입니다: {image.size}"]
        frame_count = image.width // FRAME_SIZE
    if frame_count not in SUPPORTED_FRAME_COUNTS:
        return [f"지원하지 않는 프레임 수입니다: {frame_count}"]
    expected_size = (FRAME_SIZE * frame_count, FRAME_SIZE)
    if image.size != expected_size:
        errors.append(f"크기 오류 {image.size}, expected={expected_size}")
        return errors
    for frame_index in range(frame_count):
        frame = image.crop(
            (
                frame_index * FRAME_SIZE,
                0,
                (frame_index + 1) * FRAME_SIZE,
                FRAME_SIZE,
            )
        )
        box = frame.getchannel("A").getbbox()
        prefix = f"frame {frame_index + 1}"
        if box is None:
            errors.append(f"{prefix}: 캐릭터 없음")
            continue
        left, top, right, bottom = box
        if bottom != EXPECTED_BASELINE:
            errors.append(f"{prefix}: baseline={bottom}")
        if abs((bottom - top) - EXPECTED_HEIGHT) > HEIGHT_TOLERANCE:
            errors.append(f"{prefix}: height={bottom - top}")
        foot_center = _foot_center(frame, box)
        if abs(foot_center - EXPECTED_FOOT_CENTER) > FOOT_CENTER_TOLERANCE:
            errors.append(f"{prefix}: foot_center={foot_center:.1f}")
        if min(left, FRAME_SIZE - right) < 8:
            errors.append(f"{prefix}: 좌우 안전 여백 부족 ({left}, {FRAME_SIZE-right})")
        if top < 8:
            errors.append(f"{prefix}: 상단 안전 여백 부족 ({top})")
        if frame.getpixel((0, 0))[3] != 0 or frame.getpixel((511, 511))[3] != 0:
            errors.append(f"{prefix}: 모서리가 투명하지 않음")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("static/animation_v2"),
    )
    args = parser.parse_args()
    checked = 0
    checked_frames = 0
    all_errors: list[str] = []
    for staff in STAFF:
        for action in ACTIONS:
            selected_path: Path | None = None
            selected_frame_count = 0
            for frame_count in SUPPORTED_FRAME_COUNTS:
                candidate = (
                    args.root / staff / f"{staff}_{action}_{frame_count}f.png"
                )
                if candidate.exists():
                    selected_path = candidate
                    selected_frame_count = frame_count
                    break
            if selected_path is None:
                selected_frame_count = 4
                selected_path = args.root / staff / f"{staff}_{action}_4f.png"
            errors = validate_sheet(selected_path, selected_frame_count)
            checked += 1
            checked_frames += selected_frame_count
            all_errors.extend(f"{selected_path}: {error}" for error in errors)
    if all_errors:
        raise SystemExit("\n".join(all_errors))
    print(f"validated: {checked} sheets / {checked_frames} frames")


if __name__ == "__main__":
    main()
