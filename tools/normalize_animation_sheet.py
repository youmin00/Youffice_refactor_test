"""Normalize a 2x2 or 4x2 storyboard into a stable horizontal sprite sheet.

The chroma key must already have been converted to alpha.  Every output frame
is 512x512, shares one scale, is anchored by the feet, and has a transparent
background. Four-frame sources use a 2x2 grid and eight-frame sources use a
4x2 grid. This removes runtime crop/centering guesses from the UI.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


FRAME_SIZE = 512
FOOT_BASELINE = 488
SIDE_MARGIN = 20
TOP_MARGIN = 20


def _content_box(image: Image.Image) -> tuple[int, int, int, int]:
    alpha = image.getchannel("A")
    box = alpha.getbbox()
    if box is None:
        raise ValueError("투명하지 않은 캐릭터 픽셀을 찾지 못했습니다.")
    return box


def _foot_center(
    image: Image.Image,
    box: tuple[int, int, int, int],
) -> float:
    """Estimate body center from the lowest opaque pixels, ignoring hand props."""

    left, top, right, bottom = box
    alpha = image.getchannel("A")
    band_top = max(top, bottom - max(8, int((bottom - top) * 0.16)))
    pixels = alpha.load()
    x_values: list[int] = []
    for y in range(band_top, bottom):
        for x in range(left, right):
            if pixels[x, y] >= 96:
                x_values.append(x)
    if not x_values:
        return (left + right) / 2
    return (min(x_values) + max(x_values)) / 2


def _analyze_sheet(
    source: Path,
    frame_count: int = 4,
    grid_columns: int | None = None,
) -> tuple[
    list[Image.Image],
    list[tuple[int, int, int, int]],
    list[float],
    float,
]:
    image = Image.open(source).convert("RGBA")
    width, height = image.size
    if width < 512 or height < 512:
        raise ValueError(f"원본이 너무 작습니다: {width}x{height}")

    if frame_count not in {4, 8}:
        raise ValueError(f"지원하지 않는 프레임 수입니다: {frame_count}")
    if grid_columns is None:
        grid_columns = 2 if frame_count == 4 else 4
    if grid_columns <= 0 or frame_count % grid_columns != 0:
        raise ValueError(
            f"프레임 수 {frame_count}를 {grid_columns}열로 나눌 수 없습니다."
        )
    grid_rows = frame_count // grid_columns
    x_edges = tuple(
        round(column * width / grid_columns)
        for column in range(grid_columns + 1)
    )
    y_edges = tuple(
        round(row * height / grid_rows)
        for row in range(grid_rows + 1)
    )
    cells: list[Image.Image] = []
    boxes: list[tuple[int, int, int, int]] = []
    foot_centers: list[float] = []
    for row in range(grid_rows):
        for column in range(grid_columns):
            cell = image.crop(
                (
                    x_edges[column],
                    y_edges[row],
                    x_edges[column + 1],
                    y_edges[row + 1],
                )
            )
            box = _content_box(cell)
            if (
                box[0] <= 1
                or box[1] <= 1
                or box[2] >= cell.width - 1
                or box[3] >= cell.height - 1
            ):
                raise ValueError(
                    f"프레임 {len(cells) + 1}의 캐릭터가 원본 칸 경계에 닿았습니다."
                )
            cells.append(cell)
            boxes.append(box)
            foot_centers.append(_foot_center(cell, box))

    max_target_height = float(FOOT_BASELINE - TOP_MARGIN)
    for box, foot_center in zip(boxes, foot_centers):
        left, top, right, bottom = box
        content_height = bottom - top
        horizontal_extent = max(foot_center - left, right - foot_center)
        width_limited_height = (
            (FRAME_SIZE / 2 - SIDE_MARGIN)
            * content_height
            / horizontal_extent
        )
        max_target_height = min(max_target_height, width_limited_height)
    return cells, boxes, foot_centers, max_target_height


def normalize_sheet(
    source: Path,
    output: Path,
    target_height: float | None = None,
    frame_count: int = 4,
    grid_columns: int | None = None,
) -> list[dict[str, float]]:
    cells, boxes, foot_centers, sheet_target_height = _analyze_sheet(
        source,
        frame_count=frame_count,
        grid_columns=grid_columns,
    )
    if target_height is None:
        target_height = sheet_target_height
    elif target_height > sheet_target_height + 1e-9:
        raise ValueError(
            f"공통 높이 {target_height:.2f}가 {source.name}의 안전 높이 "
            f"{sheet_target_height:.2f}보다 큽니다."
        )

    output_sheet = Image.new(
        "RGBA",
        (FRAME_SIZE * frame_count, FRAME_SIZE),
        (0, 0, 0, 0),
    )
    diagnostics: list[dict[str, float]] = []
    for index, (cell, box, foot_center) in enumerate(
        zip(cells, boxes, foot_centers)
    ):
        cropped = cell.crop(box)
        scale = target_height / cropped.height
        target_width = max(1, round(cropped.width * scale))
        rendered_height = max(1, round(cropped.height * scale))
        resized = cropped.resize(
            (target_width, rendered_height),
            Image.Resampling.NEAREST,
        )
        relative_foot_center = (foot_center - box[0]) * scale
        paste_x = round(FRAME_SIZE / 2 - relative_foot_center)
        paste_y = FOOT_BASELINE - rendered_height
        if (
            paste_x < 0
            or paste_y < 0
            or paste_x + target_width > FRAME_SIZE
            or paste_y + rendered_height > FRAME_SIZE
        ):
            raise ValueError(f"프레임 {index + 1} 정규화 후 잘림이 발생합니다.")
        output_sheet.alpha_composite(resized, (index * FRAME_SIZE + paste_x, paste_y))
        diagnostics.append(
            {
                "frame": index + 1,
                "width": target_width,
                "height": rendered_height,
                "left": paste_x,
                "top": paste_y,
                "baseline": FOOT_BASELINE,
            }
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    output_sheet.save(output, optimize=True)
    return diagnostics


def normalize_employee_directory(
    directory: Path,
    frame_count: int = 4,
    grid_columns: int | None = None,
) -> list[Path]:
    slug = directory.name
    source_suffix = (
        "_source_alpha.png"
        if frame_count == 4
        else f"_{frame_count}f_source_alpha.png"
    )
    expected_actions = {
        "idle",
        "thinking",
        "working",
        "talking",
        "handoff",
        "complete",
        "rework",
    }
    sources = sorted(
        directory / f"{slug}_{action}{source_suffix}"
        for action in expected_actions
        if (directory / f"{slug}_{action}{source_suffix}").exists()
    )
    source_actions = {
        source.name.removeprefix(f"{slug}_").removesuffix(source_suffix)
        for source in sources
    }
    if source_actions != expected_actions:
        missing = sorted(expected_actions - source_actions)
        extra = sorted(source_actions - expected_actions)
        raise ValueError(f"행동 파일 불일치: missing={missing}, extra={extra}")

    safe_heights = [
        _analyze_sheet(
            source,
            frame_count=frame_count,
            grid_columns=grid_columns,
        )[3]
        for source in sources
    ]
    employee_height = min(safe_heights)
    print(f"employee content height: {employee_height:.3f}")
    outputs: list[Path] = []
    for source in sources:
        action = source.name.removeprefix(f"{slug}_").removesuffix(source_suffix)
        output = directory / f"{slug}_{action}_{frame_count}f.png"
        normalize_sheet(
            source,
            output,
            employee_height,
            frame_count=frame_count,
            grid_columns=grid_columns,
        )
        outputs.append(output)
        print(f"saved: {output} ({FRAME_SIZE * frame_count}x{FRAME_SIZE})")
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--input", type=Path)
    source_group.add_argument("--employee-directory", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--frames", type=int, choices=(4, 8), default=4)
    parser.add_argument("--grid-columns", type=int)
    args = parser.parse_args()
    if args.employee_directory is not None:
        normalize_employee_directory(
            args.employee_directory,
            frame_count=args.frames,
            grid_columns=args.grid_columns,
        )
        return
    if args.output is None:
        parser.error("--input을 사용할 때는 --output이 필요합니다.")
    diagnostics = normalize_sheet(
        args.input,
        args.output,
        frame_count=args.frames,
        grid_columns=args.grid_columns,
    )
    print(f"saved: {args.output} ({FRAME_SIZE * args.frames}x{FRAME_SIZE})")
    for item in diagnostics:
        print(
            "frame {frame}: {width}x{height}, x={left}, y={top}, "
            "baseline={baseline}".format(**item)
        )


if __name__ == "__main__":
    main()
