import json
import os
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort


MODEL_DIR = Path(__file__).resolve().parents[2] / "models"
DETECTOR_PATH = MODEL_DIR / "FaceDetector.onnx"
LIVENESS_PATH = MODEL_DIR / "best_model_anti_spoofing.onnx"
ARCFACE_PATH = MODEL_DIR / "arcface.onnx"

ARCFACE_TEMPLATE = np.array(
    [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ],
    dtype=np.float32,
)


def create_session(model_path: Path):
    if not model_path.is_file():
        raise FileNotFoundError(f"Khong tim thay model: {model_path}")

    providers = ["CPUExecutionProvider"]
    sess = ort.InferenceSession(str(model_path), providers=providers)
    input_name = sess.get_inputs()[0].name
    output_names = [o.name for o in sess.get_outputs()]
    input_shape = sess.get_inputs()[0].shape

    return {
        "session": sess,
        "input_name": input_name,
        "output_names": output_names,
        "input_shape": input_shape,
    }


def load_models(verbose=True):
    detector = create_session(DETECTOR_PATH)
    liveness = create_session(LIVENESS_PATH)
    arcface = create_session(ARCFACE_PATH)

    if verbose:
        print("\n[Detector]")
        print("input:", detector["input_name"], detector["input_shape"])
        print("outputs:", detector["output_names"])

        print("\n[Liveness]")
        print("input:", liveness["input_name"], liveness["input_shape"])
        print("outputs:", liveness["output_names"])

        print("\n[ArcFace]")
        print("input:", arcface["input_name"], arcface["input_shape"])
        print("outputs:", arcface["output_names"])

    return detector, liveness, arcface


def softmax(x, axis=-1):
    x = x - np.max(x, axis=axis, keepdims=True)
    e = np.exp(x)
    return e / np.sum(e, axis=axis, keepdims=True)


def norm_embedding(emb):
    emb = emb.astype(np.float32)
    n = np.linalg.norm(emb)
    if n < 1e-8:
        return emb
    return emb / n


def cosine_similarity(a, b):
    return float(np.dot(norm_embedding(a), norm_embedding(b)))


def build_priors(image_h, image_w, min_sizes, steps, clip=False):
    priors = []
    for k, step in enumerate(steps):
        feature_h = int(np.ceil(image_h / step))
        feature_w = int(np.ceil(image_w / step))
        for i in range(feature_h):
            for j in range(feature_w):
                for min_size in min_sizes[k]:
                    s_kx = min_size / image_w
                    s_ky = min_size / image_h
                    cx = (j + 0.5) * step / image_w
                    cy = (i + 0.5) * step / image_h
                    priors.extend([cx, cy, s_kx, s_ky])
    priors = np.array(priors, dtype=np.float32).reshape(-1, 4)
    if clip:
        priors = np.clip(priors, 0.0, 1.0)
    return priors


def decode_boxes(loc, priors, variances=(0.1, 0.2)):
    boxes = np.concatenate(
        [
            priors[:, :2] + loc[:, :2] * variances[0] * priors[:, 2:],
            priors[:, 2:] * np.exp(loc[:, 2:] * variances[1]),
        ],
        axis=1,
    )
    boxes[:, :2] -= boxes[:, 2:] / 2
    boxes[:, 2:] += boxes[:, :2]
    return boxes


def decode_landmarks(pre, priors, variances=(0.1, 0.2)):
    landms = np.concatenate(
        [
            priors[:, :2] + pre[:, 0:2] * variances[0] * priors[:, 2:],
            priors[:, :2] + pre[:, 2:4] * variances[0] * priors[:, 2:],
            priors[:, :2] + pre[:, 4:6] * variances[0] * priors[:, 2:],
            priors[:, :2] + pre[:, 6:8] * variances[0] * priors[:, 2:],
            priors[:, :2] + pre[:, 8:10] * variances[0] * priors[:, 2:],
        ],
        axis=1,
    )
    return landms


