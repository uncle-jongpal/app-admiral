"""색·글꼴·아이콘. 화면 부품은 여기 값만 쓴다(색을 파일마다 따로 적지 않기)."""
import math

from PIL import Image, ImageDraw

FONT = "맑은 고딕"
LOGO_FONT = "Segoe UI"
THEME = {"bg": "#0f1115", "side": "#151821", "card": "#1b1e26", "line": "#2a2f3a", "text": "#e8eaf0",
         "sub": "#9aa1b2", "accent": "#5b8cff", "accent_hover": "#4a78e6", "field": "#252a35", "field_hover": "#2f3542",
         "field_press": "#3a4152", "box": "#14171d", "badge": "#1f232c", "track": "#2a2f3a"}
STATE_COLORS = {"idle": "#3a4152", "rec": "#e5484d", "busy": "#f5a524", "ok": "#30a46c", "err": "#8e4ec6"}
STATE_ICONS = {"idle": "●", "rec": "●", "busy": "…", "ok": "✓", "err": "!"}
BRAND = "#2f5bd3"


def make_icon(color, size=64):
    """둥근 사각형 위에 흰 별(제독 계급장). color 로 상태를 표시."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    k = size / 64
    d.rounded_rectangle((2 * k, 2 * k, 62 * k, 62 * k), radius=16 * k, fill=color)
    cx, cy, ro, ri = 32 * k, 33 * k, 21 * k, 8.5 * k
    pts = []
    for i in range(10):
        r = ro if i % 2 == 0 else ri
        ang = -math.pi / 2 + i * math.pi / 5
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    d.polygon(pts, fill="white")
    return img
