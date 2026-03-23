import cv2
import numpy as np

from app.core.settings import (
    BACKEND_BASE_URL,
    CAMERA_INDEX,
    ENROLL_NUM_SAMPLES,
    LIVENESS_THRESHOLD,
    SYNC_TIMEOUT_SECONDS,
)
from app.services.backend_sync import BackendSyncClient
from app.vision.face_utils import (
    align_face,
    anti_spoof_score,
    detect_faces,
    draw_face,
    extract_embedding,
    load_models,
)

def _ask_employee_code() -> str | None:
    code = input("Nhap ma nhan vien moi (vd: EMP001), de trong de huy: ").strip()
    if not code:
        print("[INFO] Huy dang ky nhan vien moi")
        return None
    return code


def _ask_employee_name() -> str | None:
    name = input("Nhap ten nhan vien (vd: Nguyen Van A), de trong de huy: ").strip()
    if not name:
        print("[INFO] Huy dang ky nhan vien moi")
        return None
    return name


def run_register_employee(
    employee_code: str | None = None,
    employee_name: str | None = None,
    num_samples: int = ENROLL_NUM_SAMPLES,
    models=None,
):
    person_code = employee_code or _ask_employee_code()
    if not person_code:
        return {"success": False, "reason": "cancelled", "employee_code": None, "captured": 0}

    person_name = employee_name or _ask_employee_name()
    if not person_name:
        return {
            "success": False,
            "reason": "cancelled",
            "employee_code": person_code,
            "employee_name": None,
            "captured": 0,
        }

    sync_client = BackendSyncClient(base_url=BACKEND_BASE_URL, timeout_seconds=SYNC_TIMEOUT_SECONDS)
    if not sync_client.check_online():
        return {
            "success": False,
            "reason": "network_error",
            "employee_code": person_code,
            "employee_name": person_name,
            "captured": 0,
        }

    camera_index = CAMERA_INDEX
    live_thres = LIVENESS_THRESHOLD

    if models is None:
        print("[INFO] Loading models...")
        detector, liveness, arcface = load_models(verbose=False)
    else:
        detector, liveness, arcface = models
    captured_embeddings: list[np.ndarray] = []

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"[ERR] Khong mo duoc camera {camera_index}")
        return {
            "success": False,
            "reason": "camera_error",
            "employee_code": person_code,
            "employee_name": person_name,
            "captured": 0,
        }

    captured = 0
    print("\nControls:")
    print("  C: chup 1 mau embedding neu frame hop le")
    print("  Q: thoat")

    while True:
        ok, frame = cap.read()
        if not ok:
            print("[ERR] Khong doc duoc frame tu camera")
            break

        faces = detect_faces(frame, detector, conf_thres=0.6)
        status = "Khong co mat"
        can_capture = False
        emb = None

        if faces:
            best = faces[0]
            live = anti_spoof_score(frame, best["bbox"], liveness, expansion=1.5)
            aligned = align_face(frame, best["landmarks"])
            emb = extract_embedding(aligned, arcface) if aligned is not None else None

            draw_face(frame, best, label=f"live={live:.3f}")
            if emb is not None and live >= live_thres:
                can_capture = True
                status = "Frame hop le - Bam C de luu"
            else:
                status = "Frame chua hop le"

        cv2.putText(
            frame,
            f"Enroll: {person_code} - {person_name} | {captured}/{num_samples}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),
            2,
        )
        cv2.putText(
            frame,
            status,
            (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (0, 255, 0) if can_capture else (0, 0, 255),
            2,
        )

        cv2.imshow("Enroll Camera", frame)
        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            break

        if key == ord("c") and can_capture:
            captured_embeddings.append(np.asarray(emb, dtype=np.float32))
            captured += 1
            print(f"[INFO] Da luu mau {captured}/{num_samples}")
            if captured >= num_samples:
                mean_emb = np.mean(np.stack(captured_embeddings, axis=0), axis=0)
                ok_enroll, enroll_data = sync_client.enroll_embedding(
                    employee_code=person_code,
                    user_name=person_name,
                    embedding=mean_emb.astype(float).tolist(),
                    model_version="arcface.onnx",
                )
                if not ok_enroll:
                    cap.release()
                    cv2.destroyAllWindows()
                    error_code = enroll_data.get("error") if isinstance(enroll_data, dict) else "unknown_error"
                    error_detail = enroll_data.get("detail") if isinstance(enroll_data, dict) else None
                    return {
                        "success": False,
                        "reason": "backend_error" if str(error_code).startswith("http_") else "network_error",
                        "detail": error_detail or error_code,
                        "employee_code": person_code,
                        "employee_name": person_name,
                        "captured": captured,
                    }

                print(f"[OK] Hoan tat enroll '{person_code} - {person_name}'.")
                cap.release()
                cv2.destroyAllWindows()
                return {
                    "success": True,
                    "reason": "completed",
                    "employee_code": person_code,
                    "employee_name": enroll_data.get("user_name", person_name),
                    "captured": captured,
                }

    cap.release()
    cv2.destroyAllWindows()

    return {
        "success": False,
        "reason": "incomplete",
        "employee_code": person_code,
        "employee_name": person_name,
        "captured": captured,
    }


def main():
    run_register_employee()
