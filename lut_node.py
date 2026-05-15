from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from invokeai.invocation_api import (
    BaseInvocation,
    ImageField,
    ImageOutput,
    InputField,
    InvocationContext,
    WithBoard,
    WithMetadata,
    invocation,
)
from PIL import Image


InterpolationMode = Literal["trilinear", "nearest"]

LUT_DIRECTORY = Path(__file__).resolve().parent / "luts"
MAX_LUT_SIZE = 128
NO_LUTS_FOUND = "__no_luts_found__"


@dataclass(frozen=True)
class CubeLUT:
    title: str | None
    size: int
    domain_min: np.ndarray
    domain_max: np.ndarray
    table: np.ndarray


_LUT_CACHE: dict[tuple[Path, int], CubeLUT] = {}


def _available_luts() -> list[str]:
    if not LUT_DIRECTORY.exists():
        return []
    return sorted(str(path.relative_to(LUT_DIRECTORY)) for path in LUT_DIRECTORY.rglob("*.cube") if path.is_file())


def _make_lut_literal():
    names = _available_luts()
    if not names:
        names = [NO_LUTS_FOUND]
    return Literal.__getitem__(tuple(names))


AvailableLUT = _make_lut_literal()


def _default_lut() -> str:
    names = _available_luts()
    return names[0] if names else NO_LUTS_FOUND


def _available_luts_message() -> str:
    names = _available_luts()
    if not names:
        return f"No .cube LUT files found in {LUT_DIRECTORY}."
    return "Available LUTs: " + ", ".join(names)


def _resolve_lut_path(lut_name: str) -> Path:
    if not lut_name or not lut_name.strip():
        raise ValueError(f"Enter a LUT filename from the fixed LUT folder. {_available_luts_message()}")

    raw_name = lut_name.strip()
    if raw_name == NO_LUTS_FOUND:
        raise ValueError(f"No LUT can be selected yet. Place at least one .cube LUT in {LUT_DIRECTORY} and restart InvokeAI.")
    if Path(raw_name).is_absolute():
        raise ValueError("Use a filename from the fixed LUT folder, not an absolute path.")

    requested = Path(raw_name)
    if requested.suffix == "":
        requested = requested.with_suffix(".cube")
    if requested.suffix.lower() != ".cube":
        raise ValueError("Only .cube LUT files are supported.")

    root = LUT_DIRECTORY.resolve()
    resolved = (root / requested).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("LUT filenames must stay inside the fixed LUT folder.") from exc

    if not resolved.exists() or not resolved.is_file():
        raise ValueError(f"LUT '{raw_name}' was not found in {LUT_DIRECTORY}. {_available_luts_message()}")

    return resolved


def _parse_three_floats(parts: list[str], keyword: str) -> np.ndarray:
    if len(parts) < 4:
        raise ValueError(f"{keyword} must contain three numeric values.")
    try:
        return np.asarray([float(parts[1]), float(parts[2]), float(parts[3])], dtype=np.float32)
    except ValueError as exc:
        raise ValueError(f"{keyword} contains an invalid numeric value.") from exc


def _parse_cube_lut(path: Path) -> CubeLUT:
    title: str | None = None
    size: int | None = None
    domain_min = np.asarray([0.0, 0.0, 0.0], dtype=np.float32)
    domain_max = np.asarray([1.0, 1.0, 1.0], dtype=np.float32)
    values: list[tuple[float, float, float]] = []

    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, original_line in enumerate(handle, start=1):
            line = original_line.split("#", 1)[0].strip()
            if not line:
                continue

            parts = line.split()
            keyword = parts[0].upper()

            if keyword == "TITLE":
                title = line[5:].strip().strip('"')
                continue
            if keyword == "LUT_3D_SIZE":
                if len(parts) < 2:
                    raise ValueError(f"LUT_3D_SIZE is missing a value on line {line_number}.")
                size = int(parts[1])
                if size < 2 or size > MAX_LUT_SIZE:
                    raise ValueError(f"LUT_3D_SIZE must be between 2 and {MAX_LUT_SIZE}.")
                continue
            if keyword == "LUT_1D_SIZE":
                raise ValueError("1D .cube LUTs are not supported by this node.")
            if keyword == "DOMAIN_MIN":
                domain_min = _parse_three_floats(parts, keyword)
                continue
            if keyword == "DOMAIN_MAX":
                domain_max = _parse_three_floats(parts, keyword)
                continue
            if keyword == "LUT_3D_INPUT_RANGE":
                if len(parts) < 3:
                    raise ValueError(f"LUT_3D_INPUT_RANGE is missing values on line {line_number}.")
                try:
                    input_min = float(parts[1])
                    input_max = float(parts[2])
                except ValueError as exc:
                    raise ValueError(f"LUT_3D_INPUT_RANGE contains an invalid value on line {line_number}.") from exc
                domain_min = np.asarray([input_min, input_min, input_min], dtype=np.float32)
                domain_max = np.asarray([input_max, input_max, input_max], dtype=np.float32)
                continue
            if keyword.startswith("LUT_"):
                continue

            if len(parts) < 3:
                raise ValueError(f"Invalid LUT data row on line {line_number}.")
            try:
                values.append((float(parts[0]), float(parts[1]), float(parts[2])))
            except ValueError as exc:
                raise ValueError(f"Invalid LUT data row on line {line_number}.") from exc

    if size is None:
        raise ValueError("Missing LUT_3D_SIZE in .cube file.")

    expected_values = size**3
    if len(values) != expected_values:
        raise ValueError(f"Expected {expected_values} LUT values, found {len(values)}.")

    if np.any(np.isclose(domain_max - domain_min, 0.0)):
        raise ValueError("DOMAIN_MIN and DOMAIN_MAX must not contain equal channel values.")

    table = np.zeros((size, size, size, 3), dtype=np.float32)
    index = 0
    for blue in range(size):
        for green in range(size):
            for red in range(size):
                table[red, green, blue] = values[index]
                index += 1

    return CubeLUT(
        title=title,
        size=size,
        domain_min=domain_min,
        domain_max=domain_max,
        table=np.clip(table, 0.0, 1.0),
    )


