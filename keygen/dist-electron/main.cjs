"use strict";
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const electron_1 = require("electron");
const path_1 = __importDefault(require("path"));
const dotenv_1 = __importDefault(require("dotenv"));
dotenv_1.default.config();
const API_BASE = 'https://www.virtuprinto.com/test2/php_server';
// Handle creating/removing shortcuts on Windows when installing/uninstalling.
// (Removed electron-squirrel-startup check to prevent dev dependency issues)
const createWindow = () => {
    // Create the browser window.
    const mainWindow = new electron_1.BrowserWindow({
        width: 1200,
        height: 800,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false,
            webSecurity: false
        },
    });
    if (electron_1.app.isPackaged) {
        mainWindow.loadFile(path_1.default.join(__dirname, '../dist/index.html'));
    }
    else {
        mainWindow.loadURL('http://localhost:3000');
        mainWindow.webContents.openDevTools();
    }
};
electron_1.app.on('ready', () => {
    createWindow();
    // No local DB init needed anymore
});
electron_1.app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        electron_1.app.quit();
    }
});
electron_1.app.on('activate', () => {
    if (electron_1.BrowserWindow.getAllWindows().length === 0) {
        createWindow();
    }
});
// --- IPC Handlers (Using PHP API) ---
// Register User
electron_1.ipcMain.handle('auth:register', (event_1, _a) => __awaiter(void 0, [event_1, _a], void 0, function* (event, { username, password, role }) {
    try {
        const response = yield fetch(`${API_BASE}/auth.php?action=register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password, role: role || 'user' })
        });
        const text = yield response.text();
        try {
            const data = JSON.parse(text);
            if (data.success) {
                return { success: true };
            }
            else {
                return { success: false, error: data.error || 'Registration failed' };
            }
        }
        catch (e) {
            console.error('SERVER RESPONSE (Not JSON):', text.substring(0, 500));
            return { success: false, error: 'Server returned invalid JSON. Check console.' };
        }
    }
    catch (error) {
        console.error('Registration error:', error);
        return { success: false, error: 'Network error: ' + error.message };
    }
}));
// Login User
electron_1.ipcMain.handle('auth:login', (event_1, _a) => __awaiter(void 0, [event_1, _a], void 0, function* (event, { username, password }) {
    try {
        const response = yield fetch(`${API_BASE}/auth.php?action=login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        const text = yield response.text();
        try {
            const data = JSON.parse(text);
            if (data.success) {
                return { success: true, user: data.user };
            }
            else {
                return { success: false, error: data.error || 'Login failed' };
            }
        }
        catch (e) {
            console.error('SERVER RESPONSE (Not JSON):', text.substring(0, 500));
            return { success: false, error: 'Server returned invalid JSON. Check console.' };
        }
    }
    catch (error) {
        console.error('Login error:', error);
        return { success: false, error: 'Network error: ' + error.message };
    }
}));
// Get All Users
electron_1.ipcMain.handle('users:get-all', () => __awaiter(void 0, void 0, void 0, function* () {
    try {
        const response = yield fetch(`${API_BASE}/users.php`);
        const text = yield response.text();
        try {
            const data = JSON.parse(text);
            if (data.success) {
                return { success: true, users: data.users };
            }
            else {
                return { success: false, error: data.error || 'Failed to fetch users' };
            }
        }
        catch (e) {
            console.error('SERVER RESPONSE (Not JSON):', text.substring(0, 500));
            return { success: false, error: 'Server returned invalid JSON. Check console.' };
        }
    }
    catch (error) {
        console.error('Fetch users error:', error);
        return { success: false, error: error.message };
    }
}));
// Delete User
electron_1.ipcMain.handle('users:delete', (event, userId) => __awaiter(void 0, void 0, void 0, function* () {
    try {
        const response = yield fetch(`${API_BASE}/users.php?action=delete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: userId })
        });
        const text = yield response.text();
        try {
            const data = JSON.parse(text);
            if (data.success) {
                return { success: true };
            }
            else {
                return { success: false, error: data.error || 'Failed to delete user' };
            }
        }
        catch (e) {
            console.error('SERVER RESPONSE (Not JSON):', text.substring(0, 500));
            return { success: false, error: 'Server returned invalid JSON. Check console.' };
        }
    }
    catch (error) {
        console.error('Delete user error:', error);
        return { success: false, error: error.message };
    }
}));
// Create User
electron_1.ipcMain.handle('users:create', (event, userData) => __awaiter(void 0, void 0, void 0, function* () {
    try {
        const response = yield fetch(`${API_BASE}/users.php?action=create`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(userData)
        });
        const text = yield response.text();
        try {
            const data = JSON.parse(text);
            if (data.success) {
                return { success: true };
            }
            else {
                return { success: false, error: data.error || 'Failed to create user' };
            }
        }
        catch (e) {
            console.error('SERVER RESPONSE (Not JSON):', text.substring(0, 500));
            return { success: false, error: 'Server returned invalid JSON. Check console.' };
        }
    }
    catch (error) {
        console.error('Create user error:', error);
        return { success: false, error: error.message };
    }
}));
// Update User Role
electron_1.ipcMain.handle('users:update-role', (event_1, _a) => __awaiter(void 0, [event_1, _a], void 0, function* (event, { id, role }) {
    try {
        const response = yield fetch(`${API_BASE}/users.php?action=update_role`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id, role })
        });
        const text = yield response.text();
        try {
            const data = JSON.parse(text);
            if (data.success) {
                return { success: true };
            }
            else {
                return { success: false, error: data.error || 'Failed to update role' };
            }
        }
        catch (e) {
            console.error('SERVER RESPONSE (Not JSON):', text.substring(0, 500));
            return { success: false, error: 'Server returned invalid JSON. Check console.' };
        }
    }
    catch (error) {
        console.error('Update role error:', error);
        return { success: false, error: error.message };
    }
}));
// Update User Registration Date
electron_1.ipcMain.handle('users:update-date', (event_1, _a) => __awaiter(void 0, [event_1, _a], void 0, function* (event, { id, date }) {
    try {
        const response = yield fetch(`${API_BASE}/users.php?action=update_date`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id, date })
        });
        const text = yield response.text();
        try {
            const data = JSON.parse(text);
            return data;
        }
        catch (e) {
            return { success: false, error: 'Invalid server response' };
        }
    }
    catch (error) {
        return { success: false, error: error.message };
    }
}));
// Get Global Stats
electron_1.ipcMain.handle('stats:get-global', () => __awaiter(void 0, void 0, void 0, function* () {
    try {
        const response = yield fetch(`${API_BASE}/stats.php`);
        const text = yield response.text();
        try {
            const data = JSON.parse(text);
            return data;
        }
        catch (e) {
            return { success: false, error: 'Invalid server response' };
        }
    }
    catch (error) {
        return { success: false, error: error.message };
    }
}));
// Track Download
electron_1.ipcMain.handle('stats:track-download', (event, userId) => __awaiter(void 0, void 0, void 0, function* () {
    try {
        const response = yield fetch(`${API_BASE}/stats.php?action=track`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId })
        });
        const text = yield response.text();
        try {
            const data = JSON.parse(text);
            return data;
        }
        catch (e) {
            return { success: false, error: 'Invalid server response' };
        }
    }
    catch (error) {
        return { success: false, error: error.message };
    }
}));
// Update User Expiry Date
electron_1.ipcMain.handle('users:update-expiry', (event_1, _a) => __awaiter(void 0, [event_1, _a], void 0, function* (event, { id, expiry }) {
    try {
        const response = yield fetch(`${API_BASE}/users.php?action=update_expiry`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id, expiry })
        });
        const text = yield response.text();
        try {
            const data = JSON.parse(text);
            return data;
        }
        catch (e) {
            return { success: false, error: 'Invalid server response' };
        }
    }
    catch (error) {
        return { success: false, error: error.message };
    }
}));
