# The "Golden Path": Packaging Python AI Apps for macOS
**Target Audience**: Developers who have a Python script/repo and want a professional `.dmg` installer.
**Philosophy**: "Fail-Proof & Future-Proof". We use **Electron** (UI), **FastAPI** (Backend), and **uv** (Distribution).

---

## 🏗️ Phase 1: The Stack Selection (Don't Think, Just Choose This)
To avoid pain, stick exactly to this stack. It is battle-tested.
*   **Frontend**: React + Tailwind (via Vite). *Why? It's the industry standard for UI.*
*   **Backend**: **FastAPI**. *Why? It's async, typesafe, and auto-generates docs. Flask is dead for AI.*
*   **Wrapper**: Electron. *Why? It's the only way to get full OS control.*
*   **Manager**: **uv**. *Why? It solves the "dependency hell" without needing 5GB Docker images.*

---

## 📂 Phase 2: Project Structure
Organize your folder like this. Do not mix files.

```text
my-app/
├── python/                 <-- YOUR PYTHON CODE
│   ├── pyproject.toml      <-- Dependencies (managed by uv)
│   ├── api.py              <-- FastAPI Entry Point
│   └── core/               <-- Your existing python scripts
├── electron/               <-- THE WRAPPER
│   ├── package.json
│   ├── forge.config.ts
│   ├── src/
│   │   ├── main.ts         <-- The Master Controller
│   │   └── preload.ts
│   └── assets/             <-- Icons, Backgrounds, and the 'uv' binary
└── README.md
```

---

## 🛠️ Phase 3: The Setup (Step-by-Step)

### 1. Prepare Python (The Backend)
Create `python/api.py`. This is where you expose your functions to the UI.

```python
# python/api.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

app = FastAPI()

# Allow Electron to talk to us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok", "pid": os.getpid()}

@app.get("/run-my-ai-task")
async def run_task(prompt: str):
    # Call your complex logic here
    return {"result": f"Processed {prompt}"}

if __name__ == "__main__":
    # IMPORTANT: Listen on localhost only!
    port = int(os.environ.get("MYAPP_PORT", 8000))
    uvicorn.run(app, host="127.0.0.1", port=port)
```

### 2. Prepare Electron (The Controller)
This is the hardest part. Copy this logic into `electron/src/main.ts`. It handles the lifecycle.

```typescript
// Key logic to spawn the Python backend safely
const setupPython = async () => {
  // 1. Where is the environment?
  const userDataPath = app.getPath('userData');
  const venvPath = path.join(userDataPath, '.venv');
  const pythonExec = path.join(venvPath, 'bin', 'python');
  
  // 2. Install if missing (First Run Experience)
  if (!fs.existsSync(venvPath)) {
    // Show a loading window here...
    // Run 'uv sync' command using the bundled 'uv' binary in resources
    const uvPath = isDev ? 'uv' : path.join(process.resourcesPath, 'uv');
    execSync(`"${uvPath}" venv "${venvPath}"`, { ... });
    execSync(`"${uvPath}" pip install -r requirements.txt`, { ... });
  }

  // 3. Spawn the Process
  const freePort = await getFreePort(); // You need a port finder
  const serverProcess = spawn(pythonExec, ['api.py'], {
    env: { ...process.env, MYAPP_PORT: freePort.toString() }
  });

  // 4. Wait for Health Check
  await waitForHealthCheck(freePort);

  return freePort; // Pass this port to your Frontend Window
};
```

### 3. Configure the Builder (`forge.config.ts`)
This is where packaging happens. You must tell Forge to include your Python code.

```typescript
const config: ForgeConfig = {
  packagerConfig: {
    icon: './assets/icon', // Path to icon.icns (without extension)
    extraResource: [
      '../python',           // Copy the entire python folder
      './assets/uv'          // Copy the standalone uv binary
    ]
  },
  makers: [
    new MakerDMG({
      icon: './assets/icon.icns',
      background: './assets/dmg-bg.png', // 600x400 PNG
      contents: [
        // Center your app in the DMG window
        { x: 190, y: 200, type: 'file', path: process.cwd() + '/out/MyApp.app' },
        { x: 410, y: 200, type: 'link', path: '/Applications' }
      ]
    })
  ]
};
```

---

## 🎨 Phase 4: Polish (The "Pro" Touches)

### 1. Icons are Hard
Don't just use a PNG. macOS needs an `.icns` file with all resolutions (16x16 to 1024x1024).
*   **Fail-Proof Way**:
    1.  Get a 1024x1024 PNG.
    2.  Use a script (like `iconutil` on Mac) to generate the `.icns`.
    3.  **Use Rounded Corners**: macOS icons are "squircles". If your PNG is a square, it will look ugly. Mask it first!

### 2. The Loading Screen
Your Python server takes 2-5 seconds to start (importing torch/mlx takes time!).
*   **Do**: Show a "Initializing AI Core..." splash screen immediately.
*   **Don't**: Wait for Python to start before opening any window. The user will think the app is broken.

### 3. Distribution Size
*   **Don't** ship `node_modules` or `.venv`.
*   **Do** ship `uv`.
*   **Result**: Your DMG is small (~100MB). The user downloads the heavy AI libraries (Torch/MLX) on *their* machine during the first run setup. This is 10x friendlier than downloading a 4GB installer.

---

## 🚀 Phase 5: The Build Command
When you are ready to ship:

1.  **Download uv**: Get the standalone binary and put it in `electron/assets/uv`.
2.  **Clean Build**: `rm -rf out`
3.  **Make**: `npm run make`

You will get a `.dmg` in `out/make/`. Open it, drag to Apps, and you are done.

---
**Summary Checklist for Success**:
- [ ] Backend is **FastAPI** (not Flask).
- [ ] Dependency Manager is **uv**.
- [ ] Frontend communicates via **HTTP** (localhost), not weird bindings.
- [ ] App Icon is a **Squircle .icns**.
- [ ] DMG background is customized.
