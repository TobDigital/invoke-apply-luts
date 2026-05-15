# LUT Folder

Place 3D `.cube` LUT files in this folder, then restart InvokeAI if the UI does not pick up the new node files.

`identity.cube` is included as a no-op example LUT. It should not visibly change the image.

The **Apply LUT** node shows files from this folder in the `lut_name` dropdown, for example:

```text
cinematic.cube
```

Subfolders are supported as long as they stay inside this folder:

```text
film/kodak_2383.cube
```

Restart InvokeAI after adding, removing, or renaming LUT files so the dropdown can be rebuilt.
