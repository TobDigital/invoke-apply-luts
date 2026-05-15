# invoke-apply-luts
InvokeAI community node for applying 3D .cube LUTs with dropdown selection, strength control, interpolation modes, and alpha preservation.

# Invoke LUT

Invoke LUT is a standalone InvokeAI 6.x community node for applying 3D `.cube` LUTs to images directly inside an InvokeAI workflow.

The node loads LUT files from a fixed local `luts` folder and exposes them as a dropdown in the workflow editor. It supports smooth trilinear interpolation, nearest-neighbor LUT sampling, adjustable strength, and optional alpha preservation.

## Features

- Standalone InvokeAI custom node
- Applies 3D `.cube` LUT files
- Dropdown selection from the local `invoke_lut/luts/` folder
- Supports LUTs in subfolders
- Adjustable LUT strength
- Trilinear or nearest interpolation
- Optional alpha-channel preservation

## Usage

Place your `.cube` LUT files in:

/nodes/invoke_lut/luts/

