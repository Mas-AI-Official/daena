# FFmpeg Recipes for Video Production

## Ken Burns on image (aggressive zoom + pan):
```bash
ffmpeg -loop 1 -i image.jpg -vf "scale=1920:1080,zoompan=z='min(zoom+0.0015,1.35)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=150:s=1080x1920" -t 5 -c:v libx264 out.mp4
```

## Crossfade transition between clips:
```bash
ffmpeg -i clip1.mp4 -i clip2.mp4 -filter_complex "xfade=transition=fade:duration=0.5:offset=4.5" out.mp4
```

## Glass card text overlay:
```bash
drawtext=text='Your text':fontsize=36:fontcolor=white:borderw=2:bordercolor=black:box=1:boxcolor=black@0.4:boxborderw=12:x=(w-text_w)/2:y=h*0.35
```

## Dark cinematic overlay (30% opacity):
```bash
ffmpeg -i input.mp4 -vf "drawbox=x=0:y=0:w=iw:h=ih:color=black@0.3:t=fill" output.mp4
```

## Audio fade out (last 2 seconds):
```bash
ffmpeg -i input.mp4 -af "afade=t=out:st=58:d=2" -c:v copy output.mp4
```

## Mix voiceover + background music:
```bash
ffmpeg -i video.mp4 -i voice.wav -i music.mp3 \
  -filter_complex "[1:a]afade=t=out:st=58:d=1[voice];[2:a]aloop=loop=-1:size=2e+09,atrim=duration=60,volume=0.12,afade=t=in:d=1,afade=t=out:st=58:d=1.5[music];[voice][music]amix=inputs=2:duration=first[aout]" \
  -map 0:v -map "[aout]" -c:v copy -c:a aac -b:a 192k output.mp4
```

## Colorkey avatar overlay (remove white background):
```bash
ffmpeg -i broll.mp4 -i avatar.mp4 -filter_complex \
  "[1:v]crop=290:300:430:600,colorkey=0xFFFFFF:0.22:0.10,scale=-1:h*0.55[avatar]; \
   [0:v][avatar]overlay=W-w-40:H-h-40[out]" \
  -map "[out]" -map 0:a output.mp4
```

## Loop B-roll to match audio duration:
```bash
ffmpeg -stream_loop -1 -i broll.mp4 -i audio.wav -c:v libx264 -c:a aac -shortest -movflags +faststart out.mp4
```

## Trim audio to max duration (60s):
```bash
ffmpeg -y -i audio.wav -t 60 -c copy trimmed.wav
```

## Progress bar overlay (teal, bottom):
```bash
drawbox=x=0:y=ih-4:w='iw*t/60':h=4:color=0x2DD4BF:t=fill
```

## Full composition (B-roll + dark overlay + avatar + captions + audio):
```bash
ffmpeg -stream_loop -1 -i broll.mp4 -i avatar.mp4 -i voice.wav \
  -filter_complex \
  "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[bg]; \
   [bg]drawbox=x=0:y=0:w=iw:h=ih:color=black@0.3:t=fill[bg_dim]; \
   [1:v]crop=290:300:430:600,colorkey=0xFFFFFF:0.22:0.10,scale=-1:1056[avatar]; \
   [bg_dim][avatar]overlay=W-w-40:H-h-40[composed]" \
  -map "[composed]" -map 2:a \
  -c:v libx264 -preset medium -crf 18 \
  -c:a aac -b:a 192k -movflags +faststart output.mp4
```
