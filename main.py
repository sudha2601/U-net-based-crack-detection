import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import numpy as np
import cv2
import tensorflow as tf
import csv
import threading
import urllib.request
import uuid

from flask import Flask, jsonify, render_template, request, send_file
from collections import deque
from skimage.morphology import skeletonize
from tensorflow.keras.models import load_model
from flask_cors import CORS
from werkzeug.utils import secure_filename

# ============================================================
# FLASK APP
# ============================================================
app = Flask(
    __name__,
    static_folder=os.path.join("frontend", "dist"),
    static_url_path=""
)
CORS(app)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

JOBS = {}
JOBS_LOCK = threading.Lock()

# -----------------------------
# FORCE CPU
# -----------------------------
tf.config.set_visible_devices([], 'GPU')

# ============================================================
# CONFIG
# ============================================================
IMG_HEIGHT = 384
IMG_WIDTH  = 384

MODEL_PATH = os.environ.get("MODEL_PATH", "crack_segmentation_final.h5")
MODEL_URL = os.environ.get("MODEL_URL")

# Camera calibration
DISTANCE_MM = 80
FOCAL_MM    = 24
SENSOR_MM   = 6.4
IMAGE_WIDTH = IMG_WIDTH

PIXEL_TO_MM = (DISTANCE_MM * SENSOR_MM) / (FOCAL_MM * IMAGE_WIDTH)

# Detection thresholds
PRED_THRESH     = 0.80
MIN_CRACK_AREA  = 150
MIN_CRACK_WIDTH = 0.08

# Severity bands
LOW_TH  = 0.5
HIGH_TH = 1

# Temporal smoothing
SMOOTH_FRAMES = 5
WIDTH_SMOOTH  = 7

# Consecutive-frame gate
MIN_CONSECUTIVE = 3

MORPH_KERNEL = cv2.getStructuringElement(
    cv2.MORPH_ELLIPSE,
    (3, 3)
)

# ============================================================
# LOAD MODEL
# ============================================================
print("Loading model...")

if not os.path.exists(MODEL_PATH) and MODEL_URL:
    print("Downloading model...")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)

if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(
        f"Model file not found at {MODEL_PATH}. Set MODEL_PATH or MODEL_URL."
    )

model = load_model(MODEL_PATH, compile=False)

dummy = np.zeros((1, IMG_HEIGHT, IMG_WIDTH, 3))

for _ in range(3):
    model.predict(dummy, verbose=0)

print("Model loaded successfully")

# ============================================================
# HELPERS
# ============================================================

def post_process(smoothed_pred):

    binary = (smoothed_pred > PRED_THRESH).astype(np.uint8)

    bridged = cv2.dilate(
        binary,
        MORPH_KERNEL,
        iterations=1
    )

    bridged = cv2.morphologyEx(
        bridged,
        cv2.MORPH_CLOSE,
        MORPH_KERNEL,
        iterations=1
    )

    skeleton = skeletonize(
        bridged > 0
    ).astype(np.uint8)

    return binary, skeleton


def measure_width(binary, skeleton):

    if int(np.sum(binary)) < MIN_CRACK_AREA:
        return 0.0

    dist = cv2.distanceTransform(
        binary.astype(np.uint8),
        cv2.DIST_L2,
        5
    )

    pts = dist[skeleton == 1]

    if len(pts) == 0:
        return 0.0

    return float(np.max(pts)) * 2 * PIXEL_TO_MM


def get_severity(width_mm):

    if width_mm < LOW_TH:
        return "Minor", (0, 255, 255)

    elif width_mm < HIGH_TH:
        return "Moderate", (0, 165, 255)

    else:
        return "Severe", (0, 0, 255)


def format_timestamp(seconds):

    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60

    return f"{h:02d}:{m:02d}:{s:06.3f}"


def update_job(job_id, **updates):

    with JOBS_LOCK:
        if job_id in JOBS:
            JOBS[job_id].update(updates)


def wants_json_response():

    best = request.accept_mimetypes.best_match(
        ["application/json", "text/html"]
    )

    return best == "application/json" or request.is_json

# ============================================================
# VIDEO PROCESSING
# ============================================================

