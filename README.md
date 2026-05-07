# Crack Detection UI

A Flask + React application for detecting cracks in uploaded video footage with a TensorFlow segmentation model. The backend processes each frame, overlays detected cracks with severity colors, and returns a browser-playable WebM output. The React UI shows upload state, model progress, input preview, detected output preview, and download controls.

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
