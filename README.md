# Invoke LUT for InvokeAI

Standalone InvokeAI 6.x community node for applying 3D `.cube` LUT files.

## Node

- **Apply LUT**: applies a 3D `.cube` LUT to an input image.

## LUT Folder

Put LUT files in:

```text
invoke_lut/luts/
```

A few LUTs have been included as examples.

The node shows the discovered `.cube` files in the `lut_name` dropdown.

```text
cinematic.cube
```

Subfolders are supported:

```text
film/kodak_2383.cube
```

The node only resolves files inside this fixed folder. Absolute paths and `..` path escapes are rejected.

InvokeAI reads the dropdown values when the node package is loaded. Restart InvokeAI after adding, removing, or renaming LUT files.

## Controls

- `image`: image to color grade.
- `lut_name`: dropdown with `.cube` files inside `invoke_lut/luts/`.
- `strength`: blend amount from `0.0` to `1.0`.
- `interpolation`: `trilinear` for smooth sampling or `nearest` for hard table steps.
- `preserve_alpha`: keeps the source alpha channel when present.

## Notes

Only 3D `.cube` LUTs are supported. 1D `.cube` LUTs are rejected with a clear error.
