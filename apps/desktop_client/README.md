# Desktop Client Architecture

Desktop client su dung `Tkinter + OpenCV + ONNX Runtime`.

## Muc Tieu

- Cung cap UI desktop don gian cho 2 chuc nang:
	- Cham cong
	- Dang ky nhan vien moi
- Xu ly AI local tren may (detect + anti-spoof + embedding).
- Match/enroll embedding qua backend API (online-only).
- Dong bo su kien cham cong len backend API.

## Cau Truc Thu Muc

- `main.py`: launcher chinh (de build `.exe`).
- `app/main.py`: app entrypoint noi bo.
- `app/ui/desktop_tk_ui.py`: giao dien Tkinter.
- `app/pipelines/infer_camera.py`: pipeline cham cong camera.
- `app/pipelines/enroll_camera.py`: pipeline dang ky khuon mat.
- `app/vision/face_utils.py`: ham AI chung (model load, detect, align, embedding).
- `app/services/backend_sync.py`: goi backend API cho health/match/enroll/event.
- `app/services/event_logger.py`: log su kien local.
- `app/core/settings.py`: cau hinh tap trung.
- `models/`: ONNX models.

## Luong Cham Cong

`UI button -> infer pipeline -> detect/anti-spoof/extract 5 embeddings -> backend /recognition/match-batch -> hien ket qua -> gui event backend`

Neu backend loi/mat mang:

- Cham cong bi dung ngay va UI bao loi ket noi.

## Luong Dang Ky Nhan Vien Moi

`UI button -> nhap employee_code -> camera enroll -> trung binh embedding -> backend /recognition/enroll -> thong bao ket qua`

## Chay Ung Dung

```bash
python main.py
```

UI se hien 2 nut:

- `Cham cong`
- `Dang ky nhan vien moi`

## Chay Pipeline Truc Tiep (dev)

```bash
python -m app.pipelines.infer_camera
python -m app.pipelines.enroll_camera
```

## Yeu Cau File

- Models ONNX dat trong `models/`:
	- `FaceDetector.onnx`
	- `best_model_anti_spoofing.onnx`
	- `arcface.onnx`

## Che Do Online-Only

- Khong su dung local gallery/cache de match hoac enroll.
- Khong co queue/retry offline cho attendance event.
- Neu mat ket noi backend, client khong cho cham cong/dang ky.

## Cau Hinh Quan Trong

Trong `app/core/settings.py`:

- `BACKEND_BASE_URL`: URL backend API.
- `DEVICE_CODE`: ma thiet bi gui len backend.
- `SHIFT_START_HOUR`, `SHIFT_START_MINUTE`, `LATE_GRACE_MINUTES`: quy tac hien thi dung gio/muon tren UI.
