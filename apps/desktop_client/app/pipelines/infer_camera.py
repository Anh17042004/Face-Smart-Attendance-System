from datetime import datetime

import cv2
import numpy as np

from app.core.attendance_logic import AttendanceDecisionEngine
from app.core.settings import (
    BACKEND_BASE_URL,
    CAMERA_INDEX,
    COOLDOWN_SECONDS,
    DEFAULT_ATTENDANCE_TYPE,
    DEVICE_CODE,
    IDENTITY_VOTE_MIN_COUNT,
    IDENTITY_VOTE_WINDOW_SIZE,
    LIVENESS_THRESHOLD,
    LOG_PATH,
    MATCH_THRESHOLD,
    SPOOF_ALERT_COUNT,
    SPOOF_WINDOW_SIZE,
    SYNC_TIMEOUT_SECONDS,
)
from app.services.backend_sync import BackendSyncClient
from app.services.event_logger import EventLogger
from app.vision.face_utils import (
    align_face,
    anti_spoof_score,
    detect_faces,
    draw_face,
    extract_embedding,
    load_models,
)


def run_attendance(stop_on_accept: bool = False, models=None):
    logger = EventLogger(LOG_PATH)
    decision = AttendanceDecisionEngine(
        liveness_threshold=LIVENESS_THRESHOLD,
        spoof_window_size=SPOOF_WINDOW_SIZE,
        spoof_alert_count=SPOOF_ALERT_COUNT,
        vote_window_size=IDENTITY_VOTE_WINDOW_SIZE,
        vote_min_count=IDENTITY_VOTE_MIN_COUNT,
        cooldown_seconds=COOLDOWN_SECONDS,
    )
    sync_client = BackendSyncClient(
        base_url=BACKEND_BASE_URL,
        timeout_seconds=SYNC_TIMEOUT_SECONDS,
    )

    if not sync_client.check_online():
        print("[ERR] Khong ket noi duoc backend. Khong the cham cong.")
        return {"error": "network_offline"}

    if models is None:
        print("[INFO] Loading models...")
        detector, liveness, arcface = load_models(verbose=False)
    else:
        detector, liveness, arcface = models

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print(f"[ERR] Khong mo duoc camera {CAMERA_INDEX}")
        return {"error": "camera_error"}

    print("[INFO] Start infer... Bam Q de thoat")
    collected_embeddings: list[list[float]] = []
    last_vote_info = {
        "vote_count": 0,
        "required": IDENTITY_VOTE_MIN_COUNT,
        "window_size": IDENTITY_VOTE_WINDOW_SIZE,
    }

    while True:
        ok, frame = cap.read()
        if not ok:
            print("[ERR] Khong doc duoc frame")
            break

        faces = detect_faces(frame, detector, conf_thres=0.6)
        if faces:
            best = faces[0]
            live = anti_spoof_score(frame, best["bbox"], liveness, expansion=1.5)
            spoof_info = decision.on_spoof_check(live)
            if spoof_info.get("triggered"):
                record = logger.log(
                    "SPOOF_ALERT",
                    message="khuon mat gia mao",
                    spoof_frames=spoof_info["spoof_frames"],
                    window_size=spoof_info["window_size"],
                    liveness_score=round(float(live), 4),
                )
                print(f"[LOG] {record}")

            if live >= LIVENESS_THRESHOLD:
                aligned = align_face(frame, best["landmarks"])
                emb = extract_embedding(aligned, arcface) if aligned is not None else None
                if emb is None:
                    collected_embeddings.clear()
                    decision.reset_tracking()
                    cv2.imshow("Infer Camera", frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord("q"):
                        break
                    continue

                collected_embeddings.append(np.asarray(emb, dtype=np.float32).astype(float).tolist())

                name = "collecting"
                user_name = None
                score = 0.0
                identity_info = {
                    "accepted": False,
                    "cooldown": False,
                    "identity": None,
                    "similarity": 0.0,
                }

                if len(collected_embeddings) >= IDENTITY_VOTE_WINDOW_SIZE:
                    ok_match, match_data = sync_client.match_embeddings_batch(
                        embeddings=collected_embeddings,
                        threshold=MATCH_THRESHOLD,
                        min_vote_count=IDENTITY_VOTE_MIN_COUNT,
                    )
                    collected_embeddings.clear()
                    if not ok_match:
                        cap.release()
                        cv2.destroyAllWindows()
                        print(f"[ERR] Loi ket noi recognition API: {match_data.get('error', 'unknown')}.")
                        return {"error": "network_error", "detail": match_data.get("error", "unknown")}

                    vote_count = int(match_data.get("vote_count", 0))
                    total_frames = int(match_data.get("total_frames", IDENTITY_VOTE_WINDOW_SIZE))
                    last_vote_info = {
                        "vote_count": vote_count,
                        "required": IDENTITY_VOTE_MIN_COUNT,
                        "window_size": total_frames,
                    }

                    name = match_data.get("employee_code") if match_data.get("matched") else "unknown"
                    user_name = match_data.get("user_name") if match_data.get("matched") else None
                    score = float(match_data.get("similarity", 0.0))
                    identity_info = decision.on_identity(name, score)
                else:
                    last_vote_info = {
                        "vote_count": len(collected_embeddings),
                        "required": IDENTITY_VOTE_MIN_COUNT,
                        "window_size": IDENTITY_VOTE_WINDOW_SIZE,
                    }

                if name == "unknown":
                    record = logger.log(
                        "UNKNOWN",
                        name=name,
                        similarity=round(float(score), 4),
                        liveness_score=round(float(live), 4),
                    )
                    print(f"[LOG] {record}")

                if identity_info.get("accepted"):
                    accepted_at = datetime.now()
                    record = logger.log(
                        "ACCEPT",
                        name=identity_info["identity"],
                        similarity=round(float(identity_info["similarity"]), 4),
                        liveness_score=round(float(live), 4),
                        vote_count=last_vote_info["vote_count"],
                    )
                    print(f"[LOG] {record}")

                    payload = {
                        "type": DEFAULT_ATTENDANCE_TYPE,
                        "employee_code": identity_info["identity"],
                        "similarity": round(float(identity_info["similarity"]), 4),
                        "liveness_score": round(float(live), 4),
                        "device_id": DEVICE_CODE,
                        "metadata": {
                            "source": "desktop_client",
                            "event": "ACCEPT",
                            "user_name": user_name,
                        },
                    }
                    ok, reason = sync_client.send_event(payload)
                    if ok:
                        print("[SYNC] ACCEPT sent to backend")
                        saved_event = reason if isinstance(reason, dict) else {}
                    else:
                        cap.release()
                        cv2.destroyAllWindows()
                        print(f"[ERR] Khong gui duoc attendance event: {reason}")
                        return {"error": "network_error", "detail": reason}

                    if stop_on_accept:
                        cap.release()
                        cv2.destroyAllWindows()
                        return {
                            "employee_code": identity_info["identity"],
                            "user_name": user_name,
                            "attendance_type": str(saved_event.get("type", DEFAULT_ATTENDANCE_TYPE)).lower(),
                            "similarity": round(float(identity_info["similarity"]), 4),
                            "liveness_score": round(float(live), 4),
                            "accepted_at": accepted_at,
                        }

                label = f"{name} | sim={score:.3f} | live={live:.3f}"
                color = (0, 255, 0) if name not in {"unknown", "collecting"} else (0, 255, 255)
                draw_face(frame, best, label=label, color=color)

                cv2.putText(
                    frame,
                    f"vote={last_vote_info['vote_count']}/{last_vote_info['required']} (win={last_vote_info['window_size']})",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 0),
                    2,
                )
                if identity_info.get("cooldown"):
                    cv2.putText(
                        frame,
                        "COOLDOWN",
                        (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 165, 255),
                        2,
                    )
            else:
                collected_embeddings.clear()
                decision.reset_tracking()
                draw_face(frame, best, label=f"SPOOF? live={live:.3f}", color=(0, 0, 255))
        else:
            collected_embeddings.clear()
            decision.no_face()

        cv2.imshow("Infer Camera", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    return None


def main():
    run_attendance(stop_on_accept=False)
