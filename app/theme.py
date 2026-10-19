"""
Shared palette + application stylesheet.

Neutral graphite surfaces, one blue accent for focus/selection, and
light-on-dark primary buttons. Tools should use these tokens instead of
hard-coding colours.
"""

BG        = "#161617"   # page background
BG_SUNKEN = "#111112"   # sidebar, preview wells
SURFACE   = "#1c1c1e"   # inputs, cards
SURFACE_2 = "#232326"   # buttons
HOVER     = "#2c2c2f"
BORDER    = "#2e2e31"
BORDER_2  = "#3a3a3e"

TEXT      = "#ececec"
TEXT_2    = "#a8a8ad"
TEXT_3    = "#6e6e73"

ACCENT    = "#5e9cff"
OK        = "#5bb98c"
WARN      = "#e0a84a"
ERROR     = "#e5534b"

UI_FONT   = "-apple-system, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif"
MONO_FONT = "Menlo, Consolas, 'DejaVu Sans Mono', monospace"

STYLESHEET = f"""
    QMainWindow, QWidget {{ background: {BG}; color: {TEXT}; font-size: 13px; }}

    QGroupBox {{
        border: 1px solid {BORDER};
        border-radius: 6px;
        margin-top: 18px;
        padding: 12px 10px 10px 10px;
        font-weight: 600;
        color: {TEXT_2};
        font-size: 12px;
    }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 2px; padding: 0 0 4px 0; }}

    QPushButton {{
        background: {SURFACE_2};
        color: {TEXT};
        border: 1px solid {BORDER_2};
        border-radius: 5px;
        padding: 6px 14px;
        font-size: 13px;
    }}
    QPushButton:hover    {{ background: {HOVER}; }}
    QPushButton:pressed  {{ background: {SURFACE}; }}
    QPushButton:disabled {{ color: {TEXT_3}; border-color: {BORDER}; }}

    QPushButton#primary {{
        background: {TEXT};
        color: #111112;
        border: 1px solid {TEXT};
        font-weight: 600;
        padding: 7px 16px;
    }}
    QPushButton#primary:hover    {{ background: #d6d6d8; border-color: #d6d6d8; }}
    QPushButton#primary:disabled {{ background: {SURFACE_2}; color: {TEXT_3}; border-color: {BORDER}; }}

    QPushButton#danger       {{ background: #3a1d1b; border-color: #9a3b36; }}
    QPushButton#danger:hover {{ background: #4a2320; }}

    QPushButton#chip {{
        background: transparent;
        color: {TEXT_2};
        border: 1px solid {BORDER_2};
        border-radius: 13px;
        padding: 3px 12px;
        font-size: 12px;
    }}
    QPushButton#chip:hover   {{ color: {TEXT}; background: {SURFACE}; }}
    QPushButton#chip:checked {{ color: #111112; background: {TEXT}; border-color: {TEXT}; }}

    QLineEdit, QTextEdit, QPlainTextEdit {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 5px;
        padding: 5px 8px;
        color: {TEXT};
        selection-background-color: {ACCENT};
    }}
    QLineEdit:focus, QTextEdit:focus {{ border-color: {ACCENT}; }}

    QComboBox, QSpinBox {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 5px;
        padding: 4px 8px;
        color: {TEXT};
    }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox QAbstractItemView {{
        background: {SURFACE_2};
        color: {TEXT};
        border: 1px solid {BORDER_2};
        selection-background-color: {HOVER};
    }}

    QCheckBox {{ color: {TEXT_2}; spacing: 7px; }}
    QCheckBox::indicator {{
        width: 14px; height: 14px; border-radius: 3px;
        border: 1px solid {TEXT_3}; background: {SURFACE};
    }}
    QCheckBox::indicator:hover   {{ border-color: {TEXT_2}; }}
    QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}

    QSlider::groove:horizontal {{ height: 3px; background: {BORDER_2}; border-radius: 1px; }}
    QSlider::handle:horizontal {{
        background: {TEXT}; width: 14px; height: 14px;
        margin: -6px 0; border-radius: 7px;
    }}
    QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 1px; }}

    QLabel {{ color: {TEXT_2}; background: transparent; }}
    QLabel#section {{ color: {TEXT_3}; font-size: 12px; font-weight: 600; }}

    QScrollArea {{ border: none; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {BORDER_2}; border-radius: 3px; min-height: 30px; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
    QScrollBar::handle:horizontal {{ background: {BORDER_2}; border-radius: 3px; min-width: 30px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

    QProgressBar {{
        background: {SURFACE}; border: none;
        border-radius: 2px; text-align: center; color: {TEXT_2}; font-size: 11px;
    }}
    QProgressBar::chunk {{ background: {ACCENT}; border-radius: 2px; }}

    QSplitter::handle {{ background: {BORDER}; }}
    QToolTip {{ background: {SURFACE_2}; color: {TEXT}; border: 1px solid {BORDER_2}; padding: 4px 6px; }}
"""
