/**
 * ClonEpub Electron Main Process
 * 
 * Manages app lifecycle, Python backend, and native dialogs.
 */

import { app, BrowserWindow, dialog, ipcMain, shell } from 'electron';
import { spawn, execSync, ChildProcess } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import log from 'electron-log';

// ─────────────────────────────────────────────────────────────────────────────
// Configuration
// ─────────────────────────────────────────────────────────────────────────────

const isDev = !app.isPackaged;

// Resource paths differ between dev and packaged app
const resourcesPath = isDev
    ? path.join(__dirname, '..')
    : process.resourcesPath!;

// In dev mode, Python source is in parent directory
const pythonSrcPath = isDev
    ? path.join(__dirname, '..', '..', 'clonepub')
    : path.join(resourcesPath, 'clonepub');

// In dev mode, use system uv; in packaged mode, use bundled uv
const uvPath = isDev
    ? 'uv'  // Assume uv is in PATH for development
    : path.join(resourcesPath, 'uv');

// User data directory: ~/Library/Application Support/ClonEpub
const userDataPath = app.getPath('userData');
const venvPath = path.join(userDataPath, '.venv');
const configPath = path.join(userDataPath, 'config.json');

// Python server configuration
const PYTHON_PORT = 8765;
const PYTHON_HOST = '127.0.0.1';

// Global references
let mainWindow: BrowserWindow | null = null;
let pythonProcess: ChildProcess | null = null;
let setupWindow: BrowserWindow | null = null;

// ─────────────────────────────────────────────────────────────────────────────
// Logging Setup
// ─────────────────────────────────────────────────────────────────────────────

log.initialize();
log.transports.file.level = 'info';
log.info(`ClonEpub starting v${app.getVersion()}`);
log.info(`Running in ${isDev ? 'development' : 'production'} mode`);
log.info(`Resources path: ${resourcesPath}`);
log.info(`User data path: ${userDataPath}`);

// ─────────────────────────────────────────────────────────────────────────────
// Python Environment Setup
// ─────────────────────────────────────────────────────────────────────────────

function getPythonPath(): string {
    return path.join(venvPath, 'bin', 'python');
}

function isEnvironmentReady(): boolean {
    const pythonPath = getPythonPath();
    return fs.existsSync(pythonPath);
}

async function showSetupWindow(): Promise<void> {
    setupWindow = new BrowserWindow({
        width: 500,
        height: 350,
        frame: false,
        resizable: false,
        center: true,
        backgroundColor: '#0f1419',
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true
        }
    });

    const setupHtmlPath = isDev
        ? path.join(__dirname, '..', 'assets', 'setup.html')
        : path.join(resourcesPath, 'app', 'assets', 'setup.html');

    setupWindow.loadFile(setupHtmlPath);
}