def process_video(video_path, output_video, output_csv, progress_callback=None):

    cap = cv2.VideoCapture(video_path)

    fps = cap.get(cv2.CAP_PROP_FPS) or 25

    v_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    v_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0

    if progress_callback:
        progress_callback(0, total_frames)

    fourcc = cv2.VideoWriter_fourcc(*'VP80')

    out = cv2.VideoWriter(
        output_video,
        fourcc,
        fps,
        (v_w, v_h)
    )

    if not out.isOpened():
        cap.release()
        raise RuntimeError("Could not create browser-playable output video")

    csv_file = open(output_csv, 'w', newline='')

    csv_writer = csv.writer(csv_file)

    csv_writer.writerow([
        "Timestamp",
        "Seconds",
        "Max Width (mm)",
        "Severity",
        "Crack Area (px)",
    ])

    pred_buffer = deque(maxlen=SMOOTH_FRAMES)
    width_buffer = deque(maxlen=WIDTH_SMOOTH)

    consec_count = 0
    pending_rows = []

    frame_id = 0

    while cap.isOpened():

        ret, frame = cap.read()

        if not ret:
            break

        timestamp_s = frame_id / fps

        # preprocess
        img = cv2.resize(
            frame,
            (IMG_WIDTH, IMG_HEIGHT)
        ) / 255.0

        tensor = np.expand_dims(img, 0)

        # predict
        pred = model.predict(
            tensor,
            verbose=0
        )[0].squeeze()

        pred_buffer.append(pred)

        smoothed = np.mean(
            pred_buffer,
            axis=0
        )

        # post process
        binary, skeleton = post_process(smoothed)

        # measure
        raw_width = measure_width(binary, skeleton)

        width_buffer.append(raw_width)

        avg_width = float(np.mean(width_buffer))

        crack_area = int(np.sum(binary))

        crack_detected = avg_width > MIN_CRACK_WIDTH

        # logging
        if crack_detected:

            consec_count += 1

            row = [
                format_timestamp(timestamp_s),
                round(timestamp_s, 3),
                round(avg_width, 3),
                get_severity(avg_width)[0],
                crack_area,
            ]

            pending_rows.append(row)

            if consec_count == MIN_CONSECUTIVE:

                for r in pending_rows:
                    csv_writer.writerow(r)

            elif consec_count > MIN_CONSECUTIVE:
                csv_writer.writerow(row)

        else:
            consec_count = 0
            pending_rows = []

        # overlay
        overlay = frame.copy()

        severity, color = get_severity(avg_width)

        if crack_detected:

            binary_resized = cv2.resize(
                binary,
                (v_w, v_h),
                interpolation=cv2.INTER_NEAREST
            )

            overlay[binary_resized == 1] = color

            label = f"Crack {avg_width:.2f} mm [{severity}]"

            status_color = color

        else:

            label = "No Crack Detected"

            status_color = (180, 180, 180)

        cv2.putText(
            overlay,
            f"Time : {format_timestamp(timestamp_s)}",
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (0, 255, 0),
            2
        )

        cv2.putText(
            overlay,
            label,
            (20, 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            status_color,
            2
        )

        out.write(overlay)

        frame_id += 1

        if progress_callback:
            progress_callback(frame_id, total_frames)

    cap.release()
    out.release()
    csv_file.close()


def process_video_job(job_id):

    with JOBS_LOCK:
        job = JOBS.get(job_id)

    if not job:
        return

    try:
        update_job(job_id, status="processing", progress=0)

        def progress_callback(frame_id, total_frames):
            if total_frames > 0:
                progress = min(99, int((frame_id / total_frames) * 100))
            else:
                progress = 0

            update_job(
                job_id,
                progress=progress,
                processed_frames=frame_id,
                total_frames=total_frames,
            )

        process_video(
            job["input_path"],
            job["output_video"],
            job["output_csv"],
            progress_callback=progress_callback
        )

        update_job(job_id, status="done", progress=100)

    except Exception as exc:
        update_job(job_id, status="error", error=str(exc), progress=0)

# ============================================================
# ROUTES
# ============================================================

@app.route('/')
def home():
    react_index = os.path.join(app.static_folder, "index.html")

    if os.path.exists(react_index):
        return send_file(react_index)

    return render_template('index.html')


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})


@app.route('/upload', methods=['POST'])
def upload_video():

    if 'video' not in request.files:
        if wants_json_response():
            return jsonify({"error": "No file uploaded"}), 400

        return "No file uploaded", 400

    file = request.files['video']

    if file.filename == '':
        if wants_json_response():
            return jsonify({"error": "No selected file"}), 400

        return "No selected file", 400

    job_id = uuid.uuid4().hex
    filename = secure_filename(file.filename) or f"video_{job_id}"
    base_name = os.path.splitext(filename)[0]
    unique_base = f"{base_name}_{job_id[:8]}"

    input_path = os.path.join(
        UPLOAD_FOLDER,
        unique_base + os.path.splitext(filename)[1]
    )

    file.save(input_path)

    output_video = os.path.join(
        OUTPUT_FOLDER,
        "output_" + unique_base + ".webm"
    )

    output_csv = os.path.join(
        OUTPUT_FOLDER,
        "report_" + unique_base + ".csv"
    )

    if wants_json_response():
        with JOBS_LOCK:
            JOBS[job_id] = {
                "status": "queued",
                "progress": 0,
                "processed_frames": 0,
                "total_frames": 0,
                "input_path": input_path,
                "output_video": output_video,
                "output_csv": output_csv,
                "error": "",
            }

        worker = threading.Thread(
            target=process_video_job,
            args=(job_id,),
            daemon=True
        )
        worker.start()

        return jsonify({"job_id": job_id})

    # process video
    process_video(
        input_path,
        output_video,
        output_csv
    )

    # return output video
    return send_file(
        output_video,
        mimetype="video/webm",
        as_attachment=False,
        download_name=os.path.basename(output_video)
    )


@app.route('/progress/<job_id>', methods=['GET'])
def job_progress(job_id):

    with JOBS_LOCK:
        job = JOBS.get(job_id)

        if not job:
            return jsonify({"error": "Job not found"}), 404

        return jsonify({
            "status": job["status"],
            "progress": job["progress"],
            "processed_frames": job["processed_frames"],
            "total_frames": job["total_frames"],
            "error": job["error"],
        })


@app.route('/result/<job_id>', methods=['GET'])
def job_result(job_id):

    with JOBS_LOCK:
        job = JOBS.get(job_id)

    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job["status"] != "done":
        return jsonify({"error": "Job is not complete"}), 409

    return send_file(
        job["output_video"],
        mimetype="video/webm",
        as_attachment=False,
        download_name=os.path.basename(job["output_video"])
    )

# ============================================================
# RUN APP
# ============================================================

if __name__ == '__main__':
    app.run(debug=True)
