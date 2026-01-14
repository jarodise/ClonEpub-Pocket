/**
 * ClonEpub Electron Preload Script
 * 
 * Exposes safe APIs to the renderer process via contextBridge.
 */

import { contextBridge, ipcRenderer } from 'electron';

// Expose IPC methods to renderer in a safe way
contextBridge.exposeInMainWorld('electronAPI', {
    // File dialogs
    openEpubDialog: () => ipcRenderer.invoke('dialog:openEpub'),
    openAudioDialog: () => ipcRenderer.invoke('dialog:openAudio'),
    openFolderDialog: () => ipcRenderer.invoke('dialog:openFolder'),

    // System paths
    getDownloadsPath: () => ipcRenderer.invoke('path:downloads'),

    // Shell operations
    openExternal: (url: string) => ipcRenderer.invoke('shell:openExternal', url),
    showItemInFolder: (path: string) => ipcRenderer.invoke('shell:showItemInFolder', path),

    // Logging
    log: (msg: any) => ipcRenderer.invoke('log', msg),
});

// Expose the API base URL for the Python server
contextBridge.exposeInMainWorld('API_BASE', 'http://127.0.0.1:8765');

// Type declarations for renderer process
declare global {
    interface Window {
        electronAPI: {
            openEpubDialog: () => Promise<string | null>;
            openAudioDialog: () => Promise<string | null>;
            openFolderDialog: () => Promise<string | null>;
            getDownloadsPath: () => Promise<string>;
            openExternal: (url: string) => Promise<void>;
            showItemInFolder: (path: string) => void;
        };
        API_BASE: string;
    }
}
