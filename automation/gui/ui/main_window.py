# ??????????????????????????????????????????????????????????????????????????????
#  ui/main_window.py  ?  Top-level window.
#
#  Threading model:
#    - All driver calls run in QThread workers (never on the GUI thread).
#    - Workers emit finished(dict) which is received on the GUI thread.
#    - Polling: one persistent QTimer per connected device fires every N ms
#      and spawns a fresh worker to fetch the latest state.
#    - connect_all() runs each device connect sequentially in ONE background
#      thread rather than spawning four simultaneous threads.
# ??????????????????????????????????????????????????????????????????????????????

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import time
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QFrame, QScrollArea, QGraphicsDropShadowEffect
from PySide6.QtCore    import Qt, QTimer, QThread, Signal, QObject, Slot, QMetaObject
from PySide6.QtGui     import QIcon, QColor
import ctypes

from config import (
    COL_ACCENT, COL_AMBER, COL_RED, COL_GREEN,
    WINDOW_MIN_W, WINDOW_MIN_H,
    POLL_TELESCOPE_MS, POLL_COVERS_MS, POLL_DOME_MS, POLL_ROTATOR_MS, POLL_FOCUSER_MS, ICON_PATH
)
from styles import APP_STYLESHEET, divider_style

from drivers import TelescopeWrapper, RotatorWrapper, CoverWrapper, DomeWrapper, FocuserWrapper

from ui.header                  import HeaderWidget
from ui.controls_bar            import ControlsBar
from ui.log_console             import LogConsole
from ui.night_modal             import NightModal
from ui.cards.telescope_card    import TelescopeCard
from ui.cards.covers_card       import CoversCard
from ui.cards.dome_card         import DomeCard
from ui.cards.rotator_card      import RotatorCard
from ui.cards.focuser_card      import FocuserCard
from ui.confirm                 import confirm
from ui.titlebar                import TitleBar
from ui.window_frame            import WindowFrame


# ??????????????????????????????????????????????????????????????????????????????
#  Background worker
# ??????????????????????????????????????????????????????????????????????????????

class Worker(QObject):
    """
    Runs fn() in a background thread.
    Return value is normalised to dict:
        bool True  -> {"ok": True}
        bool False -> {"ok": False}
        None       -> {}
        dict       -> unchanged
    """
    finished   = Signal(dict)
    log_signal = Signal(str, str)   # level, message

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    @Slot()
    def run(self):
        try:
            result = self._fn()
            if isinstance(result, bool):
                result = {"ok": result}
            elif result is None:
                result = {}
            elif not isinstance(result, dict):
                result = {"value": result}
            self.finished.emit(result)
        except Exception as e:
            self.log_signal.emit("ERROR", str(e))
            self.finished.emit({"ok": False, "error": str(e)})


def _spawn(fn, on_done=None, on_log=None, parent=None):
    """Run fn() in a QThread; on_done(dict) called on GUI thread when done."""
    thread = QThread()
    worker = Worker(fn)
    thread.worker = worker
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    if on_done:
        worker.finished.connect(on_done, Qt.QueuedConnection)
    if on_log:
        worker.log_signal.connect(on_log, Qt.QueuedConnection)
    worker.finished.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.start()
    return thread


# ??????????????????????????????????????????????????????????????????????????????
#  Main Window
# ??????????????????????????????????????????????????????????????????????????????

