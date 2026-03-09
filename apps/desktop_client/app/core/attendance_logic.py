from collections import deque
from datetime import datetime, timedelta


class AttendanceDecisionEngine:
    def __init__(
        self,
        liveness_threshold,
        spoof_window_size,
        spoof_alert_count,
        vote_window_size=None,
        vote_min_count=None,
        cooldown_seconds=0,
    ):
        self.liveness_threshold = float(liveness_threshold)
        self.spoof_window_size = int(spoof_window_size)
        self.spoof_alert_count = int(spoof_alert_count)
        self.cooldown_seconds = int(cooldown_seconds)

        self.spoof_window = deque(maxlen=self.spoof_window_size)
        self.spoof_alert_latched = False

        self.last_accept_time = {}

    def _in_cooldown(self, identity, now):
        if identity not in self.last_accept_time:
            return False
        return now - self.last_accept_time[identity] < timedelta(seconds=self.cooldown_seconds)

    def reset_tracking(self):
        return None

    def no_face(self):
        self.spoof_window.clear()
        self.spoof_alert_latched = False
        self.reset_tracking()

    def on_spoof_check(self, liveness_score):
        is_spoof = float(liveness_score) < self.liveness_threshold
        self.spoof_window.append(is_spoof)

        if len(self.spoof_window) == self.spoof_window_size and sum(self.spoof_window) >= self.spoof_alert_count:
            if not self.spoof_alert_latched:
                self.spoof_alert_latched = True
                return {
                    "triggered": True,
                    "spoof_frames": int(sum(self.spoof_window)),
                    "window_size": self.spoof_window_size,
                }
            return {"triggered": False}

        self.spoof_alert_latched = False
        return {"triggered": False}

    def on_identity(self, identity, similarity_score):
        now = datetime.now()

        if identity == "unknown":
            return {
                "accepted": False,
                "cooldown": False,
            }

        if self._in_cooldown(identity, now):
            return {
                "accepted": False,
                "cooldown": True,
            }

        self.last_accept_time[identity] = now
        return {
            "accepted": True,
            "cooldown": False,
            "identity": identity,
            "similarity": float(similarity_score),
        }
