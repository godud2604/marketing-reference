import os
import numpy as np
import streamlit as st
from moviepy.editor import (
    AudioFileClip,
    ImageClip,
    CompositeVideoClip,
    VideoFileClip,
    concatenate_videoclips,
    vfx,
)
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

# Pillow 10 compatibility
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

# ==========================================
# 1. 설정 및 초기화
# ==========================================
st.set_page_config(page_title="30초 인생사 메이커", layout="wide")

# 경로/폰트 설정 (프로젝트 루트 기준)
ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
FONT_DIR = os.path.join(ROOT_DIR, "fonts")
FONT_BOLD = os.path.join(FONT_DIR, "GmarketSansTTFBold.ttf")
FONT_MEDIUM = os.path.join(FONT_DIR, "GmarketSansTTFMedium.ttf")
FOOTER_BRAND = "명언 메이커"
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
DEFAULT_LINE_DURATION = 2.5
DEFAULT_MUSIC = os.path.join(os.path.dirname(__file__), "music", "just-relax-11157.mp3")

VIDEO_DIR = os.path.join(os.path.dirname(__file__), "video")
THUMB_DIR = os.path.join("temp", "thumbs")

AVAILABLE_FONTS = {
    "Gmarket Sans Bold": os.path.join(FONT_DIR, "GmarketSansTTFBold.ttf"),
    "Gmarket Sans Medium": os.path.join(FONT_DIR, "GmarketSansTTFMedium.ttf"),
    "Noto Sans KR Regular": os.path.join(FONT_DIR, "NotoSansKR-Regular.ttf"),
    "Noto Sans KR Bold": os.path.join(FONT_DIR, "NotoSansKR-Bold.ttf"),
    "SCDream 5": os.path.join(FONT_DIR, "SCDream5.otf"),
    "SCDream 6": os.path.join(FONT_DIR, "SCDream6.otf"),
    "Binggrae Bold": os.path.join(FONT_DIR, "BinggraeII-Bold.ttf"),
}

# 임시 폴더 생성
os.makedirs("temp", exist_ok=True)
os.makedirs(THUMB_DIR, exist_ok=True)


def _build_default_videos():
    """기본 영상 목록을 생성하고 썸네일을 준비"""
    default_videos = []
    if not os.path.exists(VIDEO_DIR):
        return default_videos

    for filename in sorted(os.listdir(VIDEO_DIR)):
        if not filename.lower().endswith((".mp4", ".mov", ".mkv", ".avi", ".webm")):
            continue

        video_path = os.path.join(VIDEO_DIR, filename)
        if not os.path.isfile(video_path):
            continue

        thumb_path = os.path.join(THUMB_DIR, f"{os.path.splitext(filename)[0]}.jpg")
        if not os.path.exists(thumb_path):
            try:
                with VideoFileClip(video_path) as clip:
                    capture_time = min(1.0, clip.duration / 2) if clip.duration else 0
                    clip.save_frame(thumb_path, t=capture_time)
            except Exception:
                continue

        default_videos.append(
            {
                "label": filename,
                "video_path": video_path,
                "thumbnail": thumb_path,
            }
        )
    return default_videos


DEFAULT_VIDEOS = _build_default_videos()


def _load_video_background(video_path):
    """영상 배경을 리사이즈/크롭해서 반환"""
    clip = VideoFileClip(video_path)
    resized = clip.resize(height=VIDEO_HEIGHT)
    if resized.w < VIDEO_WIDTH:
        resized = resized.resize(width=VIDEO_WIDTH)
    cropped = resized.crop(x_center=resized.w / 2, y_center=resized.h / 2, width=VIDEO_WIDTH, height=VIDEO_HEIGHT)
    return cropped

# ==========================================
# 2. 기능 함수
# ==========================================

def hex_to_rgba(hex_color, alpha=255):
    """#RRGGBB 형태를 RGBA 튜플로 변환"""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return (255, 255, 255, alpha)
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return (r, g, b, alpha)


def load_font(path, size, fallback):
    """폰트 로드"""
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return fallback

