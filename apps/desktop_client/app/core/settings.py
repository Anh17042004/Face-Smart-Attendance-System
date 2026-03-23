from pathlib import Path


# Thu muc goc cua ung dung desktop client.
BASE_DIR = Path(__file__).resolve().parents[2]

# Models
# Dat model duy nhat tai: apps/desktop_client/models
MODEL_DIR = BASE_DIR / "models"
DETECTOR_MODEL = MODEL_DIR / "retina_face.onnx"
LIVENESS_MODEL = MODEL_DIR / "anti_sproofing.onnx"
ARCFACE_MODEL = MODEL_DIR / "arcface.onnx"

# Data
# File log JSONL local de debug/audit su kien infer o phia client.
LOG_PATH = BASE_DIR / "logs" / "infer_events.jsonl"

# Camera
# Chi so camera OpenCV: 0=webcam mac dinh, 1/2=camera ngoai.
CAMERA_INDEX = 0
# So mau khuon mat hop le can thu trong qua trinh enroll.
ENROLL_NUM_SAMPLES = 5

# Backend sync
# URL goc cua backend cho health, recognition va attendance API.
BACKEND_BASE_URL = "http://127.0.0.1:8000"
# Ma thiet bi gui kem su kien cham cong.
DEVICE_CODE = "laptop-001"
# Loai su kien cham cong gui len backend.
# Dung "auto" de backend tu quyet dinh checkin/checkout.
DEFAULT_ATTENDANCE_TYPE = "auto"
# Thoi gian timeout HTTP (giay) khi goi backend.
SYNC_TIMEOUT_SECONDS = 3

# Thresholds
# Nguong diem liveness toi thieu de xem frame la mat that.
LIVENESS_THRESHOLD = 0.1
# Nguong cosine similarity toi thieu de chap nhan match danh tinh.
MATCH_THRESHOLD = 0.4

# Attendance rules
# Kich thuoc cua cua so truot (theo so frame) de phat hien spoof.
SPOOF_WINDOW_SIZE = 5
# So frame bi nghi spoof trong cua so de kich hoat canh bao.
SPOOF_ALERT_COUNT = 3
IDENTITY_VOTE_WINDOW_SIZE = 5
IDENTITY_VOTE_MIN_COUNT = 4

COOLDOWN_SECONDS = 15

# Thoi gian bat dau lam viec.
SHIFT_START_HOUR = 8
SHIFT_START_MINUTE = 0
LATE_GRACE_MINUTES = 15  # Duoc phep muon toi da 15p.

# Thoi gian tan ca lam viec.
SHIFT_END_HOUR = 17
SHIFT_END_MINUTE = 30
