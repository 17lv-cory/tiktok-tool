# app.py - 最終完成版 (1行40枚グリッドレイアウト対応)

import math
import shutil
from io import BytesIO
from pathlib import Path

import cv2
import streamlit as st
import yt_dlp
from PIL import Image


def download_video_with_library(url, temp_dir):
    """yt-dlpライブラリを直接使って動画をダウンロードする"""
    try:
        ydl_opts = {
            'outtmpl': str(temp_dir / '%(id)s.%(ext)s'),
            'restrictfilenames': True,
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            st.info("動画情報を取得しています...")
            info = ydl.extract_info(url, download=False)
            video_id = info.get('id', 'unknown_id')
            ext = info.get('ext', 'mp4')
            filename = f"{video_id}.{ext}"
            output_path = temp_dir / filename
            st.info(f"動画ファイル「{filename}」のダウンロードを開始します...")
            ydl.download([url])
            st.info("ダウンロードが完了しました。")
        return output_path, video_id
    except yt_dlp.utils.DownloadError:
        st.error("動画のダウンロードに失敗しました。URLがサポートされていないか、動画が非公開の可能性があります。")
        return None, None
    except Exception as e:
        st.error(f"予期せぬエラーが発生しました: {e}")
        return None, None


def create_contact_sheet_image(video_path, capture_per_second, progress_bar):
    """動画から画像を抽出し、リサイズしてグリッド状のコンタクトシートを作成する"""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        st.error("エラー: 動画ファイルを開けませんでした。")
        return None, 0

    video_fps = cap.get(cv2.CAP_PROP_FPS)
    frame_total = int(cap.get(7))  # cv2.CAP_FRAME_COUNT の代わりに背番号7を直接指定
    if video_fps == 0:
        st.error("エラー: 動画のFPSが取得できませんでした。")
        return None, 0

    capture_interval = math.floor(video_fps / capture_per_second)
    if capture_interval == 0:
        capture_interval = 1

    images = []
    frame_count = 0
    RESIZED_WIDTH = 240

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_count % capture_interval == 0:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_frame)
            width, height = pil_image.size
            aspect_ratio = height / width
            new_height = int(RESIZED_WIDTH * aspect_ratio)
            resized_image = pil_image.resize((RESIZED_WIDTH, new_height), Image.Resampling.LANCZOS)
            images.append(resized_image)
        frame_count += 1
        if frame_total > 0:
            progress_bar.progress(frame_count / frame_total, text="フレームを抽出中...")
    cap.release()

    if not images:
        st.warning("警告: 1枚も画像をキャプチャできませんでした。")
        return None, 0

    # ★★★ ご希望の「1行40枚」設定 ★★★
    IMAGES_PER_ROW = 40
    
    num_images = len(images)
    img_width, img_height = images[0].size
    
    cols = min(num_images, IMAGES_PER_ROW)
    rows = math.ceil(num_images / cols)
    
    total_width = cols * img_width
    total_height = rows * img_height
    grid_image = Image.new('RGB', (total_width, total_height))
    
    for i, img in enumerate(images):
        col_index = i % cols
        x = col_index * img_width
        row_index = i // cols
        y = row_index * img_height
        grid_image.paste(img, (x, y))

    return grid_image, num_images


# --- ここからWebアプリの見た目と操作を定義 ---
st.set_page_config(page_title="TikTok コンタクトシート作成ツール", layout="wide")
st.title("🎬 TikTok コンタクトシート作成ツール")
st.info("TikTok動画のURLを貼り付けると、画像を連結したコンタクトシートをグリッド形式で作成します。")

with st.form("input_form"):
    tiktok_url = st.text_input("TikTok動画のURLを貼り付けてください", placeholder="https://www.tiktok.com/@...")
    capture_rate = st.number_input("1秒間にキャプチャする枚数", min_value=1, max_value=30, value=2, step=1)
    submitted = st.form_submit_button("コンタクトシートを作成する")

if submitted:
    if not tiktok_url:
        st.error("URLを入力してください。")
    else:
        temp_dir = Path("./temp_video_for_webapp")
        temp_dir.mkdir(exist_ok=True)
        
        video_path, video_id = download_video_with_library(tiktok_url, temp_dir)

        if video_path and video_path.exists():
            st.success(f"STEP 1/2: 動画のダウンロードが完了しました。(ID: {video_id})")
            
            progress_text = "STEP 2/2: コンタクトシートを作成しています..."
            my_bar = st.progress(0, text=progress_text)

            contact_sheet_image, image_count = create_contact_sheet_image(video_path, capture_rate, my_bar)
            my_bar.progress(1.0, text="作成完了！")

            if contact_sheet_image:
                st.success(f"🎉 コンタクトシートが完成しました！ ({image_count}枚の画像を結合)")
                st.subheader("プレビュー")
                st.image(contact_sheet_image)

                buf = BytesIO()
                contact_sheet_image.save(buf, format="JPEG", quality=95)
                img_bytes = buf.getvalue()

                st.download_button(
                    label="画像をダウンロード",
                    data=img_bytes,
                    file_name=f"contact_sheet_{video_id}_{capture_rate}fps.jpg",
                    mime="image/jpeg"
                )
        
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