def _wrap_title(draw, title_text, font, max_width):
    lines = []

    if " " in title_text:
        words = title_text.split()
        if not words:
            words = [title_text]

        current_line = []
        for word in words:
            test_tokens = current_line + [word]
            test_text = " ".join(test_tokens)
            bbox = draw.textbbox((0, 0), test_text, font=font)
            if bbox[2] - bbox[0] <= max_width or not current_line:
                current_line.append(word)
            else:
                lines.append(current_line)
                current_line = [word]
        if current_line:
            lines.append(current_line)
    else:
        chars = list(title_text)
        current_line = []
        for ch in chars:
            test_tokens = current_line + [ch]
            test_text = "".join(test_tokens)
            bbox = draw.textbbox((0, 0), test_text, font=font)
            if bbox[2] - bbox[0] <= max_width or not current_line:
                current_line.append(ch)
            else:
                lines.append(current_line)
                current_line = [ch]
        if current_line:
            lines.append(current_line)

    # 2줄까지만 사용
    if len(lines) > 2:
        all_tokens = [token for line in lines for token in line]
        mid = len(all_tokens) // 2
        lines = [all_tokens[:mid], all_tokens[mid:]]

    return lines


def create_text_overlay(
    title,
    lines,
    highlight_idx,
    *,
    title_font_path,
    body_font_path,
    brand_font_path,
    title_size=160,
    body_size=60,
    colors=None,
    video_size=(VIDEO_WIDTH, VIDEO_HEIGHT),
    overlay_darkness=140,
    overlay_blur=0,
    brand_text=FOOTER_BRAND,
):
    """영상 위에 깔 투명 텍스트 레이어 생성"""
    colors = colors or {}
    title_color = hex_to_rgba(colors.get("title", "#FFD600"))
    body_color = hex_to_rgba(colors.get("body", "#FFFFFF"))
    brand_color = hex_to_rgba(colors.get("brand", "#FF9800"))
    stroke_fill = (0, 0, 0, 255)
    title_stroke = max(3, title_size // 25)
    body_stroke = max(2, body_size // 25)

    base = Image.new("RGBA", video_size, (0, 0, 0, 0))
    if overlay_darkness > 0:
        dark = Image.new("RGBA", video_size, (0, 0, 0, int(overlay_darkness)))
        base = Image.alpha_composite(base, dark)
    if overlay_blur and overlay_blur > 0:
        # Blur only the background overlay; text stays sharp.
        base = base.filter(ImageFilter.GaussianBlur(overlay_blur))

    draw = ImageDraw.Draw(base)
    font_title = load_font(title_font_path, title_size if highlight_idx != -1 else int(title_size * 1.2), ImageFont.load_default())
    font_body = load_font(body_font_path, body_size, ImageFont.load_default())
    font_brand = load_font(brand_font_path, max(int(body_size * 1.4), 80), ImageFont.load_default())

    brand_x = video_size[0] / 2
    max_title_width = int(video_size[0] * 0.85)
    title_lines = _wrap_title(draw, title, font_title, max_title_width)

    if highlight_idx == -1:
        line_height = int(font_title.size * 1.25)
        total_lines = len(title_lines)
        title_block_height = total_lines * line_height
        title_block_top_y = (video_size[1] / 2) - (title_block_height / 2)
        title_start_y = title_block_top_y + (line_height / 2)

        if brand_text:
            brand_y_intro = title_block_top_y - 200
            draw.text(
                (brand_x, brand_y_intro),
                brand_text,
                font=font_brand,
                fill=brand_color,
                anchor="mm",
                stroke_width=body_stroke,
                stroke_fill=stroke_fill,
            )

        for i, tokens in enumerate(title_lines):
            text_y = title_start_y + (i * line_height)
            full_text = (" " if " " in title else "").join(tokens)
            draw.text(
                (video_size[0] / 2, text_y),
                full_text,
                font=font_title,
                fill=title_color,
                anchor="mm",
                stroke_width=title_stroke,
                stroke_fill=stroke_fill,
            )
        return base

    title_y = 240
    line_height = int(font_title.size * 1.15)
    last_title_bottom = title_y
    for i, tokens in enumerate(title_lines):
        text_y = title_y + (i * line_height)
        full_text = (" " if " " in title else "").join(tokens)
        title_bbox = draw.textbbox(
            (video_size[0] / 2, text_y),
            full_text,
            font=font_title,
            anchor="mm",
            stroke_width=title_stroke,
        )
        last_title_bottom = title_bbox[3]
        draw.text(
            (video_size[0] / 2, text_y),
            full_text,
            font=font_title,
            fill=title_color,
            anchor="mm",
            stroke_width=title_stroke,
            stroke_fill=stroke_fill,
        )

    if brand_text:
        brand_y_play = video_size[1] - 120
        draw.text(
            (brand_x, brand_y_play),
            brand_text,
            font=font_brand,
            fill=brand_color,
            anchor="mm",
            stroke_width=body_stroke,
            stroke_fill=stroke_fill,
        )

    margin_left = 60
    line_spacing = int(body_size * 1.7)
    body_start_y = last_title_bottom + 60
    current_y = body_start_y
    for i, line in enumerate(lines):
        text_color = body_color
        stroke_w = max(1, body_stroke - 1)
        stroke_c = stroke_fill

        number = f"{i+1}."
        num_bbox = draw.textbbox((margin_left, current_y), number, font=font_body, anchor="lt", stroke_width=stroke_w)
        draw.text(
            (margin_left, current_y),
            number,
            font=font_body,
            fill=text_color,
            anchor="lt",
            stroke_width=stroke_w,
            stroke_fill=stroke_c,
        )

        max_width = video_size[0] - num_bbox[2] - 80
        text_lines = []
        current_line = ""
        for ch in line:
            test_line = current_line + ch
            test_bbox = draw.textbbox((0, 0), test_line, font=font_body)
            if test_bbox[2] - test_bbox[0] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    text_lines.append(current_line)
                current_line = ch
        if current_line:
            text_lines.append(current_line)

        text_y = current_y
        for line_text in text_lines:
            draw.text(
                (num_bbox[2] + 20, text_y),
                line_text,
                font=font_body,
                fill=text_color,
                anchor="lt",
                stroke_width=stroke_w,
                stroke_fill=stroke_c,
            )
            text_y += 80

        current_y += line_spacing if len(text_lines) == 1 else line_spacing + int(0.8 * line_height) * (len(text_lines) - 1)

    return base


def create_text_image(
    base_img_path,
    title,
    lines,
    highlight_idx,
    *,
    title_font_path,
    body_font_path,
    brand_font_path,
    title_size=160,
    body_size=60,
    colors=None,
    video_size=(VIDEO_WIDTH, VIDEO_HEIGHT),
    overlay_blur=5,
    overlay_darkness=140,
    brand_text=FOOTER_BRAND,
):
    """이미지 위에 텍스트 합성"""
    colors = colors or {}
    title_color = hex_to_rgba(colors.get("title", "#FFD600"))
    body_color = hex_to_rgba(colors.get("body", "#FFFFFF"))
    brand_color = hex_to_rgba(colors.get("brand", "#FF9800"))
    stroke_fill = (0, 0, 0, 255)
    title_stroke = max(3, title_size // 25)
    body_stroke = max(2, body_size // 25)

    try:
        base = Image.open(base_img_path).convert("RGBA")
        base = ImageOps.fit(base, video_size, Image.Resampling.LANCZOS)
        
        # 어두운 오버레이
        overlay = Image.new("RGBA", base.size, (0, 0, 0, int(overlay_darkness)))
        base = Image.alpha_composite(base, overlay)
        if overlay_blur > 0:
            base = base.filter(ImageFilter.GaussianBlur(overlay_blur))
        
        draw = ImageDraw.Draw(base)
        # 폰트 로드 (없으면 기본 폰트)
        font_title = load_font(title_font_path, title_size if highlight_idx != -1 else int(title_size * 1.2), ImageFont.load_default())
        font_body = load_font(body_font_path, body_size, ImageFont.load_default())
        font_brand = load_font(brand_font_path, max(int(body_size * 1.4), 80), ImageFont.load_default())

        draw = ImageDraw.Draw(base)

        # 브랜드 텍스트
        brand_x = video_size[0] / 2

        # 제목 줄바꿈
        max_title_width = int(video_size[0] * 0.85)
        title_lines = _wrap_title(draw, title, font_title, max_title_width)

        # 인트로(-1): 제목만 중앙에, 본문 숨김
        if highlight_idx == -1:
            line_height = int(font_title.size * 1.25)
            total_lines = len(title_lines)
            title_block_height = total_lines * line_height
            title_block_top_y = (video_size[1] / 2) - (title_block_height / 2)
            title_start_y = title_block_top_y + (line_height / 2)

            if brand_text:
                brand_y_intro = title_block_top_y - 200
                draw.text(
                    (brand_x, brand_y_intro),
                    brand_text,
                    font=font_brand,
                    fill=brand_color,
                    anchor="mm",
                    stroke_width=body_stroke,
                    stroke_fill=stroke_fill,
                )

            for i, tokens in enumerate(title_lines):
                text_y = title_start_y + (i * line_height)
                full_text = (" " if " " in title else "").join(tokens)
                draw.text(
                    (video_size[0] / 2, text_y),
                    full_text,
                    font=font_title,
                    fill=title_color,
                    anchor="mm",
                    stroke_width=title_stroke,
                    stroke_fill=stroke_fill,
                )
            return base

        # 재생 구간 제목 (상단)
        title_y = 240
        line_height = int(font_title.size * 1.15)
        last_title_bottom = title_y
        for i, tokens in enumerate(title_lines):
            text_y = title_y + (i * line_height)
            full_text = (" " if " " in title else "").join(tokens)
            title_bbox = draw.textbbox(
                (video_size[0] / 2, text_y),
                full_text,
                font=font_title,
                anchor="mm",
                stroke_width=title_stroke,
            )
            last_title_bottom = title_bbox[3]
            draw.text(
                (video_size[0] / 2, text_y),
                full_text,
                font=font_title,
                fill=title_color,
                anchor="mm",
                stroke_width=title_stroke,
                stroke_fill=stroke_fill,
            )

        # 브랜드 하단
        if brand_text:
            brand_y_play = video_size[1] - 120
            draw.text(
                (brand_x, brand_y_play),
                brand_text,
                font=font_brand,
                fill=brand_color,
                anchor="mm",
                stroke_width=body_stroke,
                stroke_fill=stroke_fill,
            )

        # 본문
        margin_left = 60
        line_spacing = int(body_size * 1.7)
        body_start_y = last_title_bottom + 60
        current_y = body_start_y
        for i, line in enumerate(lines):
            text_color = body_color
            stroke_w = max(1, body_stroke - 1)
            stroke_c = stroke_fill

            number = f"{i+1}."
            num_bbox = draw.textbbox((margin_left, current_y), number, font=font_body, anchor="lt", stroke_width=stroke_w)
            draw.text(
                (margin_left, current_y),
                number,
                font=font_body,
                fill=text_color,
                anchor="lt",
                stroke_width=stroke_w,
                stroke_fill=stroke_c,
            )

            max_width = video_size[0] - num_bbox[2] - 80
            text_lines = []
            current_line = ""
            for ch in line:
                test_line = current_line + ch
                test_bbox = draw.textbbox((0, 0), test_line, font=font_body)
                if test_bbox[2] - test_bbox[0] <= max_width:
                    current_line = test_line
                else:
                    if current_line:
                        text_lines.append(current_line)
                    current_line = ch
            if current_line:
                text_lines.append(current_line)

            text_y = current_y
            for line_text in text_lines:
                draw.text(
                    (num_bbox[2] + 20, text_y),
                    line_text,
                    font=font_body,
                    fill=text_color,
                    anchor="lt",
                    stroke_width=stroke_w,
                    stroke_fill=stroke_c,
                )
                text_y += 80

            current_y += line_spacing if len(text_lines) == 1 else line_spacing + int(0.8 * line_height) * (len(text_lines) - 1)

        return base
    except Exception as e:
        st.error(f"이미지 처리 오류: {e}")
        return None

# ==========================================
# 3. Streamlit UI
# ==========================================
st.title("🎬 명언 영상 생성기")
st.markdown("디폴트 배경/음악으로도 바로 시작할 수 있어요. 옵션을 조절해 나만의 명언 영상을 만들어보세요.")

# 사이드바: 설정
with st.sidebar:
    st.header("🔧 설정")
    bg_mode = st.radio("배경 선택", ["기본 영상", "직접 이미지 업로드"], index=0)
    selected_video = None
    uploaded_bg = None
    if bg_mode == "기본 영상":
        if DEFAULT_VIDEOS:
            if "selected_default_video" not in st.session_state:
                st.session_state["selected_default_video"] = DEFAULT_VIDEOS[0]

            st.markdown("썸네일을 눌러 기본 영상을 고르세요.")
            video_cols = st.columns(4)
            for idx, video in enumerate(DEFAULT_VIDEOS):
                col = video_cols[idx % 4]
                with col:
                    st.image(video["thumbnail"], caption=video["label"], use_container_width=True)
                    if st.button("이 영상 사용", key=f"video_select_{idx}"):
                        st.session_state["selected_default_video"] = video
                    if st.session_state.get("selected_default_video", {}).get("video_path") == video["video_path"]:
                        st.caption("현재 선택됨")
            selected_video = st.session_state.get("selected_default_video")
        else:
            st.warning("기본 영상이 없습니다. 이미지 업로드를 이용해주세요.")
    elif bg_mode == "직접 이미지 업로드":
        uploaded_bg = st.file_uploader("이미지 업로드", type=["png", "jpg", "jpeg"])

    st.markdown("---")
    music_mode = st.radio(
        "배경 음악",
        ["기본 음악 사용", "직접 업로드", "음악 없음"],
        index=0 if os.path.exists(DEFAULT_MUSIC) else 2,
    )
    music_file = None
    if music_mode == "직접 업로드":
        music_file = st.file_uploader("MP3 업로드", type=["mp3"])
    music_volume = st.slider("배경 음악 볼륨", 0.1, 1.0, 0.3, 0.05, disabled=music_mode == "음악 없음")

    st.markdown("---")
    st.subheader("스타일")
    title_font = st.selectbox("제목 폰트", list(AVAILABLE_FONTS.keys()), index=0)
    body_font = st.selectbox("본문 폰트", list(AVAILABLE_FONTS.keys()), index=1)
    title_size = st.slider("제목 글자 크기", 100, 240, 140, 2)
    body_size = st.slider("본문 글자 크기", 40, 120, 62, 2)
    title_color = st.color_picker("제목 색상", "#FFD600")
    body_color = st.color_picker("본문 기본 색상", "#FFFFFF")
    brand_color = st.color_picker("브랜드 포인트 색상", "#FF9800")
    overlay_blur = st.slider("배경 흐림 정도", 0, 15, 5)
    overlay_darkness = st.slider("배경 어둡게 (0=없음, 255=완전암)", 0, 200, 140, 5)
    show_brand = st.checkbox("하단 브랜드 표시", value=True)
    brand_text = st.text_input("하단 브랜드 텍스트", FOOTER_BRAND, disabled=not show_brand)

# 메인: 내용 입력
silent_line_duration = DEFAULT_LINE_DURATION
col1, col2 = st.columns(2)
with col1:
    title = st.text_input("제목 (썸네일 문구)", "인생에서 후회하는 3가지")
with col2:
    lines_input = st.text_area("본문 내용 (한 줄에 하나씩)", "남의 시선을 너무 의식하지 말 것\n건강을 미리 챙기지 않은 것\n사랑하는 사람에게 표현하지 않은 것", height=180)

# 생성 버튼
if st.button("🎥 영상 생성 시작", type="primary"):
    if not lines_input.strip():
        st.error("본문 내용을 입력해주세요!")
    else:
        status = st.empty()
        progress = st.progress(0)

        bg_path = None
        bg_video_path = None
        status.info("1️⃣ 배경 준비 중...")
        progress.progress(5)

        # 배경 이미지 결정
        if bg_mode == "기본 영상" and selected_video:
            bg_video_path = selected_video["video_path"]
        elif bg_mode == "직접 이미지 업로드" and uploaded_bg:
            upload_ext = uploaded_bg.name.split(".")[-1]
            bg_path = os.path.join("temp", f"uploaded_bg.{upload_ext}")
            with open(bg_path, "wb") as f:
                f.write(uploaded_bg.getbuffer())

        if not bg_video_path and not bg_path and DEFAULT_VIDEOS:
            status.warning("선택한 영상이 없어 기본 영상을 사용합니다.")
            bg_video_path = DEFAULT_VIDEOS[0]["video_path"]

        if not bg_path and not bg_video_path:
            st.error("사용할 수 있는 배경을 찾지 못했습니다.")
            progress.empty()
        else:
            try:
                lines = [line.strip() for line in lines_input.split("\n") if line.strip()]
                if not lines:
                    st.error("본문 내용을 한 줄 이상 입력해주세요.")
                    progress.empty()
                else:
                    clips = []

                    style_options = {
                        "title_font_path": AVAILABLE_FONTS[title_font],
                        "body_font_path": AVAILABLE_FONTS[body_font],
                        "brand_font_path": AVAILABLE_FONTS[title_font],
                        "title_size": title_size,
                        "body_size": body_size,
                        "overlay_blur": overlay_blur,
                        "overlay_darkness": overlay_darkness,
                        "colors": {
                            "title": title_color,
                            "body": body_color,
                            "brand": brand_color,
                        },
                        "brand_text": brand_text if show_brand else "",
                    }

                    video_base_clip = None
                    if bg_video_path:
                        try:
                            video_base_clip = _load_video_background(bg_video_path)
                        except Exception as e:
                            st.error(f"배경 영상을 불러오는 중 오류가 발생했습니다: {e}")
                            progress.empty()
                            st.stop()

                    status.info("2️⃣ 오디오 및 장면 생성 중...")
                    progress.progress(20)

                    for i, line in enumerate(lines):
                        if bg_video_path and video_base_clip:
                            overlay_img = create_text_overlay(
                                title,
                                lines,
                                i,
                                **style_options,
                                video_size=(VIDEO_WIDTH, VIDEO_HEIGHT),
                            )
                            overlay_clip = ImageClip(np.array(overlay_img)).set_duration(silent_line_duration)
                            segment_bg = video_base_clip.fx(vfx.loop, duration=silent_line_duration)
                            segment_clip = CompositeVideoClip([segment_bg, overlay_clip]).set_duration(silent_line_duration)
                            clips.append(segment_clip)
                        else:
                            img = create_text_image(
                                bg_path,
                                title,
                                lines,
                                i,
                                **style_options,
                                video_size=(VIDEO_WIDTH, VIDEO_HEIGHT),
                            )
                            img_line_path = f"temp/line_{i}.png"
                            img.save(img_line_path)

                            videoclip = ImageClip(img_line_path).set_duration(silent_line_duration)
                            clips.append(videoclip)

                        progress.progress(20 + int(60 * (i + 1) / len(lines)))

                    status.info("3️⃣ 최종 렌더링 중...")
                    final_video = concatenate_videoclips(clips, method="compose")

                    # 배경음악 적용
                    if music_mode != "음악 없음":
                        if music_mode == "기본 음악 사용" and os.path.exists(DEFAULT_MUSIC):
                            music_clip = AudioFileClip(DEFAULT_MUSIC)
                        elif music_mode == "직접 업로드" and music_file:
                            music_temp_path = "temp/bg_music.mp3"
                            with open(music_temp_path, "wb") as f:
                                f.write(music_file.getbuffer())
                            music_clip = AudioFileClip(music_temp_path)
                        else:
                            music_clip = None

                        if music_clip:
                            # 길이 맞추기
                            if music_clip.duration < final_video.duration:
                                music_clip = music_clip.loop(duration=final_video.duration)
                            else:
                                music_clip = music_clip.subclip(0, final_video.duration)

                            music_clip = music_clip.volumex(music_volume)
                            final_video = final_video.set_audio(music_clip)

                    output_file = "output_shorts.mp4"
                    final_video.write_videofile(output_file, fps=24, codec="libx264", audio_codec="aac")

                    if video_base_clip:
                        video_base_clip.close()

                    progress.progress(100)
                    status.success("🎉 영상 생성 완료!")
                    _, video_col, _ = st.columns([1, 2, 1])
                    with video_col:
                        st.video(output_file, start_time=0)

                    with open(output_file, "rb") as file:
                        st.download_button("📥 영상 다운로드", file, file_name="shorts.mp4")

            except Exception as e:
                progress.empty()
                st.error(f"오류 발생: {e}")
