# Dashboard design: "the viewfinder"

## Concept card
- **Idea:** you look through the camera that tracks the ball (`vision/vision.py`), and the numbers are its on-screen display.
- **Metaphor:** a camera viewfinder: corner brackets, a REC light, a timecode, a focus box and an info bar.
- **Signature:** the plate view (`app/components/PlateView.tsx`).
  - Four corner brackets frame the image.
  - An amber focus box follows the ball with its x and y. When the error is under 5 mm, the box closes in and says `LOCK`.
  - An amber reticle marks the setpoint. A dashed amber line labelled `e` (the error the PID drives to zero) joins the ball to it.
  - The ball leaves a fading trail, like a long exposure.
  - Top left: `REC` (blinking) when data comes in. Top right: the timecode from `t_ms`. Bottom: the info bar with X, Y, setpoint and tilt.
- **Emotion:** focused and quiet, like looking through a good camera.
- **Motion verb:** "lock on".
  - The corner brackets pull in once when a page opens (500 ms).
  - The REC dot blinks in 1 s steps. The focus box follows the ball sample by sample, with no CSS transition (it would lag behind 50 samples per second).
- **Screenshot:** the dark plate with the amber focus box locked on the ball.

## Palette (`app/globals.css`)
| Token | Hex | Role |
|---|---|---|
| `--bg` | `#0a0b0b` | page |
| `--panel` | `#121414` | viewfinder, charts, terminals |
| `--ink` | `#ecede8` | text, ball, ball line |
| `--muted` | `#8c918b` | labels |
| `--line` | `#232726` | thin lines, grid |
| `--focus` | `#ffb020` | amber: setpoint, error, focus box, active tab. Amber always means "target" |
| `--rec` | `#ff3b30` | REC dot and error messages only |

## Type (all from Google via `next/font`)
- **Barlow Condensed** for page titles (`.display`), tabs, labels (`.label`) and buttons (`.btn`), like the markings on a camera body.
- **Barlow** for body text.
- **Martian Mono** for every number, timecode and command (tabular numbers).

## Layout
- One column with a 1440 px maximum and 32 px side gutters from `sm` up.
- On phones there is no frame: the viewfinder, charts and panels run edge to edge (`-mx-4`), and text keeps a 16 px gutter.
- Live: viewfinder in 8 of 12 columns, the X and Y charts in the other 4.
- Runs ("playback"): the clip list on the left (selected clip in amber with ▶), then the X/Y switch, the whole-run chart and the step table.
- Setup: numbered steps with terminals; a "what runs where" line on the side.
- 404: an empty viewfinder that says `NO SIGNAL`.

## Shape and motion
- Square corners everywhere, no shadows. A soft glow only on the ball and the chart lines (`.glow`).
- One ease (`--ease`). Motion is CSS only, and all of it is off under `prefers-reduced-motion`.

## Not this
- No slate cards with neon accents, no sidebar, no gradients, no glass.
- Amber is never decoration: if it is amber, it is the target.
- Red is only for REC and errors.
