"""음성 전송 흐름: 단축키 → 녹음 → 받아쓰기 → 붙여넣기(+디스코드면 엔터).
화면은 직접 안 건드리고 app.bus 로 상태만 보낸다(작업 스레드에서 돌기 때문)."""
import threading
import time
import winsound

from ...audio import devices, recorder
from ...core.log import log, log_exc
from ...system import windows


class VoiceController:
    def __init__(self, app):
        self.app = app
        self.cfg = app.cfg
        self.bus = app.bus
        self._lock = threading.Lock()
        self.active = False
        self.testing = False
        self.stop_event = threading.Event()

    # ── 상태 알림 ──
    def status(self, kind, title, detail=""):
        self.bus.post("status", kind, title, detail)

    def beep(self, freq, ms):
        if self.cfg["sound"]:
            threading.Thread(target=winsound.Beep, args=(freq, ms), daemon=True).start()

    def _begin(self, testing=False):
        with self._lock:
            if self.active:
                return False
            self.active = True
            self.testing = testing
        self.stop_event.clear()
        return True

    def _end(self):
        self.bus.post("overlay", False)
        self.bus.post("level", 0.0)
        self.active = False
        self.testing = False

    # ── 단축키 ──
    def toggle(self):
        if self.active:
            if not self.testing:
                self.stop_event.set()  # 녹음 중에 다시 누르면 바로 전송
            return
        if self._begin():
            threading.Thread(target=self._run_safe, name="voice", daemon=True).start()

    def _run_safe(self):
        try:
            self._run()
        except recorder.NoSpeech as e:
            log(f"말소리 없음, 취소 (최대 음량 {e.peak:.3f})")
            self.beep(400, 200)
            self.status("err", "소리가 안 잡혔어요", f"최대 음량 {e.peak:.3f}. 마이크 테스트로 확인해 주세요")
        except recorder.MicError as e:
            log(f"마이크 오류: {e}")
            self.beep(300, 400)
            self.status("err", "마이크 문제", str(e)[:160])
        except Exception as e:
            log_exc("음성 전송")
            self.beep(300, 400)
            self.status("err", "오류", str(e)[:160])
        finally:
            self._end()

    def _run(self):
        key = self.cfg["hotkey"].upper()
        devices.refresh()  # 헤드셋 껐다 켰어도 다시 잡기
        dev = devices.resolve(self.cfg["mic"])
        name = devices.label(dev)
        self.beep(880, 120)
        if self.cfg["overlay"]:
            self.bus.post("overlay", True)
        silence = self.cfg["silence"]
        self.status("rec", "녹음 중", f"{name}\n" + (f"말 끝나면 자동으로 보내요 ({key} 다시 눌러도 됨)" if silence > 0
                                                    else f"다 말하면 {key}를 다시 누르세요"))
        log(f"녹음 시작 ({name})")
        opts = recorder.RecordOptions(silence=silence, no_speech=self.cfg["no_speech"],
                                      max_sec=self.cfg["max_sec"], min_level=self.cfg["min_level"])
        pcm = recorder.record(dev, self.stop_event, opts, on_level=lambda v: self.bus.post("level", v))
        self.bus.post("overlay", False)
        self.beep(660, 120)
        secs = len(pcm) / recorder.RATE
        recorder.save_last(pcm)

        engine = self.app.engine
        self.status("busy", "글자로 바꾸는 중", f"{secs:.1f}초 녹음 · {engine.status}")
        t1 = time.time()
        text = engine.transcribe(pcm, self.cfg["hotwords"])
        took = time.time() - t1
        log(f"변환 {took:.1f}초 [{engine.label}]: {text}")
        if not text:
            self.beep(400, 200)
            self.status("err", "받아쓴 글자가 없어요", "다시 말해 주세요")
            return
        exe, sent = windows.paste_text(text, auto_send=self.cfg["auto_send"])
        log(f"{'전송' if sent else '입력창에 넣음'} (앞 창: {exe})")
        self.bus.post("sent", text)
        if sent:
            self.status("ok", "보냈어요", f"{secs:.1f}초 녹음 → {engine.label} 모델로 {took:.1f}초 만에 받아씀")
        else:
            self.status("ok", "입력창에 넣었어요", f"앞 창이 디스코드가 아니라 엔터는 안 쳤어요 ({exe})")

    # ── 마이크 테스트: 5초 동안 음량만 보여 줌(보내지 않음) ──
    def mic_test(self):
        if self._begin(testing=True):
            threading.Thread(target=self._mic_test, name="mic-test", daemon=True).start()

    def _mic_test(self):
        try:
            devices.refresh()
            dev = devices.resolve(self.cfg["mic"])
            name = devices.label(dev)
            self.status("busy", "마이크 테스트 중", f"{name}\n말해 보세요 (5초)")
            peak = recorder.measure(dev, 5, self.stop_event, on_level=lambda v: self.bus.post("level", v))
            if peak < self.cfg["min_level"]:
                self.status("err", "소리가 안 잡혀요", f"{name}\n음소거·연결을 확인하거나 다른 마이크를 골라 주세요")
            else:
                self.status("ok", "마이크 정상", f"{name}\n최대 음량 {peak:.3f}")
            log(f"마이크 테스트 {name} 최대 {peak:.3f}")
        except Exception as e:
            log_exc("마이크 테스트")
            self.status("err", "마이크 오류", str(e)[:160])
        finally:
            self._end()
