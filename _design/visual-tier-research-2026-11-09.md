# Visual confidence / body-language tier for orator: prior work and research (2026-11-09)

## Has an agent started this?
No. Checked: agent-claim list (no lease), dashboard queue (no match), git log (no match), job-search inbox (no match), speech-grading code.
Only trace: `speech-grading/speech_grading/config.py:76`, `enable_video: bool = False  # visual tier (needs video + mediapipe/l2cs)`. A flag with no implementation behind it. Nothing else in `speech_grading/` references video. `l2cs` is a gaze model name the original author had in mind.
Reusable adjacent code: `driver-drowsiness/prototype/perclos.py` and `replay.py` (face and eye landmark pipeline, eyelid closure over time). Not verified for reuse here.

## Prior art found (web, 2026-11-09)
- SmartSpeaking (github.com/AbdulMuhaiminKhan/smart-speaking): closest match. Local, uploads up to 15 min, MediaPipe Pose/Face/Hand landmarkers, timestamped issues, YAML scoring rules. Needs Docker or Python 3.12 + Ollama + about 3 GB models. 1 star, 9 commits, license not stated on the page. Its own limits: glasses, lighting, camera angle hurt tracking; uploads cannot calibrate for looking at a screen below the webcam; laptop webcams crop hands.
- VisionSpeak AI (github.com/Tesfazion/visionspeak-ai): on-device MediaPipe, lens time, gaze breaks, torso lean, gestures per minute, composite confidence score. Mostly live webcam; upload support unconfirmed.
- Human-Posture-Analysis (github.com/Dubow/Human-Posture-Analysis): rule-based posture and gesture on recorded video; author calls some rules experimental.
- GestureLens (arxiv.org/abs/2204.08894): academic gesture analysis of presentation videos for coaches.
- Audio-Visual Evaluation of Oratory Skills (arxiv.org/abs/2110.01367): academic. Could not read the PDF text; abstract-level details unverified.
None is mature. All are heuristic geometry over MediaPipe landmarks. Nobody ships validated "confidence" labels.

## What MediaPipe gives (per search of official docs, unverified in code)
- FaceLandmarker: 478 landmarks, optional blendshapes (52, ARKit style names, third-party claim), optional facial transformation matrix (head pose).
- No native gaze output and no self-touch output found. Both need custom logic over landmarks (iris landmarks for gaze; hand-to-face landmark distance for touch).
- Package version reported 0.10.35 (May 2026), third-party page.

## Science caveat (matches your pasted source)
Searches found weak and context dependent links between nonverbal cues and deception or nervousness (DePaulo 2003 review; a 2024 Frontiers in Psychology mock-crime study found more self-adaptors and gaze aversion in liars, small sample). Found nothing on whether self-touch lowers perceived speaker confidence. So the tool should report observable behavior counts and rates, not "insecurity" verdicts.

## Which pasted cues are measurable
| Cue | Feasibility | Method |
|---|---|---|
| Face touching (nose, mouth, hair, jaw, neck) | High if hands in frame | hand landmark within threshold of face landmark regions, duration and count |
| Hands at chest level | High | wrist height vs shoulder and hip |
| Head level, chin not up | Medium to high | head pitch and roll from transformation matrix |
| Eye contact vs glances | Medium | iris offset to camera; fails if notes or screen below lens |
| Check reactions after each sentence | Medium | gaze shift aligned to sentence ends from the ASR timestamps orator already makes |
| Smile after statement | Medium | smile blendshapes aligned to sentence ends |
| Lip pressing or biting, jaw clench | Low to medium | mouth blendshapes; noisy |
| Brow raise, furrow, wide eyes | Medium | brow and eyelid blendshapes vs speaker's own baseline |
| Pause with steady gaze before answering | Medium | needs Q and A segmentation; gaze steadiness plus silence gap |
| Chin stroking slow vs repeated | Low | needs gesture classification; count and cadence only |
| "Calm and engaged, not emotionless" | Low | no validated label; use variance of expression vs baseline as a descriptive stat |

## Recommended build (key-free, local, fits orator)
1. Wire the existing `enable_video` flag to a new `analysis/visual.py` using MediaPipe tasks (Face, Pose, Hand) on sampled frames (10 fps).
2. Per-speaker baseline in the first 30 s; score deviations, not absolutes.
3. Align events to orator's sentence timestamps (sentence end smile, gaze check, face touch after a question).
4. Output counts, rates and time-coded clips, no "insecure" labels. Add data quality gates: face visible %, hands visible %, lighting, glasses flag; skip a cue when its gate fails.
5. Reuse orator report schema as a new dimension group; reuse `driver-drowsiness` eyelid code if it checks out.
Open questions for Trevor: input is Zoom or phone recordings? hands usually in frame? score or descriptive report only?