def _split_detector_outputs(outputs):
    bbox, conf, landm = None, None, None
    for out in outputs:
        if out.ndim != 3:
            continue
        c = out.shape[-1]
        if c == 4:
            bbox = out
        elif c == 2:
            conf = out
        elif c == 10:
            landm = out
    if bbox is None or conf is None or landm is None:
        raise RuntimeError("Khong map duoc outputs detector (bbox/conf/landmark)")
    return bbox, conf, landm


def detect_faces(frame_bgr, detector, conf_thres=0.6, nms_thres=0.4):
    h, w = frame_bgr.shape[:2]
    img = cv2.resize(frame_bgr, (640, 640), interpolation=cv2.INTER_LINEAR)
    img = img.astype(np.float32)
    img -= (104, 117, 123)
    img = img.transpose(2, 0, 1)[None, ...]

    sess = detector["session"]
    outputs = sess.run(detector["output_names"], {detector["input_name"]: img})
    loc, conf, landm = _split_detector_outputs(outputs)

    loc = loc.squeeze(0)
    conf = conf.squeeze(0)
    landm = landm.squeeze(0)

    priors = build_priors(
        640,
        640,
        min_sizes=[[16, 32], [64, 128], [256, 512]],
        steps=[8, 16, 32],
        clip=False,
    )

    boxes = decode_boxes(loc, priors)
    landms = decode_landmarks(landm, priors)

    scores = conf[:, 1]
    keep = np.where(scores > conf_thres)[0]
    if keep.size == 0:
        return []

    boxes = boxes[keep]
    landms = landms[keep]
    scores = scores[keep]

    boxes_xyxy = boxes.copy()
    boxes_xyxy[:, [0, 2]] *= w
    boxes_xyxy[:, [1, 3]] *= h

    landms_xy = landms.copy().reshape(-1, 5, 2)
    landms_xy[:, :, 0] *= w
    landms_xy[:, :, 1] *= h

    nms_boxes = np.concatenate([boxes_xyxy, scores[:, None]], axis=1).astype(np.float32)
    keep_idx = cv2.dnn.NMSBoxes(
        bboxes=[
            [
                float(b[0]),
                float(b[1]),
                float(max(1.0, b[2] - b[0])),
                float(max(1.0, b[3] - b[1])),
            ]
            for b in nms_boxes
        ],
        scores=[float(s) for s in scores],
        score_threshold=conf_thres,
        nms_threshold=nms_thres,
    )

    if keep_idx is None or len(keep_idx) == 0:
        return []

    if isinstance(keep_idx, np.ndarray):
        keep_idx = keep_idx.flatten().tolist()
    else:
        keep_idx = [int(k[0]) if isinstance(k, (list, tuple, np.ndarray)) else int(k) for k in keep_idx]

    results = []
    for i in keep_idx:
        b = boxes_xyxy[i]
        lm = landms_xy[i]
        x1, y1, x2, y2 = [int(round(v)) for v in b]
        x1 = max(0, min(x1, w - 1))
        y1 = max(0, min(y1, h - 1))
        x2 = max(0, min(x2, w - 1))
        y2 = max(0, min(y2, h - 1))
        if x2 <= x1 or y2 <= y1:
            continue
        results.append(
            {
                "bbox": (x1, y1, x2, y2),
                "score": float(scores[i]),
                "landmarks": lm.astype(np.float32),
            }
        )

    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def crop_face_expanded_reflect(frame_bgr, bbox, expansion=1.5):
    h, w = frame_bgr.shape[:2]
    x1, y1, x2, y2 = bbox

    bw = max(1.0, float(x2 - x1))
    bh = max(1.0, float(y2 - y1))
    cx = x1 + bw / 2.0
    cy = y1 + bh / 2.0
    side = max(bw, bh) * expansion / 2.0

    ex1 = int(round(cx - side))
    ey1 = int(round(cy - side))
    ex2 = int(round(cx + side))
    ey2 = int(round(cy + side))

    pad_top = max(0, -ey1)
    pad_bottom = max(0, ey2 - h)
    pad_left = max(0, -ex1)
    pad_right = max(0, ex2 - w)

    if any([pad_top, pad_bottom, pad_left, pad_right]):
        frame_bgr = cv2.copyMakeBorder(
            frame_bgr,
            pad_top,
            pad_bottom,
            pad_left,
            pad_right,
            borderType=cv2.BORDER_REFLECT_101,
        )
        ex1 += pad_left
        ex2 += pad_left
        ey1 += pad_top
        ey2 += pad_top

    if ex2 <= ex1 or ey2 <= ey1:
        return None

    return frame_bgr[ey1:ey2, ex1:ex2].copy()


