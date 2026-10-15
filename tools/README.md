# Daily Reel + Story renderer

`render_template.py` renders one post set with Pillow and FFmpeg:

- `reel.mp4` (about 30 s, 1080x1920, 30 fps, H.264 + AAC, silent audio track, animated captions)
- `cover.png` (Reel cover)
- `story-1.png` .. `story-3.png` and `story.mp4` (13.5 s Story video built from the slides)

Usage: copy the file, edit the content blocks (code snippets, scene texts, cover and story texts),
then run `python3 render_template.py <output_dir>`. Requires `ffmpeg`, `Pillow`, `PyYAML` and the
DejaVu fonts. Keep text inside the central safe area (roughly y 250 to 1500).

Each day's output lives in `posts/<YYYY-MM-DD>-<slug>/`. Metricool reads the files through the
public raw.githubusercontent.com URLs, so this repository must stay public.
