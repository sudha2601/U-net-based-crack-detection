---
title: U-Net Crack Detection
sdk: docker
app_port: 7860
---

# Crack Detection UI

A Flask + React application for detecting cracks in uploaded video footage with a TensorFlow segmentation model. The backend processes each frame, overlays detected cracks with severity colors, and returns a browser-playable WebM output. The React UI shows upload state, model progress, input preview, detected output preview, and download controls.

## Live Demo

[Open the deployed app on Hugging Face Spaces](https://huggingface.co/spaces/Sudhanshu2601/u-net-crack-detection)

## Project Structure

- `main.py` - Flask API, model loading, video processing, progress endpoints
- `templates/index.html` - Flask-rendered upload page
- `frontend/` - React/Vite frontend
- `requirements.txt` - Python dependencies

## Model File

The trained model file is intentionally not tracked in Git because it is large. Place it in the project root with this name before running the backend:

```text
crack_segmentation_final.h5
```

For deployment, the app can download the model from Hugging Face with `MODEL_URL`:

```text
https://huggingface.co/Sudhanshu2601/Cracksegementationdataset/resolve/main/crack_segmentation_final%20(2).h5
```

## Backend Setup

```bash
pip install -r requirements.txt
python main.py
```

The Flask API runs at:

```text
http://127.0.0.1:5000
```

## Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The React UI usually runs at:

```text
http://127.0.0.1:5173
```

## Notes

Generated uploads, processed videos, CSV reports, frontend build files, dependencies, and model weights are excluded from Git.

## Free Deployment on Hugging Face Spaces

1. Create a new Space at https://huggingface.co/new-space.
2. Choose **Docker** as the Space SDK.
3. Choose **Public** visibility.
4. Use the free **CPU Basic** hardware.
5. Push this repository's files to the Space repository.
6. The app will use `MODEL_URL` to download the model during startup.

The first build/start can take several minutes because the container installs TensorFlow and downloads the model file.
