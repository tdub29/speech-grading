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


def _inside_face(face_lms, hand) -> bool:
    """True for the hand model's false positive on a face (seen on real video): the
    wrist and at least 75% of the hand landmarks sit inside the face box. A real
    self-touch keeps the wrist below or beside the face.
    ponytail: a palm flat over the whole face with the wrist at the chin is dropped too."""
    pts = face_lms.values() if isinstance(face_lms, dict) else face_lms
    xs, ys = [p.x for p in pts], [p.y for p in pts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    inside = [x0 <= p.x <= x1 and y0 <= p.y <= y1 for p in hand]
    return inside[0] and sum(inside) >= 0.75 * len(inside)


def _face_crops(w: int, h: int, box):
    """Crops to retry when the full frame finds no face (small or distant face).
    Last known face box first, else a 3x3 grid of half-size squares."""
    if box:
        yield box
        return
    s = min(w, h) // 2
    for y in (0, (h - s) // 2, h - s):
        for x in (0, (w - s) // 2, w - s):
            yield (x, y, s, s)


def _box_around(lms, w: int, h: int):
    """Square crop 3x the face size around landmarks (full-frame normalised)."""
    xs, ys = [p.x * w for p in lms], [p.y * h for p in lms]
    side = int(min(max(3 * max(max(xs) - min(xs), max(ys) - min(ys)), 64), w, h))
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    x = int(min(max(cx - side / 2, 0), w - side))
    y = int(min(max(cy - side / 2, 0), h - side))
    return (x, y, side, side)


class _Pt:
    __slots__ = ("x", "y", "z")

    def __init__(self, x, y, z=0.0):
        self.x, self.y, self.z = x, y, z


def hand_face_dist(face_lms, hands, aspect: float = 1.0) -> float | None:
    """Min hand-landmark to nose/chin distance, normalised by face size.

    Landmarks are normalised per axis, so x is scaled by width/height (`aspect`) to get
    square pixels. Face size is max(width, height) so a head turn (width shrinks) does not
    inflate the distance. ponytail: 2D only; a hand in front of the face at depth still counts.
    """
    hands = [h for h in hands if not _inside_face(face_lms, h)]
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
    # IMAGE mode: crops move between frames, so video tracking would be misled.
    face_crop = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
        base_options=mpt.BaseOptions(model_asset_path=str(md / MODELS[0])),
        running_mode=vision.RunningMode.IMAGE, output_face_blendshapes=True,
        output_facial_transformation_matrixes=True, num_faces=1))
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise VisualUnavailable(f"cannot open video: {path}")
    frames, next_t, step = [], 0.0, 1.0 / fps
    last_ms, idx, box, n = -1, -1, None, 0
    native_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    try:
        while True:
            if not cap.grab():  # skipped frames still decode (FFmpeg) but skip retrieve + colour convert
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
            n += 1
            lms = fr.face_landmarks[0] if fr.face_landmarks else None
            if lms is None and (box or n % 10 == 1):  # ponytail: grid scan ~1/s, crop tracking between
                H, W = bgr.shape[:2]
                for x, y, cw, ch in _face_crops(W, H, box):
                    sub = cv2.cvtColor(bgr[y:y + ch, x:x + cw], cv2.COLOR_BGR2RGB)
                    cr = face_crop.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=sub.copy()))
                    if cr.face_landmarks:
                        fr = cr
                        lms = [_Pt((x + p.x * cw) / W, (y + p.y * ch) / H, p.z) for p in cr.face_landmarks[0]]
                        break
            if lms is not None:
                box = _box_around(lms, *bgr.shape[1::-1])
            else:
                box = None
            row = dict(t=t, smile=None, brow_raise=None, brow_furrow=None, jaw_open=None,
                       gaze_off=None, pitch_deg=None, hand_face_dist=None,
                       face_visible=lms is not None)
            if lms is not None:
                blend = {c.category_name: c.score for c in (fr.face_blendshapes or [[]])[0]}
                m = fr.facial_transformation_matrixes[0] if fr.facial_transformation_matrixes else None
                row.update(face_features(lms, blend, m))
                row["hand_face_dist"] = hand_face_dist(lms, hr.hand_landmarks,
                                                       aspect=bgr.shape[1] / bgr.shape[0])
            frames.append(row)
    finally:
        cap.release()
        face.close()
        face_crop.close()
        hand.close()
    return frames
