export const API_BASE = './php_server';

/**
 * Utility to fetch and parse JSON, handling "dirty" server responses
 * (e.g. PHP warnings prepended to JSON).
 */
/**
 * Utility to fetch and parse JSON, handling "dirty" server responses
 * (e.g. PHP warnings prepended to JSON or appended after).
 * Uses brace counting for robust extraction.
 */
export const fetchJson = async (url: string, options: RequestInit = {}) => {
    const response = await fetch(url, options);
    const text = await response.text();

    try {
        const extractJSON = (str: string) => {
            const firstOpen = str.indexOf('{');
            const firstArray = str.indexOf('[');

            let startIndex = -1;
            let isArray = false;

            if (firstOpen !== -1 && (firstArray === -1 || firstOpen < firstArray)) {
                startIndex = firstOpen;
            } else if (firstArray !== -1) {
                startIndex = firstArray;
                isArray = true;
            }

            if (startIndex === -1) return str;

            let openCount = 0;
            const openChar = isArray ? '[' : '{';
            const closeChar = isArray ? ']' : '}';

            for (let i = startIndex; i < str.length; i++) {
                if (str[i] === openChar) {
                    openCount++;
                } else if (str[i] === closeChar) {
                    openCount--;
                    if (openCount === 0) {
                        return str.substring(startIndex, i + 1);
                    }
                }
            }
            // Fallback if not balanced
            return str.substring(startIndex);
        };

        const cleanJson = extractJSON(text);
        return JSON.parse(cleanJson);
    } catch (e) {
        console.error("fetchJson parsing failed. Raw response:", text);
        throw new Error(`Server returned invalid JSON: ${text.substring(0, 100)}...`);
    }
};

const getIpcRenderer = () => {
    // Safer check for Electron IPC
    if (typeof window !== 'undefined' && window.require) {
        try {
            const electron = window.require('electron');
            return electron.ipcRenderer;
        } catch (e) {
            return null;
        }
    }
    return null;
};

const ipcRenderer = getIpcRenderer();
const isElectron = !!ipcRenderer;