def _load_cube_lut(path: Path) -> CubeLUT:
    cache_key = (path, path.stat().st_mtime_ns)
    cached = _LUT_CACHE.get(cache_key)
    if cached is not None:
        return cached

    lut = _parse_cube_lut(path)
    _LUT_CACHE.clear()
    _LUT_CACHE[cache_key] = lut
    return lut


def _apply_nearest(rgb: np.ndarray, lut: CubeLUT) -> np.ndarray:
    position = _lut_position(rgb, lut)
    indices = np.rint(position).astype(np.int16)
    return lut.table[indices[..., 0], indices[..., 1], indices[..., 2]]


def _lut_position(rgb: np.ndarray, lut: CubeLUT) -> np.ndarray:
    normalized = (rgb - lut.domain_min) / (lut.domain_max - lut.domain_min)
    return np.clip(normalized, 0.0, 1.0) * float(lut.size - 1)


def _apply_trilinear(rgb: np.ndarray, lut: CubeLUT) -> np.ndarray:
    position = _lut_position(rgb, lut)

    lower = np.floor(position).astype(np.int16)
    upper = np.minimum(lower + 1, lut.size - 1)
    fraction = position - lower

    r0, g0, b0 = lower[..., 0], lower[..., 1], lower[..., 2]
    r1, g1, b1 = upper[..., 0], upper[..., 1], upper[..., 2]
    rd = fraction[..., 0][..., None]
    gd = fraction[..., 1][..., None]
    bd = fraction[..., 2][..., None]
    table = lut.table

    c000 = table[r0, g0, b0]
    c100 = table[r1, g0, b0]
    c010 = table[r0, g1, b0]
    c110 = table[r1, g1, b0]
    c001 = table[r0, g0, b1]
    c101 = table[r1, g0, b1]
    c011 = table[r0, g1, b1]
    c111 = table[r1, g1, b1]

    c00 = c000 * (1.0 - rd) + c100 * rd
    c10 = c010 * (1.0 - rd) + c110 * rd
    c01 = c001 * (1.0 - rd) + c101 * rd
    c11 = c011 * (1.0 - rd) + c111 * rd
    c0 = c00 * (1.0 - gd) + c10 * gd
    c1 = c01 * (1.0 - gd) + c11 * gd
    return c0 * (1.0 - bd) + c1 * bd


def _rgb_array_to_image(rgb: np.ndarray, alpha: Image.Image | None) -> Image.Image:
    image = Image.fromarray(np.clip(rgb * 255.0, 0, 255).astype(np.uint8), mode="RGB")
    if alpha is not None:
        image.putalpha(alpha)
    return image


@invocation(
    "apply_lut",
    title="Apply LUT",
    tags=["lut", "cube", "color", "grading"],
    category="LUT",
    version="1.0.0",
)
class ApplyLUTInvocation(BaseInvocation, WithMetadata, WithBoard):
    """Applies a standalone 3D .cube LUT from the fixed invoke_lut/luts folder."""

    image: ImageField = InputField(description="The image to color grade")
    lut_name: AvailableLUT = InputField(default=_default_lut(), description="LUT file from invoke_lut/luts")
    strength: float = InputField(default=1.0, ge=0.0, le=1.0, description="Blend strength from 0.0 to 1.0")
    interpolation: InterpolationMode = InputField(default="trilinear", description="LUT sampling method")
    preserve_alpha: bool = InputField(default=True, description="Keep the source alpha channel when present")

    def invoke(self, context: InvocationContext) -> ImageOutput:
        source = context.images.get_pil(self.image.image_name)
        alpha = source.getchannel("A") if self.preserve_alpha and "A" in source.getbands() else None
        rgb = np.asarray(source.convert("RGB"), dtype=np.float32) / 255.0

        lut_path = _resolve_lut_path(str(self.lut_name))
        lut = _load_cube_lut(lut_path)

        if self.interpolation == "nearest":
            graded = _apply_nearest(rgb, lut)
        else:
            graded = _apply_trilinear(rgb, lut)

        result_rgb = rgb * (1.0 - self.strength) + graded * self.strength
        result = _rgb_array_to_image(result_rgb, alpha)
        image_dto = context.images.save(image=result)
        return ImageOutput.build(image_dto)