def anti_spoof_score(frame_bgr, bbox, liveness, expansion=1.5):
    face_bgr = crop_face_expanded_reflect(frame_bgr, bbox, expansion=expansion)
    if face_bgr is None or face_bgr.size == 0:
        return 0.0

    img = cv2.resize(face_bgr, (128, 128), interpolation=cv2.INTER_LINEAR)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    img = img.transpose(2, 0, 1)[None, ...]

    sess = liveness["session"]
    out = sess.run(liveness["output_names"], {liveness["input_name"]: img})[0]
    out = np.array(out)
    if out.ndim == 1:
        out = out[None, :]

    probs = softmax(out, axis=1)
    if probs.shape[1] == 1:
        return float(probs[0, 0])
    return float(probs[0, 0])


def align_face(frame_bgr, landmarks):
    src = np.array(landmarks, dtype=np.float32).reshape(5, 2)
    dst = ARCFACE_TEMPLATE.copy()
    m, _ = cv2.estimateAffinePartial2D(src, dst, method=cv2.LMEDS)
    if m is None:
        return None
    aligned = cv2.warpAffine(frame_bgr, m, (112, 112), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return aligned


def extract_embedding(aligned_bgr, arcface):
    if aligned_bgr is None or aligned_bgr.size == 0:
        return None

    img = cv2.cvtColor(aligned_bgr, cv2.COLOR_BGR2RGB).astype(np.float32)
    img = (img / 255.0 - 0.5) / 0.5
    img = img.transpose(2, 0, 1)[None, ...]

    sess = arcface["session"]
    out = sess.run(arcface["output_names"], {arcface["input_name"]: img})[0]
    emb = out.squeeze().astype(np.float32)
    return norm_embedding(emb)


def draw_face(frame_bgr, result, label=None, color=(0, 255, 0)):
    x1, y1, x2, y2 = result["bbox"]
    cv2.rectangle(frame_bgr, (x1, y1), (x2, y2), color, 2)
    if label:
        cv2.putText(frame_bgr, label, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

    lms = result.get("landmarks")
    if lms is not None:
        for p in lms:
            cv2.circle(frame_bgr, (int(p[0]), int(p[1])), 2, (255, 255, 0), -1)


def load_gallery(gallery_path):
    p = Path(gallery_path)
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_gallery(gallery_path, gallery):
    p = Path(gallery_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(gallery, f, ensure_ascii=False, indent=2)


def upsert_person_embedding(gallery, person_name, embedding):
    person = gallery.get(person_name, {"embeddings": [], "mean_embedding": None})
    person["embeddings"].append(embedding.tolist())
    arr = np.array(person["embeddings"], dtype=np.float32)
    mean_emb = norm_embedding(arr.mean(axis=0))
    person["mean_embedding"] = mean_emb.tolist()
    gallery[person_name] = person


def match_employee(embedding, gallery, threshold=0.4):
    if embedding is None or not gallery:
        return "unknown", -1.0

    best_name = "unknown"
    best_score = -1.0
    for name, data in gallery.items():
        mean_emb = np.array(data["mean_embedding"], dtype=np.float32)
        score = cosine_similarity(embedding, mean_emb)
        if score > best_score:
            best_score = score
            best_name = name

    if best_score < threshold:
        return "unknown", best_score
    return best_name, best_score
