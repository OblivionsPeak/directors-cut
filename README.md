# Director's Cut

**Automatic highlight reels from iRacing replays** — built for the Operation
Motorsport eMotorsport community.

Open a replay in iRacing, press **Scan**, review the highlights it found,
press **Record** — walk away and come back to `highlights.mp4`.

## How it works

1. **Scan pass** — plays your replay at 16× while reading every car's position,
   gaps, and track state through the local iRacing SDK. Detects overtakes that
   stick, offs/spins, sustained nose-to-tail battles, and the finish.
2. **You pick** — review the list, untick anything boring, choose focus:
   **whole field** (league broadcast recap) or **one driver** (personal reel).
3. **Director pass** — seeks to each moment, aims a fitting TV/chase camera at
   the right car, plays it in real time while recording.
4. **Cut pass** — bundled ffmpeg normalizes the clips, burns lap/label title
   bars, and concatenates the reel into `Videos\DirectorsCut\`.

## Setup

- **Download `DirectorsCut.exe`** from Releases, run it — your browser opens.
- Recording works two ways (pick in the UI):
  - **OBS Studio** (recommended): in OBS enable Tools → WebSocket Server
    Settings → Enable. Set OBS to record your iRacing screen.
  - **iRacing built-in recorder**: enable video capture in iRacing
    (Options → Misc). Clips land in `Documents\iRacing\videos`.
- No iRacing web API access is needed — everything uses the **local SDK**
  built into the sim (the same interface every overlay uses). Unaffected by
  /data API availability.

## Notes

- Don't touch the sim while it scans/records — the tool is driving.
- A 1-hour race scans in ~4 minutes at 16×. Recording takes real time
  (sum of the clip lengths).
- 100% local. No accounts, nothing uploaded.

## From source

```bat
pip install -r requirements.txt
python app.py            # UI at http://localhost:4795
python tests\test_events.py   # highlight-detection unit tests
```

## Build the EXE

```bat
build.bat
```