export const api = {
    auth: {
        login: async (credentials: any) => {
            if (isElectron) {
                return ipcRenderer.invoke('auth:login', credentials);
            } else {
                return fetchJson(`${API_BASE}/auth.php?action=login`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(credentials)
                });
            }
        },
        register: async (credentials: any) => {
            if (isElectron) {
                return ipcRenderer.invoke('auth:register', credentials);
            } else {
                return fetchJson(`${API_BASE}/auth.php?action=register`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(credentials)
                });
            }
        },
        forgotPassword: async (username: string) => {
            // Both branches were identical in logic effectively
            return fetchJson(`${API_BASE}/auth.php?action=forgot_password`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username })
            });
        },
        verifyPayment: async (data: any) => {
            // Even in electron branch it was using fetch
            return fetchJson(`${API_BASE}/payment.php`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
        }
    },
    users: {
        getAll: async () => {
            if (isElectron) {
                return ipcRenderer.invoke('users:get-all');
            } else {
                return fetchJson(`${API_BASE}/users.php`);
            }
        },
        create: async (data: any) => {
            if (isElectron) {
                return ipcRenderer.invoke('users:create', data);
            } else {
                return fetchJson(`${API_BASE}/users.php?action=create`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
            }
        },
        updateRole: async (id: number, role: string) => {
            if (isElectron) {
                return ipcRenderer.invoke('users:update-role', { id, role });
            } else {
                return fetchJson(`${API_BASE}/users.php?action=update_role`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id, role })
                });
            }
        },
        delete: async (id: number) => {
            if (isElectron) {
                return ipcRenderer.invoke('users:delete', id);
            } else {
                return fetchJson(`${API_BASE}/users.php?action=delete`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id })
                });
            }
        },
        updateDate: async (id: number, date: string) => {
            if (isElectron) {
                return ipcRenderer.invoke('users:update-date', { id, date });
            } else {
                return fetchJson(`${API_BASE}/users.php?action=update_date`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id, date })
                });
            }
        },
        updateExpiry: async (id: number, expiry: string) => {
            if (isElectron) {
                return ipcRenderer.invoke('users:update-expiry', { id, expiry });
            } else {
                return fetchJson(`${API_BASE}/users.php?action=update_expiry`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id, expiry })
                });
            }
        }
    },
    stats: {
        getGlobal: async () => {
            if (isElectron) {
                return ipcRenderer.invoke('stats:get-global');
            } else {
                return fetchJson(`${API_BASE}/stats.php`);
            }
        },
        track: async (userId: number) => {
            if (isElectron) {
                return ipcRenderer.invoke('stats:track-download', userId);
            } else {
                return fetchJson(`${API_BASE}/stats.php?action=track`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id: userId })
                });
            }
        }
    },
    svg: {
        optimize: async (file: File) => {
            const formData = new FormData();
            formData.append('file', file);

            const data = await fetchJson(`${API_BASE}/optimize_svg.php`, {
                method: 'POST',
                body: formData
            });

            if (!data) {
                throw new Error("Optimization Failed: No data returned");
            }
            if (!data.success) {
                throw new Error(data.error || "Optimization Failed");
            }

            return data.svg;
        }
    },
    settings: {
        getAll: async () => {
            try {
                return await fetchJson(`${API_BASE}/settings.php`);
            } catch {
                return { success: false, error: 'Failed to load settings' };
            }
        },
        getPublic: async () => {
            try {
                return await fetchJson(`${API_BASE}/settings.php?mode=public`);
            } catch {
                return { success: false, error: 'Failed to load public settings' };
            }
        },
        save: async (settings: any) => {
            return fetchJson(`${API_BASE}/settings.php`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });
        },
        testTelegram: async (token: string, chatId: string) => {
            return fetchJson(`${API_BASE}/settings.php`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'test_telegram', token, chat_id: chatId }),
            });
        },
        testDonation: async (settings?: any) => {
            return fetchJson(`${API_BASE}/settings.php`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'test_donation', settings })
            });
        }
    },
    templates: {
        list: async (asAdmin: boolean = false) => {
            const t = new Date().getTime();
            return fetchJson(`${API_BASE}/templates.php?action=list${asAdmin ? '&mode=admin' : ''}&t=${t}`);
        },
        rename: async (oldName: string, newName: string) => {
            return fetchJson(`${API_BASE}/templates.php`, {
                method: 'POST',
                body: JSON.stringify({ action: 'rename', old_name: oldName, new_name: newName })
            });
        },
        toggleVisibility: async (filename: string) => {
            return fetchJson(`${API_BASE}/templates.php`, {
                method: 'POST',
                body: JSON.stringify({ action: 'toggle_visibility', filename })
            });
        },
        upload: async (file: File, name?: string) => {
            const formData = new FormData();
            formData.append('action', 'upload');
            formData.append('file', file);
            if (name) formData.append('name', name);

            return fetchJson(`${API_BASE}/templates.php`, {
                method: 'POST',
                body: formData
            });
        },
        delete: async (filename: string) => {
            return fetchJson(`${API_BASE}/templates.php`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'delete', filename })
            });
        }
    },
    fonts: {
        list: async (asAdmin: boolean = false) => {
            const t = new Date().getTime();
            return fetchJson(`${API_BASE}/fonts.php?action=list${asAdmin ? '&mode=admin' : ''}&t=${t}`);
        },
        rename: async (oldName: string, newName: string) => {
            return fetchJson(`${API_BASE}/fonts.php`, {
                method: 'POST',
                body: JSON.stringify({ action: 'rename', old_name: oldName, new_name: newName })
            });
        },
        toggleVisibility: async (filename: string) => {
            return fetchJson(`${API_BASE}/fonts.php`, {
                method: 'POST',
                body: JSON.stringify({ action: 'toggle_visibility', filename })
            });
        },
        upload: async (file: File, name?: string) => {
            const formData = new FormData();
            formData.append('action', 'upload');
            formData.append('file', file);
            if (name) formData.append('name', name);

            return fetchJson(`${API_BASE}/fonts.php`, {
                method: 'POST',
                body: formData
            });
        },
        delete: async (filename: string) => {
            return fetchJson(`${API_BASE}/fonts.php`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'delete', filename })
            });
        }
    },
    gadgets: {
        list: async () => {
            return fetchJson(`${API_BASE}/gadgets.php?action=list`);
        },
        save: async (formData: FormData) => {
            try {
                return await fetchJson(`${API_BASE}/gadgets.php?action=save`, {
                    method: 'POST',
                    body: formData
                });
            } catch (e: any) {
                console.error("Gadget Upload Response Error:", e);
                // Strip HTML tags for clean error in case fetchJson didn't catch it efficiently (though fetchJson handles it now)
                throw e;
            }
        },
        toggleVisibility: async (id: string) => {
            return fetchJson(`${API_BASE}/gadgets.php?action=toggleVisibility`, {
                method: 'POST',
                body: JSON.stringify({ action: 'toggleVisibility', id })
            });
        },
        delete: async (id: string) => {
            return fetchJson(`${API_BASE}/gadgets.php?action=delete`, {
                method: 'POST',
                body: JSON.stringify({ action: 'delete', id })
            });
        }
    }
};
