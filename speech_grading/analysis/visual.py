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
_NOSE, _CHIN, _LEFT_FACE, _RIGHT_FACE, _TOP = 1, 152, 234, 454, 10  # FaceMesh indices


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
    # Pair blendshapes by gaze DIRECTION: looking to the subject's right is the right eye
    # looking out and the left eye looking in. Pairing Out-with-Out averaged opposite eyes.
    gaze = [_bs(blend, "eyeLookOutRight", "eyeLookInLeft"), _bs(blend, "eyeLookOutLeft", "eyeLookInRight"),
            _bs(blend, "eyeLookUpLeft", "eyeLookUpRight"), _bs(blend, "eyeLookDownLeft", "eyeLookDownRight")]
    gaze = [g for g in gaze if g is not None]
    pitch = None
    if matrix is not None and getattr(matrix, "size", 0) >= 16:  # empty array when no matrix
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


def hand_face_dist(face_lms, hands, aspect: float = 1.0) -> float | None:
    """Min hand-landmark to nose/chin distance, normalised by face size.

    Landmarks are normalised per axis, so x is scaled by width/height (`aspect`) to get
    square pixels. Face size is max(width, height) so a head turn (width shrinks) does not
    inflate the distance. ponytail: 2D only; a hand in front of the face at depth still counts.
    """
    if not hands:
        return None
    def xy(lm):
        return (lm.x * aspect, lm.y)
    size = max(math.dist(xy(face_lms[_LEFT_FACE]), xy(face_lms[_RIGHT_FACE])),
               math.dist(xy(face_lms[_TOP]), xy(face_lms[_CHIN]))) or 1e-6
    pts = [xy(face_lms[_NOSE]), xy(face_lms[_CHIN])]
    return min(math.dist(xy(p), q) for h in hands for p in h for q in pts) / size


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
    last_ms, idx = -1, -1
    native_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    try:
        while True:
            if not cap.grab():  # grab-only for skipped frames: no decode cost
                break
            idx += 1
            t = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            if t <= 0 and idx > 0:  # some containers never report a position
                t = idx / native_fps
            if t < next_t:
                continue
            ok, bgr = cap.retrieve()
            if not ok:
                continue  # one bad frame should not end the run
            next_t += step  # fixed grid: t + step drifts below the requested fps
            if next_t <= t:
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
                row["hand_face_dist"] = hand_face_dist(fr.face_landmarks[0], hr.hand_landmarks,
                                                       aspect=bgr.shape[1] / bgr.shape[0])
            frames.append(row)
    finally:
        cap.release()
        face.close()
        hand.close()
    return frames
