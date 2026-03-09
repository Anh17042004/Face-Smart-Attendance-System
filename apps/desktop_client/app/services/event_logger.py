import json
from datetime import datetime
from pathlib import Path


class EventLogger:
	def __init__(self, log_path):
		self.log_path = Path(log_path)
		self.log_path.parent.mkdir(parents=True, exist_ok=True)

	def log(self, event_type, **payload):
		record = {
			"time": datetime.now().isoformat(timespec="seconds"),
			"event": event_type,
			**payload,
		}
		with self.log_path.open("a", encoding="utf-8") as f:
			f.write(json.dumps(record, ensure_ascii=False) + "\n")
		return record
