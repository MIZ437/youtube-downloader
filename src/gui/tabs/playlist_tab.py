"""
再生リストタブ
YouTubeプレイリストのダウンロード機能を提供
"""

from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QProgressBar, QCheckBox,
    QSpinBox, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal

from src.gui.workers import PlaylistFetchWorker
from src.downloader import YouTubeDownloader, PlaylistFilter


class PlaylistTab(QWidget):
    """再生リストタブ"""

    # ダウンロード開始シグナル（URLリストを親に送信）
    download_requested = pyqtSignal(list)

    def __init__(self, downloader: YouTubeDownloader, parent=None):
        super().__init__(parent)
        self.downloader = downloader
        self.all_videos = []  # 全動画（フィルター前）
        self.playlist_videos = []  # 表示中の動画（フィルター後）
        self.current_worker = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # URL入力
        url_layout = QHBoxLayout()
        url_label = QLabel("再生リストURL:")
        self.playlist_url_input = QLineEdit()
        self.playlist_url_input.setPlaceholderText("https://www.youtube.com/playlist?list=...")
        self.fetch_playlist_btn = QPushButton("読み込み")
        self.fetch_playlist_btn.clicked.connect(self.fetch_playlist)
        self.cancel_fetch_btn = QPushButton("中止")
        self.cancel_fetch_btn.setEnabled(False)
        self.cancel_fetch_btn.clicked.connect(self.cancel_fetch)
        self.clear_list_btn = QPushButton("クリア")
        self.clear_list_btn.clicked.connect(self.clear_playlist)
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.playlist_url_input, 1)
        url_layout.addWidget(self.fetch_playlist_btn)
        url_layout.addWidget(self.cancel_fetch_btn)
        url_layout.addWidget(self.clear_list_btn)
        layout.addLayout(url_layout)

        # フィルターオプション
        filter_group = QGroupBox("フィルター条件")
        filter_layout = QHBoxLayout()

        # 日付フィルター（年・月をプルダウンで選択）
        date_layout = QVBoxLayout()
        date_label = QLabel("アップロード日:")
        self.use_date_filter = QCheckBox("日付でフィルター")

        # From: 年・月プルダウン
        self.year_from = QComboBox()
        self.year_from.addItems([str(y) for y in range(2005, 2027)])
        self.year_from.setCurrentText("2005")
        self.year_from.setFixedWidth(70)
        self.month_from = QComboBox()
        self.month_from.addItems([str(m) for m in range(1, 13)])
        self.month_from.setFixedWidth(50)

        # To: 年・月プルダウン
        self.year_to = QComboBox()
        self.year_to.addItems([str(y) for y in range(2005, 2027)])
        self.year_to.setCurrentText("2026")  # 2026年をデフォルト
        self.year_to.setFixedWidth(70)
        self.month_to = QComboBox()
        self.month_to.addItems([str(m) for m in range(1, 13)])
        self.month_to.setCurrentText("12")
        self.month_to.setFixedWidth(50)

        date_layout.addWidget(date_label)
        date_layout.addWidget(self.use_date_filter)
        date_from_layout = QHBoxLayout()
        from_label = QLabel("From:")
        from_label.setFixedWidth(35)
        date_from_layout.addWidget(from_label)
        date_from_layout.addWidget(self.year_from)
        date_from_layout.addWidget(self.month_from)
        date_from_layout.addStretch()
        date_layout.addLayout(date_from_layout)
        date_to_layout = QHBoxLayout()
        to_label = QLabel("To:")
        to_label.setFixedWidth(35)
        date_to_layout.addWidget(to_label)
        date_to_layout.addWidget(self.year_to)
        date_to_layout.addWidget(self.month_to)
        date_to_layout.addStretch()
        date_layout.addLayout(date_to_layout)
        filter_layout.addLayout(date_layout)

        # 再生回数フィルター
        view_layout = QVBoxLayout()
        view_label = QLabel("再生回数:")
        self.use_view_filter = QCheckBox("再生回数でフィルター")
        self.min_views = QSpinBox()
        self.min_views.setRange(0, 1000000000)
        self.min_views.setSingleStep(1000)
        self.max_views = QSpinBox()
        self.max_views.setRange(0, 1000000000)
        self.max_views.setSingleStep(1000)
        self.max_views.setValue(1000000000)
        view_layout.addWidget(view_label)
        view_layout.addWidget(self.use_view_filter)
        min_view_layout = QHBoxLayout()
        min_view_layout.addWidget(QLabel("Min:"))
        min_view_layout.addWidget(self.min_views)
        view_layout.addLayout(min_view_layout)
        max_view_layout = QHBoxLayout()
        max_view_layout.addWidget(QLabel("Max:"))
        max_view_layout.addWidget(self.max_views)
        view_layout.addLayout(max_view_layout)
        filter_layout.addLayout(view_layout)

        # 再生時間フィルター（分単位）
        duration_layout = QVBoxLayout()
        duration_label = QLabel("再生時間(分):")
        self.use_duration_filter = QCheckBox("再生時間でフィルター")
        self.min_duration = QSpinBox()
        self.min_duration.setRange(0, 1440)  # 最大24時間
        self.max_duration = QSpinBox()
        self.max_duration.setRange(0, 1440)
        self.max_duration.setValue(1440)
        duration_layout.addWidget(duration_label)
        duration_layout.addWidget(self.use_duration_filter)
        min_dur_layout = QHBoxLayout()
        min_dur_layout.addWidget(QLabel("Min:"))
        min_dur_layout.addWidget(self.min_duration)
        duration_layout.addLayout(min_dur_layout)
        max_dur_layout = QHBoxLayout()
        max_dur_layout.addWidget(QLabel("Max:"))
        max_dur_layout.addWidget(self.max_duration)
        duration_layout.addLayout(max_dur_layout)
        filter_layout.addLayout(duration_layout)

        # タイトルフィルター
        title_layout = QVBoxLayout()
        title_label = QLabel("タイトル:")
        self.title_contains = QLineEdit()
        self.title_contains.setPlaceholderText("含む文字列")
        self.title_excludes = QLineEdit()
        self.title_excludes.setPlaceholderText("除外する文字列")
        title_layout.addWidget(title_label)
        title_layout.addWidget(QLabel("含む:"))
        title_layout.addWidget(self.title_contains)
        title_layout.addWidget(QLabel("除外:"))
        title_layout.addWidget(self.title_excludes)
        filter_layout.addLayout(title_layout)

        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        # フィルター適用ボタン
        filter_btn_layout = QHBoxLayout()
        self.apply_filter_btn = QPushButton("フィルター適用")
        self.apply_filter_btn.clicked.connect(self.apply_filter)
        self.reset_filter_btn = QPushButton("フィルターリセット")
        self.reset_filter_btn.clicked.connect(self.reset_filter)
        filter_btn_layout.addStretch()
        filter_btn_layout.addWidget(self.apply_filter_btn)
        filter_btn_layout.addWidget(self.reset_filter_btn)
        layout.addLayout(filter_btn_layout)

        # 進捗
        self.playlist_progress = QProgressBar()
        self.playlist_progress_label = QLabel("再生リストを読み込んでください")
        layout.addWidget(self.playlist_progress_label)
        layout.addWidget(self.playlist_progress)

        # 動画リスト
        list_group = QGroupBox("動画一覧")
        list_layout = QVBoxLayout()

        self.playlist_table = QTableWidget()
        self.playlist_table.setColumnCount(5)
        self.playlist_table.setHorizontalHeaderLabels(["選択", "タイトル", "再生時間", "再生回数", "アップロード日"])
        self.playlist_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.playlist_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.playlist_table.cellChanged.connect(self.update_selected_count)
        list_layout.addWidget(self.playlist_table)

        # 選択ボタン
        select_btn_layout = QHBoxLayout()
        select_all_btn = QPushButton("全選択")
        select_all_btn.clicked.connect(self.select_all_playlist)
        deselect_all_btn = QPushButton("全解除")
        deselect_all_btn.clicked.connect(self.deselect_all_playlist)
        self.selected_count_label = QLabel("選択: 0件")
        select_btn_layout.addWidget(select_all_btn)
        select_btn_layout.addWidget(deselect_all_btn)
        select_btn_layout.addStretch()
        select_btn_layout.addWidget(self.selected_count_label)
        list_layout.addLayout(select_btn_layout)

        list_group.setLayout(list_layout)
        layout.addWidget(list_group)

        # ダウンロードボタン
        self.playlist_download_btn = QPushButton("選択した動画をダウンロード")
        self.playlist_download_btn.setMinimumHeight(40)
        self.playlist_download_btn.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.playlist_download_btn.clicked.connect(self.download_selected_playlist)
        layout.addWidget(self.playlist_download_btn)

    def fetch_playlist(self):
        """再生リスト取得（フィルターチェックボックスがONなら適用）"""
        url = self.playlist_url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "エラー", "再生リストURLを入力してください")
            return

        # フィルターオプション作成（チェックボックスがONの場合のみ適用）
        filter_options = PlaylistFilter()

        if self.use_date_filter.isChecked():
            filter_options.date_from = datetime(
                int(self.year_from.currentText()),
                int(self.month_from.currentText()),
                1
            )
            # 月末日を計算
            year_to = int(self.year_to.currentText())
            month_to = int(self.month_to.currentText())
            if month_to == 12:
                next_month = datetime(year_to + 1, 1, 1)
            else:
                next_month = datetime(year_to, month_to + 1, 1)
            from datetime import timedelta
            last_day = (next_month - timedelta(days=1)).day
            filter_options.date_to = datetime(year_to, month_to, last_day)

        if self.use_view_filter.isChecked():
            filter_options.min_views = self.min_views.value()
            filter_options.max_views = self.max_views.value()

        if self.use_duration_filter.isChecked():
            # 分→秒に変換
            filter_options.min_duration = self.min_duration.value() * 60
            filter_options.max_duration = self.max_duration.value() * 60

        title_contains = self.title_contains.text().strip()
        title_excludes = self.title_excludes.text().strip()
        if title_contains:
            filter_options.title_contains = title_contains
        if title_excludes:
            filter_options.title_excludes = title_excludes

        # UI更新
        self.fetch_playlist_btn.setEnabled(False)
        self.cancel_fetch_btn.setEnabled(True)
        self.playlist_progress_label.setText("再生リストを読み込み中...")
        self.playlist_progress.setValue(0)
        self.playlist_table.setRowCount(0)

        # ワーカー開始
        self.current_worker = PlaylistFetchWorker(self.downloader, url, filter_options)
        self.current_worker.progress.connect(self.on_playlist_progress)
        self.current_worker.finished.connect(self.on_playlist_fetched)
        self.current_worker.error.connect(self.on_playlist_error)
        self.current_worker.start()

    def cancel_fetch(self):
        """読み込みを中止"""
        if self.current_worker and self.current_worker.isRunning():
            self.downloader.cancel()
            self.playlist_progress_label.setText("中止中...")
            self.cancel_fetch_btn.setEnabled(False)

    def on_playlist_progress(self, current, total):
        """再生リスト取得進捗"""
        self.playlist_progress_label.setText(f"読み込み中... {current}/{total}")
        self.playlist_progress.setValue(int(current / total * 100) if total > 0 else 0)

    def on_playlist_fetched(self, videos):
        """再生リスト取得完了"""
        self.fetch_playlist_btn.setEnabled(True)
        self.cancel_fetch_btn.setEnabled(False)

        # キャンセルされた場合
        if not videos and self.downloader._is_cancelled():
            self.playlist_progress_label.setText("中止しました")
            self.downloader.reset_cancel()  # フラグをリセット
            return

        self.all_videos = videos  # 全動画を保存
        self.playlist_videos = videos  # 表示用にもコピー
        self.playlist_progress_label.setText(f"完了: {len(videos)}件の動画")
        self.playlist_progress.setValue(100)

        # フィルターのデフォルト値を実際のデータ範囲に設定
        self._set_filter_defaults_from_data(videos)

        # テーブル更新
        self._update_table(videos)

    def _set_filter_defaults_from_data(self, videos):
        """フィルターのデフォルト値を実際のデータ範囲に設定"""
        if not videos:
            return

        # 日付の範囲を計算
        dates = [v.upload_datetime for v in videos if v.upload_datetime]
        if dates:
            min_date = min(dates)
            max_date = max(dates)
            self.year_from.setCurrentText(str(min_date.year))
            self.month_from.setCurrentText(str(min_date.month))
            self.year_to.setCurrentText(str(max_date.year))
            self.month_to.setCurrentText(str(max_date.month))

        # 再生回数の範囲を計算
        view_counts = [v.view_count for v in videos if v.view_count is not None]
        if view_counts:
            self.min_views.setValue(min(view_counts))
            self.max_views.setValue(max(view_counts))

        # 再生時間の範囲を計算（秒→分に変換）
        durations = [v.duration for v in videos if v.duration is not None]
        if durations:
            self.min_duration.setValue(min(durations) // 60)
            self.max_duration.setValue(max(durations) // 60 + 1)  # 切り上げ

    def _update_table(self, videos):
        """テーブルを更新"""
        self.playlist_table.setRowCount(len(videos))
        for i, video in enumerate(videos):
            # チェックボックス
            checkbox = QTableWidgetItem()
            checkbox.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            checkbox.setCheckState(Qt.CheckState.Checked)
            self.playlist_table.setItem(i, 0, checkbox)

            # タイトル
            self.playlist_table.setItem(i, 1, QTableWidgetItem(video.title))

            # 再生時間
            self.playlist_table.setItem(i, 2, QTableWidgetItem(video.duration_str))

            # 再生回数
            self.playlist_table.setItem(i, 3, QTableWidgetItem(video.view_count_str))

            # アップロード日
            upload_date = video.upload_datetime
            date_str = upload_date.strftime("%Y/%m/%d") if upload_date else "不明"
            self.playlist_table.setItem(i, 4, QTableWidgetItem(date_str))

        self.update_selected_count()

    def apply_filter(self):
        """フィルターを適用（ローカルで絞り込み）"""
        if not self.all_videos:
            QMessageBox.warning(self, "エラー", "先に再生リストを読み込んでください")
            return

        filtered = self.all_videos.copy()

        # 日付フィルター
        if self.use_date_filter.isChecked():
            date_from = datetime(
                int(self.year_from.currentText()),
                int(self.month_from.currentText()),
                1
            )
            # 月末日を計算
            year_to = int(self.year_to.currentText())
            month_to = int(self.month_to.currentText())
            if month_to == 12:
                next_month = datetime(year_to + 1, 1, 1)
            else:
                next_month = datetime(year_to, month_to + 1, 1)
            from datetime import timedelta
            last_day = (next_month - timedelta(days=1)).day
            date_to = datetime(year_to, month_to, last_day, 23, 59, 59)
            filtered = [v for v in filtered if v.upload_datetime and date_from <= v.upload_datetime <= date_to]

        # 再生回数フィルター
        if self.use_view_filter.isChecked():
            min_v = self.min_views.value()
            max_v = self.max_views.value()
            filtered = [v for v in filtered if v.view_count is not None and min_v <= v.view_count <= max_v]

        # 再生時間フィルター（分→秒に変換して比較）
        if self.use_duration_filter.isChecked():
            min_d = self.min_duration.value() * 60  # 分→秒
            max_d = self.max_duration.value() * 60
            filtered = [v for v in filtered if v.duration is not None and min_d <= v.duration <= max_d]

        # タイトルフィルター
        title_contains = self.title_contains.text().strip()
        title_excludes = self.title_excludes.text().strip()
        if title_contains:
            filtered = [v for v in filtered if title_contains.lower() in v.title.lower()]
        if title_excludes:
            filtered = [v for v in filtered if title_excludes.lower() not in v.title.lower()]

        # 結果を保存して表示
        self.playlist_videos = filtered
        self._update_table(filtered)
        self.playlist_progress_label.setText(f"フィルター適用: {len(filtered)}/{len(self.all_videos)}件")

    def reset_filter(self):
        """フィルターをリセットして全件表示"""
        if not self.all_videos:
            return

        # チェックボックスを外す
        self.use_date_filter.setChecked(False)
        self.use_view_filter.setChecked(False)
        self.use_duration_filter.setChecked(False)
        self.title_contains.clear()
        self.title_excludes.clear()

        # デフォルト値を再設定
        self._set_filter_defaults_from_data(self.all_videos)

        # 全件表示
        self.playlist_videos = self.all_videos
        self._update_table(self.all_videos)
        self.playlist_progress_label.setText(f"全件表示: {len(self.all_videos)}件")

    def clear_playlist(self):
        """再生リストをクリア（URLと一覧を消去）"""
        self.playlist_url_input.clear()
        self.playlist_table.setRowCount(0)
        self.all_videos = []
        self.playlist_videos = []
        self.playlist_progress_label.setText("再生リストを読み込んでください")
        self.playlist_progress.setValue(0)
        self.selected_count_label.setText("選択: 0件")

        # フィルターもリセット
        self.use_date_filter.setChecked(False)
        self.use_view_filter.setChecked(False)
        self.use_duration_filter.setChecked(False)
        self.title_contains.clear()
        self.title_excludes.clear()

        # デフォルト値に戻す
        self.year_from.setCurrentText("2005")
        self.month_from.setCurrentText("1")
        self.year_to.setCurrentText("2026")
        self.month_to.setCurrentText("12")
        self.min_views.setValue(0)
        self.max_views.setValue(1000000000)
        self.min_duration.setValue(0)
        self.max_duration.setValue(1440)

    def on_playlist_error(self, error_msg):
        """再生リスト取得エラー"""
        self.fetch_playlist_btn.setEnabled(True)
        self.cancel_fetch_btn.setEnabled(False)
        self.playlist_progress_label.setText("エラー発生")
        QMessageBox.critical(self, "エラー", f"再生リスト取得エラー:\n{error_msg}")

    def select_all_playlist(self):
        """全選択"""
        for i in range(self.playlist_table.rowCount()):
            item = self.playlist_table.item(i, 0)
            if item:
                item.setCheckState(Qt.CheckState.Checked)
        self.update_selected_count()

    def deselect_all_playlist(self):
        """全解除"""
        for i in range(self.playlist_table.rowCount()):
            item = self.playlist_table.item(i, 0)
            if item:
                item.setCheckState(Qt.CheckState.Unchecked)
        self.update_selected_count()

    def update_selected_count(self):
        """選択数更新"""
        count = 0
        for i in range(self.playlist_table.rowCount()):
            item = self.playlist_table.item(i, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                count += 1
        self.selected_count_label.setText(f"選択: {count}件")

    def download_selected_playlist(self):
        """選択した動画をダウンロード"""
        urls = []
        for i in range(self.playlist_table.rowCount()):
            item = self.playlist_table.item(i, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                if i < len(self.playlist_videos):
                    urls.append(self.playlist_videos[i].url)

        if not urls:
            QMessageBox.warning(self, "エラー", "動画を選択してください")
            return

        # ダウンロード要求シグナルを発行
        self.download_requested.emit(urls)
