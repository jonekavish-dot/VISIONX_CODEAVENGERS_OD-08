# IVACS V-TRACE: Vercel & Render Cloud Deployment Guide

**Project:** IVACS V-TRACE (Vehicle Trust, Route & Evidence Engine)  
**Problem Statement:** OD-08 — License Plate Detection and Recognition from Construction-Site CCTV Footage  

---

## 🚀 Overview & Architecture

When deploying IVACS V-TRACE to cloud hosting platforms (Vercel & Render):

```
+------------------------------------+             +------------------------------------+
|          VERCEL HOSTING            |             |           RENDER HOSTING           |
|  (Static React Command Center UI)  |  HTTP REST  | (Python 3.10 FastAPI Backend Server|
|    https://vtrace.vercel.app       | ----------> |  https://vtrace-backend.onrender.com|
|                                    |  WebSocket  |  YOLOv8 + EasyOCR + SQLite DB)     |
+------------------------------------+             +------------------------------------+
```

* **Vercel:** Hosts the static compiled React / Vite Command Center dashboard (`frontend/dist`).
* **Render:** Hosts the Python FastAPI backend engine (`backend/app.py`), running YOLOv8 vehicle detection, EasyOCR character extraction, 512-D ResNet18 visual embeddings, and SQLite database persistence.

---

## ⚠️ Root Cause: Why Vercel Shows "Offline / No Backend Connected"

When Vercel deploys the frontend independently without configuring the backend URL, `import.meta.env.VITE_API_URL` defaults to empty string (`""`). The UI attempts to fetch `/api/health` relative to the Vercel domain (`https://vtrace.vercel.app/api/health`).

Because Vercel is a static host and does **not** execute Python server code, Vercel returns HTTP 404 HTML, causing the dashboard to indicate **`OFFLINE`**.

---

## 🛠️ Solution 1: Connect Vercel to Render via Environment Variables (Recommended)

### Step 1: Deploy Backend to Render
1. Create a **Web Service** on [Render](https://render.com).
2. Connect repository `https://github.com/jonekavish-dot/VISIONX_CODEAVENGERS_OD-08.git`.
3. Set the build and start commands:
   * **Build Command:** `pip install -r requirements.txt`
   * **Start Command:** `uvicorn backend.app:app --host 0.0.0.0 --port $PORT`
4. Copy your deployed Render service URL (e.g. `https://ivacs-vtrace-backend.onrender.com`).

### Step 2: Configure Environment Variable in Vercel
1. Go to your project dashboard on [Vercel](https://vercel.com).
2. Navigate to **Settings** $\to$ **Environment Variables**.
3. Add a new variable:
   * **Key:** `VITE_API_URL`
   * **Value:** `https://ivacs-vtrace-backend.onrender.com` (replace with your exact Render URL)
   * **Environments:** Select Production, Preview, and Development.
4. Trigger a **Redeploy** on Vercel so Vite embeds the new `VITE_API_URL` into the build bundle.

---

## ⚡ Solution 2: Instant Connection via UI Backend Settings (No Redeploy Required)

If you cannot re-deploy Vercel immediately, use the built-in **Dynamic Backend Connection Manager** directly in the web UI:

1. Open your Vercel deployment URL (e.g., `https://vtrace.vercel.app`).
2. Notice the top header banner: **`BACKEND OFFLINE / DISCONNECTED`**.
3. Click the **`⚡ Backend Server`** button in the top right header.
4. Click **`Render Backend`** preset (or type your Render URL into the input field).
5. Click **`⚡ Test Connection`** to verify live telemetry response.
6. Click **`Save & Apply`**. The browser stores your URL in `localStorage` and immediately reconnects the dashboard live!

---

## 📦 Solution 3: Render Single Unified Deployment (Fullstack on Render)

To run both backend and frontend on a single Render Web Service without Vercel:

1. Use the provided [`render.yaml`](file:///d:/VISIONX/render.yaml) blueprint file.
2. Render automatically installs Python & Node.js, compiles `frontend/dist`, and serves static React assets directly from FastAPI at `http://<your-render-url>/`.

---

## 📁 Deployment Configuration Files Included in Repository

* [`vercel.json`](file:///d:/VISIONX/vercel.json): Configures Vercel build directory and API proxy rewrites to Render.
* [`frontend/vercel.json`](file:///d:/VISIONX/frontend/vercel.json): Vercel configuration for frontend subfolder deployments.
* [`render.yaml`](file:///d:/VISIONX/render.yaml): Render Blueprint specification for 1-click cloud setup.
* [`Procfile`](file:///d:/VISIONX/Procfile): Process file for Uvicorn web server execution on Render/Heroku.
* [`requirements.txt`](file:///d:/VISIONX/requirements.txt): Complete Python dependency list for Linux container runtime.
