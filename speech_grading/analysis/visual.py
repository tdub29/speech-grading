"""Video -> per-frame feature dicts for `visual_events` (MediaPipe Face + Hand).

Samples by timestamp, so variable fps, phone VFR and any resolution work.
Models (.task files) are not bundled: put face_landmarker.task and
hand_landmarker.task in `models_dir` (default ~/.orator/models or $ORATOR_MODELS).
Missing deps or models raise VisualUnavailable; the pipeline then skips the tier.
"""
from __future__ import annotations

import math
import os
from pathlib import Path

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
MODELS = ("face_landmarker.task", "hand_landmarker.task")
_NOSE, _CHIN, _LEFT_FACE, _RIGHT_FACE = 1, 152, 234, 454  # FaceMesh indices


class VisualUnavailable(RuntimeError):
    pass


def is_video(path: str | Path) -> bool:
    return Path(path).suffix.lower() in VIDEO_EXT


def models_dir(path: str | Path | None = None) -> Path:
    return Path(path or os.environ.get("ORATOR_MODELS") or Path.home() / ".orator" / "models")


def _bs(blend: dict, *names: str) -> float | None:
    vals = [blend[n] for n in names if n in blend]
    return sum(vals) / len(vals) if vals else None


def face_features(lms, blend: dict, matrix) -> dict:
    """One face -> smile/brow/jaw/gaze/pitch. `lms` has .x/.y; `blend` maps name->score."""
    gaze = [_bs(blend, f"eyeLook{d}Left", f"eyeLook{d}Right") for d in ("Out", "In", "Up", "Down")]
    gaze = [g for g in gaze if g is not None]
    pitch = None
    if matrix is not None:
        # MediaPipe metric 3D space: right-handed, camera looks down -Z, Y is up, face looks towards +Z.
        # Chin up tilts head back (negative rotation around X), so -matrix[2][1] > 0 and pitch_deg is positive.
        pitch = math.degrees(math.atan2(-matrix[2][1], matrix[2][2]))
    return dict(
        smile=_bs(blend, "mouthSmileLeft", "mouthSmileRight"),
        brow_raise=_bs(blend, "browInnerUp", "browOuterUpLeft", "browOuterUpRight"),
        brow_furrow=_bs(blend, "browDownLeft", "browDownRight"),
        jaw_open=_bs(blend, "jawOpen"),
        gaze_off=max(gaze) if gaze else None,
        pitch_deg=pitch,
    )


def hand_face_dist(face_lms, hands) -> float | None:
    """Min hand-landmark to nose/chin distance, normalised by face width."""
    if not hands:
        return None
    w = math.dist((face_lms[_LEFT_FACE].x, face_lms[_LEFT_FACE].y),
                  (face_lms[_RIGHT_FACE].x, face_lms[_RIGHT_FACE].y)) or 1e-6
    pts = [(face_lms[_NOSE].x, face_lms[_NOSE].y), (face_lms[_CHIN].x, face_lms[_CHIN].y)]
    return min(math.dist((p.x, p.y), q) for h in hands for p in h for q in pts) / w


def extract_frames(path: str | Path, fps: float = 10.0, models: str | Path | None = None) -> list[dict]:
    try:
        import cv2
        import mediapipe as mp
        from mediapipe.tasks import python as mpt
        from mediapipe.tasks.python import vision
    except ImportError as e:
        raise VisualUnavailable(f"video deps missing: {e}") from e
    md = models_dir(models)
    missing = [m for m in MODELS if not (md / m).is_file()]
    if missing:
        raise VisualUnavailable(f"missing model files in {md}: {', '.join(missing)}")
    face = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
        base_options=mpt.BaseOptions(model_asset_path=str(md / MODELS[0])),
        running_mode=vision.RunningMode.VIDEO, output_face_blendshapes=True,
        output_facial_transformation_matrixes=True, num_faces=1))
    hand = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
        base_options=mpt.BaseOptions(model_asset_path=str(md / MODELS[1])),
        running_mode=vision.RunningMode.VIDEO, num_hands=2))
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise VisualUnavailable(f"cannot open video: {path}")
    frames, next_t, step = [], 0.0, 1.0 / fps
    last_ms = -1
    try:
        while True:
            ok, bgr = cap.read()
            if not ok:
                break
            t = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            if t < next_t:
                continue
            next_t = t + step
            img = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
            ms = int(t * 1000)
            if ms <= last_ms:
                ms = last_ms + 1
            last_ms = ms
            fr, hr = face.detect_for_video(img, ms), hand.detect_for_video(img, ms)
            row = dict(t=t, smile=None, brow_raise=None, brow_furrow=None, jaw_open=None,
                       gaze_off=None, pitch_deg=None, hand_face_dist=None, wrist_y_rel=None,
                       face_visible=bool(fr.face_landmarks))
            if fr.face_landmarks:
                blend = {c.category_name: c.score for c in (fr.face_blendshapes or [[]])[0]}
                m = fr.facial_transformation_matrixes[0] if fr.facial_transformation_matrixes else None
                row.update(face_features(fr.face_landmarks[0], blend, m))
                row["hand_face_dist"] = hand_face_dist(fr.face_landmarks[0], hr.hand_landmarks)
            frames.append(row)
    finally:
        cap.release()
        face.close()
        hand.close()
    return frames
