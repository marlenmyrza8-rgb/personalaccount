from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

DAYS = ["Дүйсенбі", "Сейсенбі", "Сәрсенбі", "Бейсенбі", "Жұма", "Сенбі", "Жексенбі"]

# Түстер
BG           = (255, 255, 255)
HEADER_BG    = (55,  65,  81)   # қою сұр
HEADER_TEXT  = (255, 255, 255)
DAY_BG       = (243, 244, 246)  # ашық сұр
DAY_TEXT     = (31,  41,  55)
ROW_BG_1     = (255, 255, 255)
ROW_BG_2     = (219, 234, 254)  # ашық көк
ROW_BG_GREEN = (220, 252, 231)  # ашық жасыл
BORDER       = (209, 213, 219)
TEXT_DARK    = (17,  24,  39)
TEXT_MID     = (75,  85,  99)

SUBJECT_ROW_COLORS = [
    (219, 234, 254),  # ашық көк
    (220, 252, 231),  # ашық жасыл
    (254, 243, 199),  # ашық сары
    (252, 231, 243),  # ашық қызғылт
    (237, 233, 254),  # ашық күлгін
    (204, 251, 241),  # ашық бирюза
]


def _load_fonts():
    paths = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    bold_paths = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]

    def try_load(ps, size):
        for p in ps:
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
        return ImageFont.load_default()

    return {
        "title":   try_load(bold_paths, 26),
        "header":  try_load(bold_paths, 16),
        "day":     try_load(bold_paths, 17),
        "subject": try_load(paths, 15),
        "time":    try_load(paths, 14),
        "small":   try_load(paths, 13),
    }


def _text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _draw_text_center(draw, text, font, color, x0, y0, x1, y1):
    tw, th = _text_size(draw, text, font)
    cx = x0 + (x1 - x0 - tw) // 2
    cy = y0 + (y1 - y0 - th) // 2
    draw.text((cx, cy), text, font=font, fill=color)


def generate_schedule_image(schedule_data: dict, student_name: str = "") -> BytesIO:
    subjects_raw = schedule_data.get("subjects", [])

    # Пән → түс маппинг (row түс)
    color_map = {}
    color_idx = 0
    for s in subjects_raw:
        name = s["name"]
        if name not in color_map:
            color_map[name] = SUBJECT_ROW_COLORS[color_idx % len(SUBJECT_ROW_COLORS)]
            color_idx += 1

    # Күн → жолдар тізімі
    day_rows: dict[int, list] = {i: [] for i in range(7)}
    for s in subjects_raw:
        for d in s.get("days", []):
            if 0 <= d <= 6:
                day_rows[d].append({"name": s["name"], "time": s["time"]})

    for d in range(7):
        day_rows[d].sort(key=lambda x: x["time"])

    # Тек пән бар күндерді аламыз
    active_days = [d for d in range(7) if day_rows[d]]
    if not active_days:
        active_days = list(range(5))

    fonts = _load_fonts()

    # Баған өлшемдері
    DAY_COL_W  = 140
    TIME_COL_W = 120
    SUBJ_COL_W = 300
    ROW_H      = 48
    HEADER_H   = 44
    TITLE_H    = 60
    PADDING    = 30

    total_rows = sum(max(len(day_rows[d]), 1) for d in active_days)
    total_w    = PADDING * 2 + DAY_COL_W + TIME_COL_W + SUBJ_COL_W
    total_h    = PADDING + TITLE_H + HEADER_H + total_rows * ROW_H + PADDING

    img  = Image.new("RGB", (total_w, total_h), BG)
    draw = ImageDraw.Draw(img)

    # Сыртқы жиек
    draw.rectangle([0, 0, total_w - 1, total_h - 1], outline=BORDER, width=1)

    # ── Title ──────────────────────────────────────────────────────────
    title = f"{student_name + ' — ' if student_name else ''}Апталық кесте"
    tw, _ = _text_size(draw, title, fonts["title"])
    draw.text(
        ((total_w - tw) // 2, PADDING + 10),
        title, font=fonts["title"], fill=TEXT_DARK
    )

    y = PADDING + TITLE_H

    # ── Header ─────────────────────────────────────────────────────────
    x0 = PADDING
    headers = [
        (DAY_COL_W,  "Күн"),
        (TIME_COL_W, "Уақыт"),
        (SUBJ_COL_W, "Пән"),
    ]
    cx = x0
    for col_w, col_name in headers:
        draw.rectangle([cx, y, cx + col_w, y + HEADER_H], fill=HEADER_BG, outline=BORDER, width=1)
        _draw_text_center(draw, col_name, fonts["header"], HEADER_TEXT,
                          cx, y, cx + col_w, y + HEADER_H)
        cx += col_w

    y += HEADER_H

    # ── Жолдар ─────────────────────────────────────────────────────────
    for day_idx in active_days:
        rows   = day_rows[day_idx]
        n_rows = max(len(rows), 1)
        day_h  = n_rows * ROW_H

        x0 = PADDING

        # Күн ұяшығы (merge — барлық жолдарды қамтиды)
        draw.rectangle(
            [x0, y, x0 + DAY_COL_W, y + day_h],
            fill=DAY_BG, outline=BORDER, width=1
        )
        _draw_text_center(draw, DAYS[day_idx], fonts["day"], DAY_TEXT,
                          x0, y, x0 + DAY_COL_W, y + day_h)

        if not rows:
            # Бос күн
            draw.rectangle(
                [x0 + DAY_COL_W, y, x0 + DAY_COL_W + TIME_COL_W, y + ROW_H],
                fill=ROW_BG_1, outline=BORDER, width=1
            )
            draw.rectangle(
                [x0 + DAY_COL_W + TIME_COL_W, y,
                 x0 + DAY_COL_W + TIME_COL_W + SUBJ_COL_W, y + ROW_H],
                fill=ROW_BG_1, outline=BORDER, width=1
            )
            _draw_text_center(draw, "—", fonts["small"], TEXT_MID,
                              x0 + DAY_COL_W, y,
                              x0 + DAY_COL_W + TIME_COL_W, y + ROW_H)
            _draw_text_center(draw, "Бос", fonts["small"], TEXT_MID,
                              x0 + DAY_COL_W + TIME_COL_W, y,
                              x0 + DAY_COL_W + TIME_COL_W + SUBJ_COL_W, y + ROW_H)
            y += ROW_H
        else:
            for i, item in enumerate(rows):
                row_color = color_map.get(item["name"], ROW_BG_1)
                ry0 = y + i * ROW_H
                ry1 = ry0 + ROW_H

                # Уақыт ұяшығы
                tx0 = x0 + DAY_COL_W
                tx1 = tx0 + TIME_COL_W
                draw.rectangle([tx0, ry0, tx1, ry1],
                               fill=row_color, outline=BORDER, width=1)
                _draw_text_center(draw, item["time"], fonts["time"], TEXT_DARK,
                                  tx0, ry0, tx1, ry1)

                # Пән ұяшығы
                sx0 = tx1
                sx1 = sx0 + SUBJ_COL_W
                draw.rectangle([sx0, ry0, sx1, ry1],
                               fill=row_color, outline=BORDER, width=1)
                _draw_text_center(draw, item["name"], fonts["subject"], TEXT_DARK,
                                  sx0, ry0, sx1, ry1)

            y += day_h

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf