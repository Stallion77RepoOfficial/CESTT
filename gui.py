import sys, json, threading
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QFileDialog,
    QLineEdit, QVBoxLayout, QHBoxLayout, QCheckBox, QTextEdit, QGroupBox,
    QMessageBox, QSpinBox
)
from PyQt6.QtCore import Qt

from logger import LogBus, Report
from engine_tests import uci, burst, endurance, threads, multipv, instances, fuzz, pgnreplay


class CESTT(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CESTT — Chess Engine Stress Test Toolkit")
        self.setMinimumSize(1000, 700)

        self.bus = LogBus(self._sink)
        self.report = None

        # --- Ana widget ---
        main = QWidget()
        self.setCentralWidget(main)
        layout = QVBoxLayout(main)

        # --- Engine seçimi ---
        top = QHBoxLayout()
        layout.addLayout(top)
        top.addWidget(QLabel("Engine path:"))
        self.engine_edit = QLineEdit()
        top.addWidget(self.engine_edit)
        btn_browse = QPushButton("Browse")
        btn_browse.clicked.connect(self.pick_engine)
        top.addWidget(btn_browse)

        # --- Parametreler ---
        params_box = QGroupBox("Parameters")
        layout.addWidget(params_box)
        pv = QVBoxLayout(params_box)

        self.movetime = self._param_row(pv, "movetime (sec)", "0.10")
        self.duration = self._param_row(pv, "endurance sec", "60")
        self.burst = self._param_row(pv, "burst positions", "200")
        self.thmax = self._param_row(pv, "threads max", "8")
        self.inst = self._param_row(pv, "instances", "4")
        self.perinst = self._param_row(pv, "per-instance positions", "50")
        self.pgn_dir = self._param_row(pv, "PGN dir (optional)", "", pick_dir=True)

        # --- Test seçimi ---
        tests_box = QGroupBox("Select tests")
        layout.addWidget(tests_box)
        th = QHBoxLayout(tests_box)
        self.test_vars = {}
        for name, default in [
            ("UCI", True), ("Burst", True), ("Endurance", False),
            ("Threads", True), ("MultiPV", True),
            ("Multi-instance", False), ("UCI Fuzz", False), ("PGN Replay", False)
        ]:
            cb = QCheckBox(name)
            cb.setChecked(default)
            self.test_vars[name] = cb
            th.addWidget(cb)

        # --- Çalıştırma + Log ---
        run_bar = QHBoxLayout()
        layout.addLayout(run_bar)
        btn_run = QPushButton("Run Selected")
        btn_run.clicked.connect(self.run_selected)
        run_bar.addWidget(btn_run)
        btn_save = QPushButton("Save Report JSON")
        btn_save.clicked.connect(self.save_report)
        run_bar.addWidget(btn_save)
        self.status_label = QLabel("idle")
        run_bar.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignRight)

        # --- Log Alanı ---
        log_box = QGroupBox("Log")
        layout.addWidget(log_box, stretch=1)
        vb = QVBoxLayout(log_box)
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        vb.addWidget(self.log_area)

    # -----------------------
    def _param_row(self, parent, label, default, pick_dir=False):
        fr = QHBoxLayout()
        parent.addLayout(fr)
        fr.addWidget(QLabel(label), stretch=1)
        edit = QLineEdit(default)
        fr.addWidget(edit, stretch=2)
        if pick_dir:
            btn = QPushButton("…")
            btn.clicked.connect(lambda: self._pick_dir(edit))
            fr.addWidget(btn)
        return edit

    def _pick_dir(self, edit):
        d = QFileDialog.getExistingDirectory(self, "Pick PGN folder")
        if d:
            edit.setText(d)

    def pick_engine(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select engine binary")
        if path:
            self.engine_edit.setText(path)

    def _sink(self, line: str):
        self.log_area.append(line)
        self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum())

    # -----------------------
    def run_selected(self):
        eng = self.engine_edit.text().strip()
        if not eng:
            QMessageBox.critical(self, "Error", "Engine yolu seçin.")
            return

        self.report = Report(eng)
        self.status_label.setText("running…")

        def worker():
            try:
                mv = max(0.005, float(self.movetime.text()))
                dur = max(5, int(float(self.duration.text())))
                bct = max(1, int(float(self.burst.text())))
                thm = max(1, int(float(self.thmax.text())))
                inst = max(1, int(float(self.inst.text())))
                per = max(1, int(float(self.perinst.text())))
                pgn_dir = self.pgn_dir.text().strip()

                if self.test_vars["UCI"].isChecked():
                    uci.run(self.bus, self.report, eng, movetime=mv)
                if self.test_vars["Burst"].isChecked():
                    burst.run(self.bus, self.report, eng, count=bct, movetime=mv)
                if self.test_vars["Endurance"].isChecked():
                    endurance.run(self.bus, self.report, eng, duration_s=dur, movetime=mv)
                if self.test_vars["Threads"].isChecked():
                    threads.run(self.bus, self.report, eng, movetime=mv, max_threads=thm)
                if self.test_vars["MultiPV"].isChecked():
                    multipv.run(self.bus, self.report, eng, movetime=mv, multipv=4)
                if self.test_vars["Multi-instance"].isChecked():
                    instances.run(self.bus, self.report, eng, instances=inst, per_instance=per, movetime=mv)
                if self.test_vars["UCI Fuzz"].isChecked():
                    fuzz.run(self.bus, self.report, eng, seconds=10)
                if self.test_vars["PGN Replay"].isChecked() and pgn_dir:
                    pgnreplay.run(self.bus, self.report, eng, pgn_dir=pgn_dir, movetime=mv, max_games=200)

            except Exception as e:
                self.bus.log(f"[ERROR] {e!r}")
                self.report.data["notes"].append(f"error: {e!r}")
            finally:
                self.report.finish()
                self.status_label.setText("idle")
                self.bus.log("=== CESTT finished ===")

        threading.Thread(target=worker, daemon=True).start()

    def save_report(self):
        if not self.report:
            QMessageBox.information(self, "Bilgi", "Önce bir test çalıştır.")
            return
        p, _ = QFileDialog.getSaveFileName(self, "Save report", filter="JSON Files (*.json)")
        if not p:
            return
        with open(p, "w") as f:
            f.write(self.report.to_json())
        self.bus.log(f"[report] saved → {p}")


def main():
    app = QApplication(sys.argv)
    win = CESTT()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
