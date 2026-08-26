import { app, BrowserWindow, ipcMain } from 'electron';
import path from 'path';
import dotenv from 'dotenv';

dotenv.config();

const API_BASE = 'https://www.virtuprinto.com/test2/php_server';

/**
 * Utility to fetch and parse JSON, handling "dirty" server responses
 * (e.g. PHP warnings prepended to JSON).
 */
const fetchJson = async (url: string, options: RequestInit = {}) => {
    const response = await fetch(url, options);
    const text = await response.text();

    try {
        let jsonText = text;
        const firstBrace = text.indexOf('{');
        const firstBracket = text.indexOf('[');

        let start = -1;
        let end = -1;

        // Determine if object or array starts first
        if (firstBrace !== -1 && (firstBracket === -1 || firstBrace < firstBracket)) {
            // Object
            start = firstBrace;
            end = text.lastIndexOf('}');
        } else if (firstBracket !== -1 && (firstBrace === -1 || firstBracket < firstBrace)) {
            // Array
            start = firstBracket;
            end = text.lastIndexOf(']');
        }

        if (start !== -1 && end !== -1 && end > start) {
            jsonText = text.substring(start, end + 1);
        }

        return JSON.parse(jsonText);
    } catch (e) {
        console.error("fetchJson parsing failed. Raw response:", text);
        throw new Error(`Server returned invalid JSON: ${text.substring(0, 100)}...`);
    }
};

// Handle creating/removing shortcuts on Windows when installing/uninstalling.
// (Removed electron-squirrel-startup check to prevent dev dependency issues)

const createWindow = () => {
    // Create the browser window.
    const mainWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false,
            webSecurity: false
        },
    });

    if (app.isPackaged) {
        mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
    } else {
        mainWindow.loadURL('http://localhost:3000');
        mainWindow.webContents.openDevTools();
    }
};

app.on('ready', () => {
    createWindow();
    // No local DB init needed anymore
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
    }
});

// --- IPC Handlers (Using PHP API) ---

// Register User
ipcMain.handle('auth:register', async (event, { username, password, role }) => {
    try {
        const data = await fetchJson(`${API_BASE}/auth.php?action=register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password, role: role || 'user' })
        });

        if (data.success) {
            return { success: true };
        } else {
            return { success: false, error: data.error || 'Registration failed' };
        }
    } catch (error: any) {
        console.error('Registration error:', error);
        return { success: false, error: 'Network error: ' + error.message };
    }
});

// Login User
ipcMain.handle('auth:login', async (event, { username, password }) => {
    try {
        const data = await fetchJson(`${API_BASE}/auth.php?action=login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        if (data.success) {
            return { success: true, user: data.user };
        } else {
            return { success: false, error: data.error || 'Login failed' };
        }
    } catch (error: any) {
        console.error('Login error:', error);
        return { success: false, error: 'Network error: ' + error.message };
    }
});

// Get All Users
ipcMain.handle('users:get-all', async () => {
    try {
        const data = await fetchJson(`${API_BASE}/users.php`);

        if (data.success) {
            return { success: true, users: data.users };
        } else {
            return { success: false, error: data.error || 'Failed to fetch users' };
        }
    } catch (error: any) {
        console.error('Fetch users error:', error);
        return { success: false, error: error.message };
    }
});

// Delete User
ipcMain.handle('users:delete', async (event, userId) => {
    try {
        const data = await fetchJson(`${API_BASE}/users.php?action=delete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: userId })
        });

        if (data.success) {
            return { success: true };
        } else {
            return { success: false, error: data.error || 'Failed to delete user' };
        }
    } catch (error: any) {
        console.error('Delete user error:', error);
        return { success: false, error: error.message };
    }
});

// Create User
ipcMain.handle('users:create', async (event, userData) => {
    try {
        const data = await fetchJson(`${API_BASE}/users.php?action=create`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(userData)
        });

        if (data.success) {
            return { success: true };
        } else {
            return { success: false, error: data.error || 'Failed to create user' };
        }
    } catch (error: any) {
        console.error('Create user error:', error);
        return { success: false, error: error.message };
    }
});

// Update User Role
ipcMain.handle('users:update-role', async (event, { id, role }) => {
    try {
        const data = await fetchJson(`${API_BASE}/users.php?action=update_role`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id, role })
        });

        if (data.success) {
            return { success: true };
        } else {
            return { success: false, error: data.error || 'Failed to update role' };
        }
    } catch (error: any) {
        console.error('Update role error:', error);
        return { success: false, error: error.message };
    }
});

// Update User Registration Date
ipcMain.handle('users:update-date', async (event, { id, date }) => {
    try {
        const data = await fetchJson(`${API_BASE}/users.php?action=update_date`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id, date })
        });
        return data;
    } catch (error: any) {
        return { success: false, error: error.message };
    }
});

// Get Global Stats
ipcMain.handle('stats:get-global', async () => {
    try {
        const data = await fetchJson(`${API_BASE}/stats.php`);
        return data;
    } catch (error: any) {
        return { success: false, error: error.message };
    }
});

// Track Download
ipcMain.handle('stats:track-download', async (event, userId) => {
    try {
        const data = await fetchJson(`${API_BASE}/stats.php?action=track`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId })
        });
        return data;
    } catch (error: any) {
        return { success: false, error: error.message };
    }
});

// Update User Expiry Date
ipcMain.handle('users:update-expiry', async (event, { id, expiry }) => {
    try {
        const data = await fetchJson(`${API_BASE}/users.php?action=update_expiry`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id, expiry })
        });
        return data;
    } catch (error: any) {
        return { success: false, error: error.message };
    }
});