class MainWindow(QMainWindow):
    _connect_result = Signal(str, bool, object)
    _connect_start = Signal(str)
    _all_done_signal = Signal()
    def __init__(self):
        
        super().__init__()
        self._connect_result.connect(self._apply_connect_result)
        self._connect_start.connect(self._on_connect_start)
        self._all_done_signal.connect(self._on_connect_all_done)
        self.setWindowTitle("T2 / RAPTOR  -  Observatory Control System")
        self.setMinimumSize(WINDOW_MIN_W, WINDOW_MIN_H)
        self.setStyleSheet(APP_STYLESHEET)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_NoSystemBackground, False)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setWindowIcon(QIcon(ICON_PATH))

        self._tel  = TelescopeWrapper()
        self._rot  = RotatorWrapper()
        self._cov  = CoverWrapper()
        self._dome = DomeWrapper()
        self._foc  = FocuserWrapper()

        # Keep thread references alive until Qt cleans them up
        self._threads: list = []

        # One QTimer per connected device
        self._poll_timers: dict[str, QTimer] = {}

        # Set True in closeEvent so in-flight callbacks don't touch dead widgets
        self._closing = False

        self._build_ui()
        
        self._frame = WindowFrame(self)
        self._frame.resize(self.size())
        self._frame.show()
        self._frame.raise_()
        
        self._wire_signals()
        self._log("SYS",  "Observatory Control System ready")
        self._log("INFO", "Ensure Autoslew and ASCOM Remote are running before connecting")

        self._poll_busy: dict[str, bool] = {}
        
    # ?? UI ????????????????????????????????????????????????????????????????????

    def _on_connect_all_done(self):
        self._controls.set_connecting(False)
        self._log("OK", "Connection sequence complete")
    
    def _on_connect_start(self, key: str):
        card = self._card(key)
        card.set_lamp("connecting")
        card.badge.set_status("CONNECTING", COL_AMBER)
    
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        
        # Custom titlebar ? replaces Windows chrome entirely
        self._titlebar = TitleBar(window=self)
        root.addWidget(self._titlebar)
        
        # Scrollable content area below titlebar
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(18, 10, 18, 12)
        content_layout.setSpacing(8)
 
        self._controls = ControlsBar()
        content_layout.addWidget(self._controls)
 
        content_layout.addWidget(self._hr())
 
        self._tel_card  = TelescopeCard()
        self._cov_card  = CoversCard()
        self._dome_card = DomeCard()
        self._rot_card  = RotatorCard()
        self._foc_card =  FocuserCard()
 
        for card in (self._dome_card, self._tel_card, self._rot_card,
                     self._foc_card, self._cov_card):
            content_layout.addWidget(card)
            content_layout.addSpacing(2)
 
        content_layout.addWidget(self._hr())
 
        self._log_console = LogConsole()
        content_layout.addWidget(self._log_console)
        content_layout.addStretch()
 
        # Wrap content in a scroll area so small screens can still reach everything
        scroll = QScrollArea()
        scroll.setWidget(content_widget)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        root.addWidget(scroll)
        
    # def _build_ui(self):
    #     central = QWidget()
    #     self.setCentralWidget(central)
    #     root = QVBoxLayout(central)
    #     root.setContentsMargins(18, 16, 18, 12)
    #     root.setSpacing(8)

        # self._header = HeaderWidget()
        # root.addWidget(self._header)

        # root.addWidget(self._hr(COL_ACCENT + "88"))

        # self._controls = ControlsBar()
        # root.addWidget(self._controls)

        # root.addWidget(self._hr())

        # self._tel_card  = TelescopeCard()
        # self._cov_card  = CoversCard()
        # self._dome_card = DomeCard()
        # self._rot_card  = RotatorCard()
        # self._foc_card  = FocuserCard()

        # for card in (self._dome_card, self._tel_card, 
        #              self._rot_card, self._foc_card, self._cov_card):
        #     root.addWidget(card)
        #     # root.addSpacing(1)

        # root.addWidget(self._hr())

        # self._log_console = LogConsole()
        # root.addWidget(self._log_console)

    def _hr(self, colour: str = None) -> QFrame:
        f = QFrame()
        f.setFixedHeight(1)
        f.setStyleSheet(divider_style(colour))
        return f

    # ?? Signals ???????????????????????????????????????????????????????????????

    def _wire_signals(self):
        self._controls.connect_all_requested.connect(self._connect_all)
        self._controls.start_night_requested.connect(
            lambda: self._open_night_modal("start"))
        self._controls.end_night_requested.connect(
            lambda: self._open_night_modal("end"))

        self._tel_card.reconnect_requested.connect(
            lambda _: self._connect_device("telescope"))
        self._cov_card.reconnect_requested.connect(
            lambda _: self._connect_device("cover"))
        self._dome_card.reconnect_requested.connect(
            lambda _: self._connect_device("dome"))
        self._rot_card.reconnect_requested.connect(
            lambda _: self._connect_device("rotator"))
        self._rot_card.move_requested.connect(self._move_rotator)
        self._foc_card.reconnect_requested.connect(
            lambda _: self._connect_device("focuser"))
        self._foc_card.move_requested.connect(self._move_focuser)

        self._tel_card.set_callbacks(
            park=lambda: confirm(self, "Park Telescope", "Park the telescope?\nWarning: Telescope will move.", danger=True) and self._park_telescope,
            abort=lambda: confirm(self, "Abort Slew", "Abort current slew?", danger=True) and self._abort_slew,
        )
        self._tel_card.mirror_requested.connect(self._set_mirror)
        
        self._cov_card.set_callbacks(
            open_cb=lambda: confirm(self, "Open Covers", "Open the covers?") and self._covers_action("open"),
            close_cb=lambda: confirm(self, "Close Covers", "Close the covers?") and self._covers_action("close"),
        )
        self._dome_card.set_callbacks(
            open_cb=lambda: confirm(self, "Open Dome", "Open the dome?", danger=True) and self._dome_action("open"),
            close_cb=lambda: confirm(self, "Close Dome", "Close the dome?", danger=True) and self._dome_action("close"),
            abort_cb=lambda: confirm(self, "Abort Dome Move", "Abort dome move?", danger=True) and self._dome_abort,
        )

    # ?? Logging ???????????????????????????????????????????????????????????????

    def _log(self, level: str, msg: str):
        self._log_console.log(level, msg)

    # ?? Thread helper ?????????????????????????????????????????????????????????

    def _go(self, fn, on_done=None):
        # If called from a non-GUI thread, re-post to GUI thread event loop
        if QThread.currentThread() is not self.thread():
            QTimer.singleShot(0, lambda: self._go(fn, on_done))
            return None

        def _guarded_done(result):
            if not self._closing and on_done:
                on_done(result)

        t = _spawn(fn, on_done=_guarded_done,
                on_log=lambda lv, msg: self._log(lv, msg) if not self._closing else None)
        self._threads.append(t)
        t.finished.connect(
            lambda: self._threads.remove(t) if t in self._threads else None,
            Qt.QueuedConnection
        )
        return t

    # ?? Card / driver lookup helpers ??????????????????????????????????????????

    def _card(self, key: str):
        return {"telescope": self._tel_card,  "cover":   self._cov_card,
                "dome":      self._dome_card,  "rotator": self._rot_card,
                "focuser":   self._foc_card}[key]

    def _driver(self, key: str):
        return {"telescope": self._tel,  "cover":   self._cov,
                "dome":      self._dome, "rotator": self._rot,
                "focuser":   self._foc}[key]

    def _update_card(self, key: str, info: dict):
        # self._log("DBG", f"{key}: update_card called with {info}")
        {"telescope": self._tel_card.update_from_info,
         "cover":     self._cov_card.update_from_info,
         "dome":      self._dome_card.update_from_info,
         "rotator":   self._rot_card.update_from_info,
         "focuser":   self._foc_card.update_from_info}[key](info)

    def _move_focuser(self, position: int):
        self._log("INFO", f"Moving focuser to {position}...")
        self._foc_card.enable_button("move", False)
        self._go(lambda: self._foc.move_to(position),
                on_done=lambda r: (
                    self._log("OK" if r.get("ok") else "ERROR",
                            f"Focuser {'moved to ' + str(position) if r.get('ok') else 'move failed'}"),
                    self._foc_card.enable_button("move", True)
                ))

    def _halt_focuser(self):
        self._log("WARN", "Halting focuser...")
        self._go(self._foc.halt,
                on_done=lambda r: self._log(
                    "OK" if r.get("ok") else "WARN",
                    "Focuser halted" if r.get("ok") else "Focuser was not moving"))
    
    def _move_rotator(self, position_deg: float):
        self._log("INFO", f"Moving rotator to {position_deg}°...")
        self._rot_card.enable_button("move", False)
        self._go(lambda: self._rot.move_to(position_deg),
                on_done=lambda r: (
                    self._log("OK" if r.get("ok") else "ERROR",
                            f"Rotator {'moved to ' + str(position_deg) if r.get('ok') else 'move failed'}"),
                    self._rot_card.enable_button("move", True)
                ))
    
    def _open_mirror_dialog(self):
        pass
    
    def _set_mirror(self, port: str):
        port_num = self._tel._driver.spectroscopy_port if port == "spectro" \
                else self._tel._driver.photometry_port
        label = "spectroscopy" if port == "spectro" else "photometry"
        self._log("INFO", f"Switching tertiary mirror to {label} port...")
        def _done(r):
            self._log("OK" if r.get("ok") else "ERROR",
                    f"Mirror at {label} port" if r.get("ok") else "Mirror switch failed")
        self._go(lambda: self._tel.set_tertiary_mirror(port_num), on_done=_done)
        
    # ?? Connect All ???????????????????????????????????????????????????????????   
    
    def _connect_all(self):
        self._controls.set_connecting(True)
        self._log("SYS",  "Initiating connection to all devices...")
        self._log("INFO", "Ensure Autoslew and ASCOM Remote are running")

        def _work():
            # results = {}
            for key in ("dome", "telescope", "rotator", "focuser", "cover"):
                if self._closing:
                    break
                self._connect_start.emit(key)
                # print(f"[THREAD] {key}: connect start") # TEMP DEBUG
                ok, info = self._do_connect(key)
                if self._closing:
                    break
                # print(f"[THREAD] {key}: connect done -> {ok}") # TEMP DEBUG
                self._connect_result.emit(key, ok, info)
                # results[key] = {"ok": ok, "info": info}
                time.sleep(0.2)
            if not self._closing:
                self._all_done_signal.emit()
        self._go(_work)            
            # return results

        # def _done(results):
        #     print(f"[_done] on thread: {QThread.currentThread()}, GUI thread: {self.thread()}, same: {QThread.currentThread() is self.thread()}")
        #     for key, res in results.items():
        #         self._connect_result.emit(key, res["ok"], res["info"])
        #     self._controls.set_connecting(False)
        #     n = sum(1 for r in results.values() if r["ok"])
        #     self._log("OK", f"Connection sequence complete ? {n}/4 devices online")
        
            #     self._controls.set_connecting(False)
            #     for key, res in results.items():
            #         self._apply_connect_result(key, res["ok"], res["info"])
            #     n = sum(1 for r in results.values() if r["ok"])
            #     self._log("OK", f"Connection sequence complete ? {n}/4 devices online")
            # QTimer.singleShot(0, _apply)
        

    # ?? Individual connect ????????????????????????????????????????????????????

    def _connect_device(self, key: str):
        card = self._card(key)
        card.set_lamp("connecting")
        card.badge.set_status("CONNECTING", COL_AMBER)
        self._log("SYS", f"Connecting to {key}...")

        def _work():
            ok, info = self._do_connect(key)
            return {"ok": ok, "info": info}

        self._go(_work,
                on_done=lambda r: self._connect_result.emit(
                    key, r.get("ok", False), r.get("info", {})))
        
        # self._go(_work,
        #          on_done=lambda r: QTimer.singleShot(
        #              0, lambda: self._apply_connect_result(
        #                  key, r.get("ok", False), r.get("info", {}))))
        # self._go(_work,
        #          on_done=lambda r: self._apply_connect_result(
        #              key, r.get("ok", False), r.get("info", {})))

    def _do_connect(self, key: str):
        """Synchronous: connect + get_info.  Called from background thread."""
        drv = self._driver(key)
        try:
            t0 = time.time()
            # self._log("DBG", f"{key}: connect() start") ## DEBUGGING
            ok = drv.connect()
            # self._log("DBG", f"{key}: connect() done in {time.time()-t0:.2f} s -> {ok}") ## DEBUGGING
            if not ok:
                return False, {}
            t1 = time.time()
            # self._log("DBG", f"{key}: get_info() start") ## DEBUGGING
            info = drv.get_info()
            # self._log("DBG", f"{key}: get_info() done in {time.time()-t1:.2f} s -> {info}") ## DEBUGGING
            # if not info or info == {}:
            #     return False, {}
            return True, info
        except Exception as e:
            self._log("ERROR", f"{key}: {e}")
            return False, {}

    def _apply_connect_result(self, key: str, ok: bool, info: dict):
        """Apply connection result ? always called on GUI thread."""
        card = self._card(key)
        if ok:
            card.set_lamp("connected")
            card.badge.set_status("CONNECTED", COL_GREEN)
            self._update_card(key, info)
            self._log("OK", f"{key.capitalize()} connected")
            QTimer.singleShot(0, lambda: self._start_poll(key))
        else:
            card.set_lamp("disconnected")
            card.badge.set_status("FAILED", COL_RED)
            self._log("ERROR", f"{key.capitalize()} connection failed")

    # ?? Polling ???????????????????????????????????????????????????????????????

    def _start_poll(self, key: str):
        """Start (or restart on reconnect) polling timer for a device.
        Must be called on the GUI thread only"""
        if key in self._poll_timers:
            old = self._poll_timers.pop(key)
            old.timeout.disconnect()
            QTimer.singleShot(0, old.stop)
            QTimer.singleShot(0, old.deleteLater)
            # self._poll_timers[key].stop()
            # self._poll_timers[key].deleteLater()
        
        self._poll_busy[key] = False

        intervals = {"telescope": POLL_TELESCOPE_MS, "cover": POLL_COVERS_MS,
                     "dome": POLL_DOME_MS, "rotator": POLL_ROTATOR_MS, "focuser": POLL_FOCUSER_MS}
        drv = self._driver(key)
        
        def _poll():
            if self._closing:
                return            
            if self._poll_busy.get(key):
                return # skip if previous call still running
            self._poll_busy[key] = True
            
            def _done(info):
                self._poll_busy[key] = False
                self._update_card(key, info)
            
            # self._go(drv.get_info, on_done=lambda r: QTimer.singleShot(0, lambda: _done(r)))
            self._go(drv.get_info, on_done=_done)
                
        
        timer = QTimer()
        # timer.setSingleShot(False)
        timer.timeout.connect(_poll)
        timer.start(intervals[key])
        self._poll_timers[key] = timer

    # ?? Telescope actions ?????????????????????????????????????????????????????

    def _park_telescope(self):
        self._log("INFO", "Parking telescope...")
        self._tel_card.enable_button("park", False)

        def _done(r):
            if r.get("ok"):
                self._log("OK", "Telescope parked")
            else:
                self._log("ERROR", "Telescope park failed ? check Autoslew")
                self._tel_card.enable_button("park", True)

        self._go(self._tel.park, on_done=_done)

    def _abort_slew(self):
        self._log("WARN", "Sending abort slew...")
        self._go(self._tel.abort_slew,
                 on_done=lambda _: self._log("OK", "Abort slew sent"))

    # ?? Cover actions ?????????????????????????????????????????????????????????

    def _covers_action(self, action: str):
        label = "Opening" if action == "open" else "Closing"
        self._log("INFO", f"{label} covers...")
        self._cov_card.enable_buttons(False)
        fn = self._cov.open_cover if action == "open" else self._cov.close_cover

        def _done(r):
            ok = r.get("ok", False)
            self._log("OK" if ok else "ERROR",
                      f"Covers {action}ed" if ok else f"Cover {action} failed")
            self._cov_card.enable_buttons(True)

        self._go(fn, on_done=_done)

    # ?? Dome actions ??????????????????????????????????????????????????????????

    def _dome_action(self, action: str):
        label = "Opening" if action == "open" else "Closing"
        self._log("INFO", f"{label} dome panels...")
        self._dome_card.enable_buttons(False)
        fn = self._dome.open if action == "open" else self._dome.close

        def _done(r):
            ok = r.get("ok", False)
            self._log("OK" if ok else "ERROR",
                      f"Dome {action}ed" if ok else f"Dome {action} failed")
            self._dome_card.enable_buttons(True)

        self._go(fn, on_done=_done)

    def _dome_abort(self):
        self._log("WARN", "Sending dome abort...")
        self._go(self._dome.abort,
                 on_done=lambda _: self._log("OK", "Dome abort sent"))

    # ?? Night modal ???????????????????????????????????????????????????????????

    def _open_night_modal(self, mode: str):
        NightModal(mode, self._execute_night, parent=self).exec()

    def _execute_night(self, mode: str, opts: dict):
        label = "START NIGHT" if mode == "start" else "END NIGHT"
        self._log("SYS", f"{label} sequence initiated")

        def _work():
            if mode == "start":
                if opts.get("dome"):
                    self._log("INFO", "Opening dome...")
                    dome_opened = self._dome.open()
                    if dome_opened:
                        self._log("OK", "Dome opened")
                    # time.sleep(0.1)
                if opts.get("covers"):
                    self._log("INFO", "Opening covers...")
                    covers_opened = self._cov.open_cover()
                    if covers_opened:
                        self._log("OK", "Covers opened")
                    # time.sleep(0.1)
                if opts.get("motors"):
                    self._log("INFO", "Turning telescope motors on...")
                    motors_on = self._tel.motor_on()
                    if motors_on:
                        self._log("OK", "Telescope motors on")
            else:
                if opts.get("covers"):
                    self._log("INFO", "Closing covers...")
                    covers_closed = self._cov.close_cover()
                    if covers_closed:
                        self._log("OK", "Covers closed")
                    # time.sleep(0.1)
                if opts.get("park"):
                    self._log("INFO", "Parking telescope...")
                    tel_parked = self._tel.park()
                    if tel_parked:
                        self._log("OK", "Telescope parked")
                    # time.sleep(0.1)
                if opts.get("motors"):
                    self._log("INFO", "Turning telescope motors off...")
                    motors_off = self._tel.motor_off()
                    if motors_off:
                        self._log("OK", "Telescope motors off")
                    # time.sleep(0.1)
                if opts.get("dome"):
                    self._log("INFO", "Closing dome...")
                    dome_closed = self._dome.close()
                    if dome_closed:
                        self._log("OK", "Dome closed")
            return {}

        self._go(_work,
                 on_done=lambda _: self._log("OK", f"{label} complete"))

    # ?? Clean shutdown ????????????????????????????????????????????????????????

    def closeEvent(self, event):
        # Confirmation is handled by TitleBar._on_close ? by the time we get
        # here the user has already confirmed, so just clean up and accept.
        self._closing = True
 
        for timer in self._poll_timers.values():
            timer.timeout.disconnect()
            QTimer.singleShot(0, timer.stop)
            QTimer.singleShot(0, timer.deleteLater)
            # timer.stop()
        self._poll_timers.clear()
 
        for t in list(self._threads):
            if t.isRunning():
                t.quit()
                # No t.wait() ? causes killTimer cross-thread errors
 
        for drv in (self._tel, self._rot, self._cov, self._dome, self._foc):
            try:
                drv.disconnect()
            except Exception:
                pass
 
        event.accept()
 
    # ?? Edge resize (frameless windows lose native resize) ????????????????????
 
    def mousePressEvent(self, event):
        """Store press position for edge-drag resize."""
        self._resize_start = event.globalPosition().toPoint()
        self._resize_geom  = self.geometry()
 
    def mouseMoveEvent(self, event):
        """Allow dragging the bottom-right 16px corner to resize."""
        if not (event.buttons() & Qt.LeftButton):
            return
        pos = event.position().toPoint()
        if pos.x() > self.width() - 16 and pos.y() > self.height() - 16:
            delta = event.globalPosition().toPoint() - self._resize_start
            new_w = max(self._resize_geom.width()  + delta.x(), WINDOW_MIN_W)
            new_h = max(self._resize_geom.height() + delta.y(), WINDOW_MIN_H)
            self.resize(new_w, new_h)


    # def closeEvent(self, event):
    #     # Prevent in-flight callbacks from touching widgets after close
    #     self._closing = True

    #     # Stop all polling timers
    #     for timer in self._poll_timers.values():
    #         timer.timeout.disconnect()
    #         QTimer.singleShot(0, timer.stop)
    #         QTimer.singleShot(0, timer.deleteLater)
    #     self._poll_timers.clear()

    #     # Tell threads to stop ? don't wait, deleteLater handles cleanup safely
    #     for t in list(self._threads):
    #         if t.isRunning():
    #             t.quit()
    #             # NO t.wait() ? causes killTimer cross-thread errors

    #     # Disconnect drivers best-effort
    #     for drv in (self._tel, self._rot, self._cov, self._dome, self._foc):
    #         try:
    #             drv.disconnect()
    #         except Exception:
    #             pass

    #     event.accept()