async function setupPythonEnvironment(): Promise<boolean> {
    log.info('Setting up Python environment...');

    await showSetupWindow();

    try {
        // Ensure user data directory exists
        if (!fs.existsSync(userDataPath)) {
            fs.mkdirSync(userDataPath, { recursive: true });
        }

        // Determine project path (where pyproject.toml is)
        const projectPath = isDev
            ? path.join(__dirname, '..', '..')
            : resourcesPath;

        log.info(`Running uv sync in ${projectPath}...`);
        log.info(`UV path: ${uvPath}`);
        log.info(`Venv path: ${venvPath}`);

        // Run uv sync to create venv and install dependencies
        // UV_PROJECT_ENVIRONMENT tells uv where to put the venv
        execSync(`"${uvPath}" sync --project "${projectPath}"`, {
            cwd: userDataPath,
            env: {
                ...process.env,
                UV_PROJECT_ENVIRONMENT: venvPath,
                HOME: app.getPath('home')
            },
            stdio: 'pipe',
            timeout: 600000 // 10 minute timeout for slow connections
        });

        log.info('Python environment setup complete!');
        return true;
    } catch (error) {
        log.error('Failed to setup Python environment:', error);

        dialog.showErrorBox(
            'Setup Failed',
            `Failed to install Python dependencies.\n\nError: ${error}\n\nPlease check the logs at:\n${log.transports.file.getFile().path}`
        );

        if (setupWindow) {
            setupWindow.close();
            setupWindow = null;
        }

        return false;
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Python Backend Management
// ─────────────────────────────────────────────────────────────────────────────

async function waitForServer(timeout: number = 60000): Promise<boolean> {
    const startTime = Date.now();
    const url = `http://${PYTHON_HOST}:${PYTHON_PORT}/health`;
    const http = require('http');

    log.info(`Waiting for Python server at ${url}...`);

    return new Promise((resolve) => {
        const checkServer = () => {
            if (Date.now() - startTime >= timeout) {
                log.error(`Python server failed to start within ${timeout}ms`);
                resolve(false);
                return;
            }

            const req = http.get(url, (res: any) => {
                if (res.statusCode === 200) {
                    log.info('Python server is ready!');
                    resolve(true);
                } else {
                    setTimeout(checkServer, 500);
                }
            });

            req.on('error', () => {
                // Server not ready yet, keep trying
                setTimeout(checkServer, 500);
            });

            req.setTimeout(2000, () => {
                req.destroy();
                setTimeout(checkServer, 500);
            });
        };

        // Give the Python process a moment to start
        setTimeout(checkServer, 1000);
    });
}

async function startPythonBackend(): Promise<boolean> {
    const pythonPath = getPythonPath();

    log.info(`Starting Python backend with ${pythonPath}...`);

    // Set PYTHONPATH to include the clonepub module
    const moduleParentPath = isDev
        ? path.join(__dirname, '..', '..')
        : resourcesPath;

    pythonProcess = spawn(pythonPath, ['-m', 'clonepub.server'], {
        cwd: moduleParentPath,
        env: {
            ...process.env,
            PYTHONPATH: moduleParentPath,
            CLONEPUB_PORT: String(PYTHON_PORT)
        },
        stdio: ['pipe', 'pipe', 'pipe']
    });

    // Log Python output
    pythonProcess.stdout?.on('data', (data) => {
        log.info(`[Python] ${data.toString().trim()}`);
    });

    pythonProcess.stderr?.on('data', (data) => {
        log.warn(`[Python stderr] ${data.toString().trim()}`);
    });

    pythonProcess.on('error', (error) => {
        log.error('Python process error:', error);
    });

    pythonProcess.on('exit', (code, signal) => {
        log.info(`Python process exited with code ${code}, signal ${signal}`);
        pythonProcess = null;
    });

    // Wait for server to be ready
    const serverReady = await waitForServer();
    if (!serverReady) {
        log.error('Python server failed to start');
        stopPythonBackend();
        return false;
    }

    return true;
}

function stopPythonBackend(): void {
    if (pythonProcess) {
        log.info('Stopping Python backend...');
        pythonProcess.kill('SIGTERM');
        pythonProcess = null;
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// IPC Handlers for Native Dialogs
// ─────────────────────────────────────────────────────────────────────────────

function setupIPC(): void {
    // Open EPUB file dialog
    ipcMain.handle('dialog:openEpub', async () => {
        if (!mainWindow) return null;

        const result = await dialog.showOpenDialog(mainWindow, {
            title: 'Open EPUB File',
            filters: [
                { name: 'EPUB Files', extensions: ['epub'] }
            ],
            properties: ['openFile']
        });

        return result.canceled ? null : result.filePaths[0];
    });

    // Open audio file dialog (for voice reference)
    ipcMain.handle('dialog:openAudio', async () => {
        if (!mainWindow) return null;

        const result = await dialog.showOpenDialog(mainWindow, {
            title: 'Select Reference Audio',
            filters: [
                { name: 'Audio Files', extensions: ['mp3', 'wav', 'm4a', 'flac', 'ogg'] }
            ],
            properties: ['openFile']
        });

        return result.canceled ? null : result.filePaths[0];
    });

    // Open folder dialog (for output directory)
    ipcMain.handle('dialog:openFolder', async () => {
        if (!mainWindow) return null;

        const result = await dialog.showOpenDialog(mainWindow, {
            title: 'Select Output Folder',
            properties: ['openDirectory', 'createDirectory']
        });

        return result.canceled ? null : result.filePaths[0];
    });

    // Get system paths
    ipcMain.handle('path:downloads', () => {
        return app.getPath('downloads');
    });

    // Open external URL
    ipcMain.handle('shell:openExternal', async (_, url: string) => {
        await shell.openExternal(url);
    });

    // Open folder in Finder
    ipcMain.handle('shell:showItemInFolder', (_, path: string) => {
        shell.showItemInFolder(path);
    });

    // Logging from renderer
    ipcMain.handle('log', (_, msg: any) => {
        log.info(`[Renderer] ${msg}`);
    });
}

// ─────────────────────────────────────────────────────────────────────────────
// Window Management
// ─────────────────────────────────────────────────────────────────────────────

function createMainWindow(): void {
    mainWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        minWidth: 960,
        minHeight: 700,
        titleBarStyle: 'hiddenInset',
        backgroundColor: '#0f1419',
        show: false, // Don't show until ready
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js')
        }
    });

    // Load the UI
    const uiPath = isDev
        ? path.join(__dirname, '..', '..', 'clonepub', 'ui', 'index.html')
        : path.join(resourcesPath, 'clonepub', 'ui', 'index.html');

    log.info(`Loading UI from ${uiPath}`);
    mainWindow.loadFile(uiPath);

    // Show window when ready
    mainWindow.once('ready-to-show', () => {
        mainWindow?.show();
        // Close setup window after main window is ready
        if (setupWindow) {
            setupWindow.close();
            setupWindow = null;
        }
    });

    // Open DevTools in development
    if (isDev) {
        mainWindow.webContents.openDevTools();
    }

    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}

// ─────────────────────────────────────────────────────────────────────────────
// App Lifecycle
// ─────────────────────────────────────────────────────────────────────────────

// Keep track of backend status
let isBackendReady = false;

app.on('ready', async () => {
    log.info('App ready event fired');
    log.info(`Preload path: ${path.join(__dirname, 'preload.js')}`);

    // Setup IPC handlers
    setupIPC();

    // Check/setup Python environment
    if (!isEnvironmentReady()) {
        log.info('Python environment not found, running setup...');
        const setupSuccess = await setupPythonEnvironment();
        if (!setupSuccess) {
            app.quit();
            return;
        }
    }

    // Start Python backend
    const backendStarted = await startPythonBackend();
    if (!backendStarted) {
        dialog.showErrorBox(
            'Server Error',
            'Failed to start the Python backend server.\n\nPlease check the logs for more information.'
        );
        app.quit();
        return;
    }

    isBackendReady = true;

    // Create main window
    createMainWindow();
});

app.on('window-all-closed', () => {
    // Only quit if backend is ready (meaning we are not in setup/startup phase)
    // Or if mainWindow was created and then closed.
    // If setupWindow closed (but not mainWindow), we might be transitioning.
    // But our logic now keeps setupWindow open until mainWindow is ready-to-show.
    // So this adjustment is robust.
    log.info('All windows closed, quitting...');
    app.quit();
});

app.on('before-quit', () => {
    log.info('App quitting, cleaning up...');
    stopPythonBackend();
});

// macOS: Re-create window when clicking dock icon
app.on('activate', () => {
    if (mainWindow === null && isBackendReady) {
        createMainWindow();
    }
});

// Handle uncaught exceptions
(process as any).on('uncaughtException', (error: any) => {
    log.error('Uncaught exception:', error);
});

(process as any).on('unhandledRejection', (reason: any) => {
    log.error('Unhandled rejection:', reason);
});
