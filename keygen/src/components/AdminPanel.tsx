import React, { useEffect, useState } from 'react';
import { Users, Trash2, LogOut, Calendar, Eye, EyeOff, Send, File, Upload, Pencil, Type, ExternalLink, Smartphone, Settings } from 'lucide-react';
import { api } from '../api';

interface AdminPanelProps {
    onLogout: () => void;
    onBack?: () => void;
}

// ... (skipping unchanged code for brevity in tool call, but context needs to be right)
// I will just replace the interface and the header section in two chunks if needed, or one big chunk if they are close.
// They are lines 5-7 (Interface) and 219-231 (Header). They are far apart.
// I should use multi_replace.

interface UserData {
    id: number;
    username: string;
    role: string;
    created_at: string;
    download_count: number;
    expiry_date: string;
}

const AdminPanel: React.FC<AdminPanelProps> = ({ onLogout, onBack }) => {
    const [users, setUsers] = useState<UserData[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [editingDateId, setEditingDateId] = useState<number | null>(null);
    const [editingExpiryId, setEditingExpiryId] = useState<number | null>(null);
    const [tempDate, setTempDate] = useState('');
    const [tempExpiry, setTempExpiry] = useState('');

    const [newUsername, setNewUsername] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [newRole, setNewRole] = useState('standard');
    const [createError, setCreateError] = useState<string | null>(null);

    // Gadget Management State
    const [gadgets, setGadgets] = useState<any[]>([]);
    const [gadgetForm, setGadgetForm] = useState({ name: '', description: '', widthMm: '', heightMm: '', baseExtrusionMm: '', engravingDepthMm: '', defaultColor: '#ffffff' });
    const [gadgetFile, setGadgetFile] = useState<File | null>(null);
    const [isGadgetUploading, setIsGadgetUploading] = useState(false);
    const [editingGadgetId, setEditingGadgetId] = useState<string | null>(null);

    const fetchGadgets = async () => {
        try {
            const res = await api.gadgets.list();
            if (res.success) setGadgets(res.gadgets || []);
        } catch (e) { console.error(e); }
    };
    const handleGadgetFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            const file = e.target.files[0];
            setGadgetFile(file);

            // Auto-detect dimensions
            const reader = new FileReader();
            reader.onload = (ev) => {
                const text = ev.target?.result as string;
                if (!text) return;

                try {
                    const parser = new DOMParser();
                    const doc = parser.parseFromString(text, 'image/svg+xml');
                    const svg = doc.querySelector('svg');

                    if (svg) {
                        let w = svg.getAttribute('width');
                        let h = svg.getAttribute('height');
                        const viewBox = svg.getAttribute('viewBox');

                        // Helper to convert to mm
                        const toMm = (val: string | null) => {
                            if (!val) return '';
                            const num = parseFloat(val);
                            if (isNaN(num)) return '';
                            if (val.includes('mm')) return num.toString();
                            if (val.includes('cm')) return (num * 10).toString();
                            if (val.includes('in')) return (num * 25.4).toString();
                            if (val.includes('pt')) return (num * 0.352778).toString();
                            // If unitless, check if viewBox exists to imply ratio, but can't guess physical scale easily.
                            // But usually users want px -> mm mapping 1:1 or specific dpi. 
                            // Let's just return the number if unitless, user can check.
                            return num.toString();
                        };

                        let wMm = toMm(w);
                        let hMm = toMm(h);

                        // If width/height missing, try viewBox
                        if ((!wMm || !hMm) && viewBox) {
                            const parts = viewBox.split(/\s+|,/).map(parseFloat);
                            if (parts.length === 4) {
                                if (!wMm) wMm = parts[2].toString(); // width
                                if (!hMm) hMm = parts[3].toString(); // height
                            }
                        }

                        setGadgetForm(prev => ({
                            ...prev,
                            widthMm: wMm || prev.widthMm,
                            heightMm: hMm || prev.heightMm,
                            name: file.name.replace('.svg', '').replace(/[-_]/g, ' ')
                        }));
                    }
                } catch (err) {
                    console.error("Error parsing SVG", err);
                }
            };
            reader.readAsText(file);
        }
    };

    const handleGadgetCreate = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsGadgetUploading(true);
        try {
            const formData = new FormData();
            formData.append('action', 'save');
            formData.append('name', gadgetForm.name);
            formData.append('description', gadgetForm.description);
            formData.append('widthMm', gadgetForm.widthMm);
            formData.append('heightMm', gadgetForm.heightMm);
            formData.append('baseExtrusionMm', gadgetForm.baseExtrusionMm);
            if (gadgetForm.engravingDepthMm) formData.append('engravingDepthMm', gadgetForm.engravingDepthMm);
            formData.append('defaultColor', gadgetForm.defaultColor);
            if (editingGadgetId) formData.append('id', editingGadgetId);
            if (gadgetFile) formData.append('file', gadgetFile);

            const res = await api.gadgets.save(formData);
            if (res.success) {
                alert(editingGadgetId ? 'Gadget updated successfully!' : 'Gadget created successfully!');
                setGadgetForm({ name: '', description: '', widthMm: '', heightMm: '', baseExtrusionMm: '', engravingDepthMm: '', defaultColor: '#ffffff' });
                setGadgetFile(null);
                setEditingGadgetId(null);
                fetchGadgets();
            } else {
                alert('Error: ' + res.error);
            }
        } catch (e: any) {
            alert('Error: ' + e.message);
        } finally {
            setIsGadgetUploading(false);
        }
    };

    const handleGadgetVisibility = async (id: string) => {
        try {
            const res = await api.gadgets.toggleVisibility(id);
            if (res.success) fetchGadgets();
            else alert(res.error);
        } catch (e: any) { alert(e.message); }
    };

    const handleGadgetDelete = async (id: string) => {
        if (!confirm('Delete this gadget template?')) return;
        try {
            const res = await api.gadgets.delete(id);
            if (res.success) fetchGadgets();
            else alert(res.error);
        } catch (e: any) { alert(e.message); }
    };

    useEffect(() => {
        fetchGadgets();
    }, []);

    const fetchUsers = async () => {
        try {
            setLoading(true);
            const response = await api.users.getAll();
            if (response.success) {
                setUsers(response.users);
            } else {
                setError(response.error);
            }
        } catch (err: any) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleCreate = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!newUsername || !newPassword) {
            setCreateError("Username and Password are required");
            return;
        }

        // Email validation
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(newUsername)) {
            setCreateError("Please enter a valid email address as username");
            return;
        }

        setCreateError(null);
        try {
            const response = await api.users.create({
                username: newUsername,
                password: newPassword,
                role: newRole
            });

            if (response.success) {
                setNewUsername('');
                setNewPassword('');
                setNewRole('standard');
                fetchUsers();
                alert('User created successfully!');
            } else {
                setCreateError(response.error);
            }
        } catch (err: any) {
            setCreateError(err.message);
        }
    };

    const handleDelete = async (userId: number) => {
        if (!confirm('Are you sure you want to delete this user?')) return;
        try {
            const response = await api.users.delete(userId);
            if (response.success) {
                fetchUsers(); // Refresh list
            } else {
                alert('Failed to delete user: ' + response.error);
            }
        } catch (err: any) {
            alert('Error: ' + err.message);
        }
    };

    const handleRoleUpdate = async (userId: number, newRole: string) => {
        try {
            const response = await api.users.updateRole(userId, newRole);
            if (response.success) {
                // Optimistically update UI or re-fetch
                setUsers(users.map(u => u.id === userId ? { ...u, role: newRole } : u));
                alert('Role updated!');
            } else {
                alert('Failed to update role: ' + response.error);
                fetchUsers(); // Revert on failure
            }
        } catch (err: any) {
            alert('Error: ' + err.message);
            fetchUsers();
        }
    };

    const handleDateUpdate = async (userId: number) => {
        try {
            const response = await api.users.updateDate(userId, tempDate);
            if (response.success) {
                setUsers(users.map(u => u.id === userId ? { ...u, created_at: tempDate } : u));
                setEditingDateId(null);
                alert('Registration date updated!');
            } else {
                alert('Failed to update date: ' + response.error);
            }
        } catch (err: any) {
            alert('Error: ' + err.message);
        }
    };

    const handleExpiryUpdate = async (userId: number) => {
        try {
            const response = await api.users.updateExpiry(userId, tempExpiry);
            if (response.success) {
                setUsers(users.map(u => u.id === userId ? { ...u, expiry_date: tempExpiry } : u));
                setEditingExpiryId(null);
                alert('Expiry date updated!');
            } else {
                alert('Failed to update expiry: ' + response.error);
            }
        } catch (err: any) {
            alert('Error: ' + err.message);
        }
    };

    const [activeTab, setActiveTab] = useState<'users' | 'email' | 'donations' | 'templates' | 'fonts' | 'gadgets' | 'settings'>('users');
    const [emailSettings, setEmailSettings] = useState<any>({});
    const [templates, setTemplates] = useState<string[]>([]);
    const [fonts, setFonts] = useState<string[]>([]);
    const [selectedTemplateName, setSelectedTemplateName] = useState('');
    const [selectedFontName, setSelectedFontName] = useState('');
    const [isUploading, setIsUploading] = useState(false);
    const [templateLoading, setTemplateLoading] = useState(false);
    const [settingsLoading, setSettingsLoading] = useState(false);
    const [settingsError, setSettingsError] = useState<string | null>(null);
    const [previewMode, setPreviewMode] = useState<{ welcome: boolean, reset: boolean }>({ welcome: false, reset: false });
    const [showSmtpPassword, setShowSmtpPassword] = useState(false);

    // Initial Load
    useEffect(() => {
        const loadSettings = async () => {
            setSettingsLoading(true);
            try {
                const res = await api.settings.getAll(); // Correct method
                if (res.success) setEmailSettings(res.settings || {});
                else setSettingsError(res.error);
            } catch (e: any) { setSettingsError(e.message); } finally { setSettingsLoading(false); }
        };

        if (activeTab === 'users') {
            fetchUsers();
        } else if (activeTab === 'email') {
            loadSettings();
        } else if (activeTab === 'templates') {
            fetchTemplates();
        } else if (activeTab === 'fonts') {
            fetchFonts();
        } else if (activeTab === 'gadgets') {
            fetchGadgets();
        }
    }, [activeTab]);

    const fetchFonts = async () => {
        try {
            const res = await api.fonts.list(true);
            if (res.success) setFonts(res.fonts);
        } catch (e) { console.error(e); }
    };

    const handleFontUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;
        setIsUploading(true);
        try {
            const res = await api.fonts.upload(file, selectedFontName || undefined);
            if (res.success) {
                const count = res.files ? res.files.length : 1;
                alert(`${count} Font(s) uploaded successfully!`);
                fetchFonts();
                setSelectedFontName('');
                e.target.value = '';
            } else {
                alert('Upload failed: ' + res.error);
            }
        } catch (e: any) {
            alert('Error: ' + e.message);
        } finally {
            setIsUploading(false);
        }
    };

    const handleFontDelete = async (filename: string) => {
        if (!confirm(`Delete font ${filename}?`)) return;
        try {
            const res = await api.fonts.delete(filename);
            if (res.success) fetchFonts();
            else alert(res.error);
        } catch (e: any) { alert(e.message); }
    };

    const fetchTemplates = async () => {
        setTemplateLoading(true);
        try {
            const res = await api.templates.list(true); // Fetch as ADMIN (shows hidden)
            if (res.success) setTemplates(res.templates);
        } catch (e) { console.error(e); } finally { setTemplateLoading(false); }
    };

    const handleTemplateUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files || e.target.files.length === 0) return;
        const file = e.target.files[0];
        try {
            const res = await api.templates.upload(file, selectedTemplateName);
            if (res.success) {
                alert('Template uploaded!');
                setSelectedTemplateName(""); // Reset name
                fetchTemplates();
            } else {
                alert('Upload failed: ' + res.error);
            }
        } catch (e: any) { alert('Error: ' + e.message); }
    };

    const handleTemplateDelete = async (filename: string) => {
        if (!confirm('Delete template ' + filename + '?')) return;
        try {
            const res = await api.templates.delete(filename);
            if (res.success) {
                fetchTemplates();
            } else {
                alert('Delete failed: ' + res.error);
            }
        } catch (e: any) { alert('Error: ' + e.message); }
    };

    const fetchSettings = async () => {
        setSettingsLoading(true);
        setSettingsError(null); // Clear previous errors
        try {
            const response = await api.settings.getAll();
            if (response.success && response.settings) {
                setEmailSettings(response.settings);
            } else {
                setSettingsError("Failed to load settings");
            }
        } catch (e: any) {
            setSettingsError(e.message);
        } finally {
            setSettingsLoading(false);
        }
    };

    const handleSettingsSave = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            const response = await api.settings.save(emailSettings);
            if (response.success) {
                alert('Email settings saved successfully!');
            } else {
                alert('Failed to save settings');
            }
        } catch (e: any) {
            alert('Error saving settings: ' + e.message);
        }
    };

    const handleTestTelegram = async () => {
        if (!emailSettings.telegram_bot_token || !emailSettings.telegram_chat_id) {
            alert('Please enter both Bot Token and Chat ID to test.');
            return;
        }
        try {
            const response = await api.settings.testTelegram(emailSettings.telegram_bot_token, emailSettings.telegram_chat_id);
            if (response.success) {
                alert('Test message sent successfully! Check your Telegram.');
            } else {
                alert('Test failed: ' + (response.error || 'Unknown error'));
            }
        } catch (e: any) {
            alert('Error testing Telegram: ' + e.message);
        }
    };

    const handleSettingChange = (key: string, value: string) => {
        setEmailSettings((prev: any) => ({ ...prev, [key]: value }));
    };

    const togglePreview = (type: 'welcome' | 'reset') => {
        setPreviewMode(prev => ({ ...prev, [type]: !prev[type] }));
    };

    return (
        <div className="min-h-screen bg-black text-white p-4 md:p-8 cyber-bg">
            <div className="max-w-7xl mx-auto relative z-10">
                <div className="flex flex-col md:flex-row justify-between items-center gap-4 mb-8">
                    <h1 className="text-2xl md:text-3xl font-black text-lime-400 tracking-tighter uppercase italic flex items-center gap-3">
                        <Users className="w-6 h-6 md:w-8 md:h-8" />
                        SYSTEM_ADMIN
                    </h1>
                    <div className="flex items-center gap-3 w-full md:w-auto">
                        {onBack && (
                            <button
                                onClick={onBack}
                                className="flex-1 md:flex-none flex items-center justify-center gap-2 bg-zinc-800 hover:bg-zinc-700 text-white px-6 py-2.5 rounded-xl transition-all border border-zinc-700 font-mono text-xs uppercase tracking-widest"
                            >
                                <LogOut className="w-4 h-4 rotate-180" /> {/* Reusing icon, maybe rotated or different */}
                                APP_VIEW
                            </button>
                        )}
                        <button
                            onClick={onLogout}
                            className="flex-1 md:flex-none flex items-center justify-center gap-2 bg-zinc-900/80 hover:bg-zinc-800 text-lime-400 px-6 py-2.5 rounded-xl transition-all border border-lime-500/20 font-mono text-xs uppercase tracking-widest"
                        >
                            <LogOut className="w-4 h-4" />
                            TERMINATE_SESSION
                        </button>
                    </div>
                </div>

                <div className="flex border-b border-zinc-800 mb-8">
                    <button
                        onClick={() => setActiveTab('users')}
                        className={`px-6 py-4 font-mono text-xs uppercase tracking-widest transition-all border-b-2 ${activeTab === 'users' ? 'text-lime-400 border-lime-400 bg-lime-400/5' : 'text-zinc-500 border-transparent hover:text-zinc-300'}`}
                    >
                        User_Management
                    </button>
                    <button
                        onClick={() => setActiveTab('email')}
                        className={`px-6 py-4 font-mono text-xs uppercase tracking-widest transition-all border-b-2 ${activeTab === 'email' ? 'text-lime-400 border-lime-400 bg-lime-400/5' : 'text-zinc-500 border-transparent hover:text-zinc-300'}`}
                    >
                        Email_Configuration
                    </button>
                    <button
                        onClick={() => setActiveTab('donations')}
                        className={`px-4 py-2 rounded-lg text-sm font-mono uppercase tracking-widest transition-colors ${activeTab === 'donations' ? 'bg-lime-400 text-black font-bold' : 'text-zinc-400 hover:text-white'}`}
                    >
                        Subscriptions
                    </button>
                    <button
                        onClick={() => setActiveTab('templates')}
                        className={`w-full text-left px-4 py-3 rounded-lg flex items-center gap-3 transition-colors ${activeTab === 'templates' ? 'bg-lime-500/10 text-lime-400 border border-lime-500/20' : 'text-zinc-500 hover:bg-zinc-900 hover:text-zinc-300'
                            }`}
                    >
                        <File className="w-5 h-5" />
                        <span className="font-medium">Templates</span>
                    </button>

                    <button
                        onClick={() => setActiveTab('fonts')}
                        className={`w-full text-left px-4 py-3 rounded-lg flex items-center gap-3 transition-colors ${activeTab === 'fonts' ? 'bg-lime-500/10 text-lime-400 border border-lime-500/20' : 'text-zinc-500 hover:bg-zinc-900 hover:text-zinc-300'
                            }`}
                    >
                        <Type className="w-5 h-5" />
                        <span className="font-medium">Fonts</span>
                    </button>

                    <button
                        onClick={() => setActiveTab('gadgets')}
                        className={`w-full text-left px-4 py-3 rounded-lg flex items-center gap-3 transition-colors ${activeTab === 'gadgets' ? 'bg-lime-500/10 text-lime-400 border border-lime-500/20' : 'text-zinc-500 hover:bg-zinc-900 hover:text-zinc-300'
                            }`}
                    >
                        <Smartphone className="w-5 h-5" />
                        <span className="font-medium">Gadgets</span>
                    </button>


                </div>

                {activeTab === 'users' && (
                    <>
                        {/* Create User Form */}
                        <div className="bg-zinc-900/40 p-6 rounded-[2rem] border border-zinc-800 mb-8 backdrop-blur-xl shadow-2xl">
                            <h3 className="text-sm font-mono uppercase tracking-[0.3em] text-zinc-500 mb-6 flex items-center gap-2">
                                <span className="w-1.5 h-1.5 rounded-full bg-lime-400 animate-pulse"></span>
                                Register_New_Agent
                            </h3>

                            {createError && (
                                <div className="mb-6 p-3 rounded-xl text-xs font-mono bg-red-500/10 text-red-200 border border-red-500/30 uppercase">
                                    ERROR: {createError}
                                </div>
                            )}

                            <form onSubmit={handleCreate} className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
                                <div className="md:col-span-1">
                                    <label className="block text-[10px] font-mono uppercase tracking-widest text-zinc-600 mb-2 ml-1">Email_Identity</label>
                                    <input
                                        type="email"
                                        value={newUsername}
                                        onChange={(e) => setNewUsername(e.target.value)}
                                        className="w-full bg-black/50 border border-zinc-800 rounded-xl px-4 py-3 focus:outline-none focus:border-lime-500/50 text-sm font-mono placeholder-zinc-800 transition-all text-white"
                                        placeholder="USER@EMAIL.COM"
                                    />
                                </div>
                                <div className="md:col-span-1">
                                    <label className="block text-[10px] font-mono uppercase tracking-widest text-zinc-600 mb-2 ml-1">Access_String</label>
                                    <input
                                        type="text"
                                        value={newPassword}
                                        onChange={(e) => setNewPassword(e.target.value)}
                                        className="w-full bg-black/50 border border-zinc-800 rounded-xl px-4 py-3 focus:outline-none focus:border-lime-500/50 text-sm font-mono placeholder-zinc-800 transition-all text-white"
                                        placeholder="PK_••••••••"
                                    />
                                </div>
                                <div className="md:col-span-1">
                                    <label className="block text-[10px] font-mono uppercase tracking-widest text-zinc-600 mb-2 ml-1">Clearence_Level</label>
                                    <div className="relative">
                                        <select
                                            value={newRole}
                                            onChange={(e) => setNewRole(e.target.value)}
                                            className="w-full bg-black/50 border border-zinc-800 rounded-xl px-4 py-3 focus:outline-none focus:border-lime-500/50 text-sm font-mono text-white appearance-none cursor-pointer"
                                        >
                                            <option value="user">DEMO</option>
                                            <option value="standard">STANDARD</option>
                                            <option value="pro">PRO</option>
                                            <option value="ultra">ULTRA</option>
                                            <option value="admin">ADMIN</option>
                                        </select>
                                        <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-zinc-600">
                                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path></svg>
                                        </div>
                                    </div>
                                </div>
                                <button
                                    type="submit"
                                    className="bg-lime-400 hover:bg-lime-300 text-black font-black py-3.5 px-6 rounded-xl shadow-[0_0_20px_rgba(163,230,53,0.15)] transition-all uppercase tracking-tighter text-sm flex items-center justify-center gap-2 active:scale-95"
                                >
                                    <Users className="w-4 h-4" />
                                    DEPLOY_USER
                                </button>
                            </form>
                        </div>

                        {error && (
                            <div className="bg-red-500/10 border border-red-500/30 text-red-200 p-4 rounded-[1.5rem] mb-6 font-mono text-xs uppercase text-center tracking-widest">
                                CRITICAL_SYSTEM_ERROR: {error}
                            </div>
                        )}

                        <div className="space-y-4">
                            <h3 className="text-[10px] font-mono uppercase tracking-[0.4em] text-zinc-600 ml-4 mb-2 flex items-center gap-2">
                                Active_Accounts_Database
                                <span className="text-lime-400 font-bold">[{users.length}]</span>
                            </h3>

                            <div className="bg-zinc-900/20 rounded-[2.5rem] border border-zinc-900/50 overflow-hidden shadow-2xl backdrop-blur-sm">
                                {loading ? (
                                    <div className="p-20 text-center">
                                        <div className="inline-block w-8 h-8 border-2 border-lime-400/30 border-t-lime-400 rounded-full animate-spin mb-4"></div>
                                        <p className="text-[10px] font-mono text-zinc-600 uppercase tracking-widest">Reading_Data_Stream...</p>
                                    </div>
                                ) : users.length === 0 ? (
                                    <div className="p-20 text-center">
                                        <p className="text-[10px] font-mono text-zinc-700 uppercase tracking-widest">Zero_Agents_Detected</p>
                                    </div>
                                ) : (
                                    <div className="overflow-x-auto">
                                        <table className="w-full text-left min-w-[800px] border-collapse md:table block">
                                            <thead className="hidden md:table-header-group">
                                                <tr className="border-b border-zinc-800">
                                                    <th className="p-6 font-mono text-[10px] text-zinc-600 uppercase tracking-widest">Identity</th>
                                                    <th className="p-6 font-mono text-[10px] text-zinc-600 uppercase tracking-widest">Status</th>
                                                    <th className="p-6 font-mono text-[10px] text-zinc-600 uppercase tracking-widest">Activity</th>
                                                    <th className="p-6 font-mono text-[10px] text-zinc-600 uppercase tracking-widest">Lifecycle</th>
                                                    <th className="p-6 font-mono text-[10px] text-zinc-600 uppercase tracking-widest text-right">Actions</th>
                                                </tr>
                                            </thead>
                                            <tbody className="divide-y divide-zinc-900 md:table-row-group block">
                                                {users.map((user) => (
                                                    <tr key={user.id} className="hover:bg-lime-400/[0.02] transition-colors md:table-row block p-4 md:p-0 border-b border-zinc-900 md:border-0 mb-4 md:mb-0 bg-zinc-900/10 md:bg-transparent rounded-2xl md:rounded-none">
                                                        <td className="p-2 md:p-6 md:table-cell block">
                                                            <div className="flex flex-col">
                                                                <span className="text-white font-bold text-sm truncate max-w-[200px]">{user.username}</span>
                                                                <span className="text-[9px] font-mono text-zinc-600 uppercase tracking-tighter italic">ID_HEX_{user.id.toString(16).toUpperCase()}</span>
                                                            </div>
                                                        </td>
                                                        <td className="p-2 md:p-6 md:table-cell block">
                                                            <div className="flex items-center gap-2">
                                                                {user.username === 'admin' ? (
                                                                    <span className="px-3 py-1 rounded-full text-[9px] font-black bg-red-500/10 text-red-500 border border-red-500/20 uppercase tracking-widest">SYSTEM_OVERRIDE</span>
                                                                ) : (
                                                                    <select
                                                                        value={user.role}
                                                                        onChange={(e) => handleRoleUpdate(user.id, e.target.value)}
                                                                        className={`px-3 py-1.5 rounded-xl text-[10px] font-bold border bg-black focus:outline-none focus:border-lime-500/50 cursor-pointer uppercase tracking-tight transition-all ${user.role === 'admin' ? 'text-red-500 border-red-500/30' :
                                                                            user.role === 'ultra' ? 'text-purple-400 border-purple-500/30' :
                                                                                user.role === 'pro' ? 'text-blue-400 border-blue-500/30' :
                                                                                    user.role === 'standard' ? 'text-emerald-400 border-emerald-500/30' :
                                                                                        'text-zinc-500 border-zinc-800'
                                                                            }`}
                                                                    >
                                                                        <option value="user">DEMO_LVL</option>
                                                                        <option value="standard">STD_LVL</option>
                                                                        <option value="pro">PRO_LVL</option>
                                                                        <option value="ultra">ULTRA_LVL</option>
                                                                        <option value="admin">ADMIN_LVL</option>
                                                                    </select>
                                                                )}
                                                            </div>
                                                        </td>
                                                        <td className="p-2 md:p-6 md:table-cell block">
                                                            <div className="flex items-center gap-3">
                                                                <div>
                                                                    <p className="text-[10px] font-mono text-zinc-700 uppercase tracking-tighter">Exports</p>
                                                                    <p className="text-sm font-black text-lime-400">{user.download_count || 0}</p>
                                                                </div>
                                                                <div className="w-8 h-8 rounded-lg bg-lime-400/5 border border-lime-500/10 flex items-center justify-center text-lime-400/40">
                                                                    <Users className="w-3 h-3" />
                                                                </div>
                                                            </div>
                                                        </td>
                                                        <td className="p-2 md:p-6 md:table-cell block">
                                                            <div className="flex flex-col gap-1">
                                                                <div className="flex items-center gap-2 group">
                                                                    <Calendar className="w-2.5 h-2.5 text-zinc-700" />
                                                                    {editingExpiryId === user.id ? (
                                                                        <div className="flex items-center gap-2">
                                                                            <input
                                                                                type="text"
                                                                                value={tempExpiry}
                                                                                onChange={(e) => setTempExpiry(e.target.value)}
                                                                                className="bg-black border border-zinc-800 rounded-lg px-2 py-1 text-[10px] text-white focus:border-lime-500 outline-none w-32 font-mono"
                                                                            />
                                                                            <button onClick={() => handleExpiryUpdate(user.id)} className="text-[9px] bg-lime-400 text-black px-2 py-1 rounded-md font-bold uppercase transition-transform active:scale-95">SAVE</button>
                                                                            <button onClick={() => setEditingExpiryId(null)} className="text-[9px] text-zinc-500 hover:text-white px-1 uppercase">ESC</button>
                                                                        </div>
                                                                    ) : (
                                                                        <div
                                                                            className="cursor-pointer hover:text-lime-400 transition-colors font-mono text-[10px] text-zinc-400 uppercase tracking-tighter flex flex-col"
                                                                            onClick={() => { setEditingExpiryId(user.id); setTempExpiry(user.expiry_date); }}
                                                                        >
                                                                            <span className="text-zinc-600 text-[8px] tracking-widest leading-none">EXPIRATION_DATE</span>
                                                                            <span className="font-bold">{new Date(user.expiry_date).toLocaleDateString()}</span>
                                                                        </div>
                                                                    )}
                                                                </div>
                                                            </div>
                                                        </td>
                                                        <td className="p-2 md:p-6 md:table-cell block text-right">
                                                            {user.username !== 'admin' && (
                                                                <button
                                                                    onClick={() => handleDelete(user.id)}
                                                                    className="p-3 md:p-2 bg-red-500/5 hover:bg-red-500/20 text-zinc-600 hover:text-red-500 rounded-xl transition-all border border-transparent hover:border-red-500/20 flex md:inline-flex items-center justify-center w-full md:w-auto mt-4 md:mt-0"
                                                                >
                                                                    <Trash2 className="w-4 h-4" />
                                                                    <span className="md:hidden ml-2 text-[10px] font-mono uppercase font-bold">TERMINATE_ACCOUNT</span>
                                                                </button>
                                                            )}
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                )}
                            </div>
                        </div>
                    </>
                )}

                {activeTab === 'email' && (
                    <div className="bg-zinc-900/40 p-6 md:p-8 rounded-[2rem] border border-zinc-800 backdrop-blur-xl shadow-2xl">
                        {settingsError && (
                            <div className="mb-6 p-3 rounded-xl text-xs font-mono bg-red-500/10 text-red-200 border border-red-500/30 uppercase">
                                ERROR: {settingsError}
                            </div>
                        )}
                        {settingsLoading ? (
                            <div className="p-20 text-center">
                                <div className="inline-block w-8 h-8 border-2 border-lime-400/30 border-t-lime-400 rounded-full animate-spin mb-4"></div>
                                <p className="text-[10px] font-mono text-zinc-600 uppercase tracking-widest">Initializing_Uplink...</p>
                            </div>
                        ) : (
                            <form onSubmit={handleSettingsSave} className="space-y-8">
                                <div>
                                    <h3 className="text-sm font-mono uppercase tracking-[0.3em] text-zinc-500 mb-6 border-b border-zinc-800 pb-2">SMTP_Configuration</h3>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                        <div className="space-y-1">
                                            <label className="text-[10px] font-mono uppercase tracking-widest text-zinc-600">Host</label>
                                            <input type="text" value={emailSettings.smtp_host || ''} onChange={e => handleSettingChange('smtp_host', e.target.value)} className="w-full bg-black/50 border border-zinc-800 rounded-xl px-4 py-3 focus:outline-none focus:border-lime-500/50 text-sm font-mono text-white" />
                                        </div>
                                        <div className="space-y-1">
                                            <label className="text-[10px] font-mono uppercase tracking-widest text-zinc-600">Port</label>
                                            <input type="text" value={emailSettings.smtp_port || ''} onChange={e => handleSettingChange('smtp_port', e.target.value)} className="w-full bg-black/50 border border-zinc-800 rounded-xl px-4 py-3 focus:outline-none focus:border-lime-500/50 text-sm font-mono text-white" />
                                        </div>
                                        <div className="space-y-1">
                                            <label className="text-[10px] font-mono uppercase tracking-widest text-zinc-600">Username</label>
                                            <input type="text" value={emailSettings.smtp_user || ''} onChange={e => handleSettingChange('smtp_user', e.target.value)} className="w-full bg-black/50 border border-zinc-800 rounded-xl px-4 py-3 focus:outline-none focus:border-lime-500/50 text-sm font-mono text-white" />
                                        </div>
                                        <div className="space-y-1">
                                            <label className="text-[10px] font-mono uppercase tracking-widest text-zinc-600">Password</label>
                                            <div className="relative">
                                                <input
                                                    type={showSmtpPassword ? "text" : "password"}
                                                    value={emailSettings.smtp_pass || ''}
                                                    onChange={e => handleSettingChange('smtp_pass', e.target.value)}
                                                    className="w-full bg-black/50 border border-zinc-800 rounded-xl px-4 py-3 focus:outline-none focus:border-lime-500/50 text-sm font-mono text-white pr-10"
                                                />
                                                <button
                                                    type="button"
                                                    onClick={() => setShowSmtpPassword(!showSmtpPassword)}
                                                    className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-white transition-colors"
                                                >
                                                    {showSmtpPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                                </button>
                                            </div>
                                        </div>
                                        <div className="space-y-1">
                                            <label className="text-[10px] font-mono uppercase tracking-widest text-zinc-600">From Name</label>
                                            <input type="text" value={emailSettings.smtp_from_name || ''} onChange={e => handleSettingChange('smtp_from_name', e.target.value)} className="w-full bg-black/50 border border-zinc-800 rounded-xl px-4 py-3 focus:outline-none focus:border-lime-500/50 text-sm font-mono text-white" />
                                        </div>
                                        <div className="space-y-1">
                                            <label className="text-[10px] font-mono uppercase tracking-widest text-zinc-600">From Email</label>
                                            <input type="text" value={emailSettings.smtp_from_email || ''} onChange={e => handleSettingChange('smtp_from_email', e.target.value)} className="w-full bg-black/50 border border-zinc-800 rounded-xl px-4 py-3 focus:outline-none focus:border-lime-500/50 text-sm font-mono text-white" />
                                        </div>
                                    </div>

                                    <div>
                                    </div>
                                </div>

                                <div>
                                    <h3 className="text-sm font-mono uppercase tracking-[0.3em] text-zinc-500 mb-6 border-b border-zinc-800 pb-2">Admin_Notifications</h3>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                        <div className="space-y-1 md:col-span-2">
                                            <label className="text-[10px] font-mono uppercase tracking-widest text-zinc-600">Notification Email</label>
                                            <input type="text" value={emailSettings.admin_email || ''} onChange={e => handleSettingChange('admin_email', e.target.value)} className="w-full bg-black/50 border border-zinc-800 rounded-xl px-4 py-3 focus:outline-none focus:border-lime-500/50 text-sm font-mono text-white" placeholder="admin@example.com" />
                                        </div>
                                        <div className="space-y-1">
                                            <label className="text-[10px] font-mono uppercase tracking-widest text-zinc-600">Telegram Bot Token</label>
                                            <input type="text" value={emailSettings.telegram_bot_token || ''} onChange={e => handleSettingChange('telegram_bot_token', e.target.value)} className="w-full bg-black/50 border border-zinc-800 rounded-xl px-4 py-3 focus:outline-none focus:border-lime-500/50 text-sm font-mono text-white" placeholder="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11" />
                                        </div>
                                        <div className="space-y-1">
                                            <label className="text-[10px] font-mono uppercase tracking-widest text-zinc-600">Telegram Chat ID</label>
                                            <div className="flex gap-2">
                                                <input type="text" value={emailSettings.telegram_chat_id || ''} onChange={e => handleSettingChange('telegram_chat_id', e.target.value)} className="w-full bg-black/50 border border-zinc-800 rounded-xl px-4 py-3 focus:outline-none focus:border-lime-500/50 text-sm font-mono text-white" placeholder="-100123456789" />
                                                <button type="button" onClick={handleTestTelegram} className="bg-lime-400/10 hover:bg-lime-400/20 text-lime-400 border border-lime-400/20 rounded-xl px-4 flex items-center justify-center transition-all" title="Test Connection">
                                                    <Send className="w-4 h-4" />
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <div>
                                    <div className="flex justify-between items-center mb-6 border-b border-zinc-800 pb-2">
                                        <h3 className="text-sm font-mono uppercase tracking-[0.3em] text-zinc-500">Welcome_Email</h3>
                                        <button type="button" onClick={() => togglePreview('welcome')} className="text-[10px] font-mono uppercase tracking-widest text-lime-400 hover:text-white transition-colors">{previewMode.welcome ? 'EDIT_CODE' : 'VIEW_PREVIEW'}</button>
                                    </div>

                                    <div className="space-y-4">
                                        <div className="space-y-1">
                                            <label className="text-[10px] font-mono uppercase tracking-widest text-zinc-600">Subject</label>
                                            <input type="text" value={emailSettings.email_welcome_subject || ''} onChange={e => handleSettingChange('email_welcome_subject', e.target.value)} className="w-full bg-black/50 border border-zinc-800 rounded-xl px-4 py-3 focus:outline-none focus:border-lime-500/50 text-sm font-mono text-white" />
                                        </div>
                                        <div className="space-y-1">
                                            <label className="text-[10px] font-mono uppercase tracking-widest text-zinc-600">Body (HTML)</label>
                                            {previewMode.welcome ? (
                                                <div className="w-full bg-white rounded-xl overflow-hidden h-96">
                                                    <iframe
                                                        srcDoc={(emailSettings.email_welcome_body || '') + (() => {
                                                            // Mocking backend styling for preview
                                                            let donationHtml = `
                                                            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top: 40px; border-top: 1px solid #333; padding-top: 40px;">
                                                                <tr>
                                                                    <td align="center">
                                                                        <h3 style="color: #a3e635; font-family: monospace; text-transform: uppercase; font-size: 24px; margin: 0 0 10px 0; letter-spacing: -1px;">Support The Project</h3>
                                                                        <p style="color: #71717a; font-family: monospace; text-transform: uppercase; font-size: 12px; margin: 0 0 30px 0; letter-spacing: 2px;">Unlock advanced features & servers</p>
                                                                    </td>
                                                                </tr>
                                                                <tr>
                                                                    <td align="center">
                                                                        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width: 600px;">`;

                                                            for (let i = 1; i <= 4; i++) {
                                                                const title = emailSettings[`donation_tier${i}_title`] || `Tier ${i}`;
                                                                const desc = emailSettings[`donation_tier${i}_desc`] || 'Support us!';
                                                                const price = emailSettings[`donation_tier${i}_price`] || "";
                                                                const link = emailSettings[`donation_tier${i}_url`] || "";
                                                                const discountLabel = emailSettings[`donation_tier${i}_discount_label`] || "";
                                                                const discountAmount = emailSettings[`donation_tier${i}_discount_amount`] || "";
                                                                const hasDiscount = discountAmount && parseFloat(discountAmount) > 0;

                                                                let borderColor = '#27272a';
                                                                let textColor = '#a1a1aa';
                                                                let bgColor = '#18181b';

                                                                if (i === 2) { borderColor = 'rgba(59, 130, 246, 0.3)'; textColor = '#60a5fa'; bgColor = 'rgba(59, 130, 246, 0.05)'; }
                                                                else if (i === 3) { borderColor = 'rgba(52, 211, 153, 0.3)'; textColor = '#34d399'; bgColor = 'rgba(52, 211, 153, 0.05)'; }
                                                                else if (i === 4) { borderColor = 'rgba(192, 132, 252, 0.3)'; textColor = '#c084fc'; bgColor = 'rgba(192, 132, 252, 0.05)'; }

                                                                const priceHtml = hasDiscount
                                                                    ? `<span style="color: #71717a; text-decoration: line-through; font-size: 14px; margin-right: 10px;">${price}</span><span style="color: #a3e635; font-size: 24px; font-weight: 900;">${discountLabel}</span>`
                                                                    : `<span style="color: #fff; font-size: 24px; font-weight: 900;">${price}</span>`;

                                                                if (price && link) {
                                                                    donationHtml += `
                                                                    <tr>
                                                                        <td style="padding-bottom: 20px;">
                                                                            <table width="100%" cellpadding="20" cellspacing="0" border="0" style="background-color: ${bgColor}; border: 1px solid ${borderColor}; border-radius: 16px;">
                                                                                <tr>
                                                                                    <td style="font-family: Arial, sans-serif;">
                                                                                        ${hasDiscount ? '<div style="float: right; background-color: #a3e635; color: #000; font-size: 10px; font-weight: 900; text-transform: uppercase; padding: 4px 8px; border-radius: 0 0 0 8px;">OFFER</div>' : ''}
                                                                                        <h3 style="color: ${textColor}; font-size: 18px; text-transform: uppercase; margin: 0 0 10px 0; font-weight: 700;">${title}</h3>
                                                                                        <div style="margin-bottom: 15px;">
                                                                                            ${priceHtml}
                                                                                        </div>
                                                                                        <p style="color: #a1a1aa; font-size: 13px; margin: 0 0 20px 0; line-height: 1.5;">${desc}</p>
                                                                                        <table width="100%" cellspacing="0" cellpadding="0">
                                                                                            <tr>
                                                                                                <td align="center" style="background-color: #27272a; border-radius: 8px;">
                                                                                                    <a href="${link}" target="_blank" style="display: block; padding: 12px; color: #fff; text-decoration: none; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; font-family: monospace;">
                                                                                                        Obtain License
                                                                                                    </a>
                                                                                                </td>
                                                                                            </tr>
                                                                                        </table>
                                                                                    </td>
                                                                                </tr>
                                                                            </table>
                                                                        </td>
                                                                    </tr>`;
                                                                }
                                                            }
                                                            donationHtml += "</table></td></tr></table>";
                                                            return donationHtml;
                                                        })()}
                                                        className="w-full h-full border-none"
                                                        title="Welcome Preview"
                                                    />
                                                </div>
                                            ) : (
                                                <>
                                                    <textarea rows={8} value={emailSettings.email_welcome_body || ''} onChange={e => handleSettingChange('email_welcome_body', e.target.value)} className="w-full bg-black/50 border border-zinc-800 rounded-xl px-4 py-3 focus:outline-none focus:border-lime-500/50 text-sm font-mono text-white font-mono" />
                                                    <p className="text-[10px] text-zinc-500">Variables available: &#123;USERNAME&#125;, &#123;PASSWORD&#125;</p>
                                                </>
                                            )}
                                        </div>
                                    </div>
                                </div>

                                <div>
                                    <div className="flex justify-between items-center mb-6 border-b border-zinc-800 pb-2">
                                        <h3 className="text-sm font-mono uppercase tracking-[0.3em] text-zinc-500">Reset_Password_Email</h3>
                                        <button type="button" onClick={() => togglePreview('reset')} className="text-[10px] font-mono uppercase tracking-widest text-lime-400 hover:text-white transition-colors">{previewMode.reset ? 'EDIT_CODE' : 'VIEW_PREVIEW'}</button>
                                    </div>

                                    <div className="space-y-4">
                                        <div className="space-y-1">
                                            <label className="text-[10px] font-mono uppercase tracking-widest text-zinc-600">Subject</label>
                                            <input type="text" value={emailSettings.email_reset_subject || ''} onChange={e => handleSettingChange('email_reset_subject', e.target.value)} className="w-full bg-black/50 border border-zinc-800 rounded-xl px-4 py-3 focus:outline-none focus:border-lime-500/50 text-sm font-mono text-white" />
                                        </div>
                                        <div className="space-y-1">
                                            <label className="text-[10px] font-mono uppercase tracking-widest text-zinc-600">Body (HTML)</label>
                                            {previewMode.reset ? (
                                                <div className="w-full bg-white rounded-xl overflow-hidden h-96">
                                                    <iframe srcDoc={emailSettings.email_reset_body} className="w-full h-full border-none" title="Reset Preview" />
                                                </div>
                                            ) : (
                                                <>
                                                    <textarea rows={8} value={emailSettings.email_reset_body || ''} onChange={e => handleSettingChange('email_reset_body', e.target.value)} className="w-full bg-black/50 border border-zinc-800 rounded-xl px-4 py-3 focus:outline-none focus:border-lime-500/50 text-sm font-mono text-white font-mono" />
                                                    <p className="text-[10px] text-zinc-500">Variables available: &#123;PASSWORD&#125;</p>
                                                </>
                                            )}
                                        </div>
                                    </div>
                                </div>

                                <button type="submit" className="bg-lime-400 hover:bg-lime-300 text-black font-black py-4 px-8 rounded-xl shadow-[0_0_20px_rgba(163,230,53,0.15)] transition-all uppercase tracking-tighter text-sm w-full md:w-auto">
                                    SAVE_CONFIGURATION
                                </button>
                            </form>
                        )}
                    </div>
                )}


                {activeTab === 'donations' && (
                    <div className="bg-zinc-900/40 p-6 md:p-8 rounded-[2rem] border border-zinc-800 backdrop-blur-xl shadow-2xl">
                        {settingsLoading ? (
                            <div className="p-20 text-center">
                                <div className="inline-block w-8 h-8 border-2 border-lime-400/30 border-t-lime-400 rounded-full animate-spin mb-4"></div>
                                <p className="text-[10px] font-mono text-zinc-600 uppercase tracking-widest">Loading_Configs...</p>
                            </div>
                        ) : (
                            <form onSubmit={handleSettingsSave} className="space-y-8">

                                <div className="mb-10 border-b border-zinc-800 pb-10">
                                    <div className="flex justify-between items-center mb-6">
                                        <div className="flex items-center gap-4">
                                            <h3 className="text-sm font-mono uppercase tracking-[0.3em] text-lime-400 flex items-center gap-2">PayPal API Configuration</h3>
                                            <a
                                                href="/?page=donations"
                                                target="_blank"
                                                className="text-[10px] bg-lime-500/10 hover:bg-lime-500/20 text-lime-400 px-3 py-1.5 rounded-lg font-mono uppercase tracking-widest transition-all border border-lime-500/20 flex items-center gap-2"
                                            >
                                                <ExternalLink className="w-3 h-3" />
                                                OPEN_PAGE
                                            </a>
                                        </div>
                                        <button
                                            type="button"
                                            onClick={async () => {
                                                try {
                                                    alert("Sending test notification to admin...");
                                                    const res = await api.settings.testDonation(emailSettings);
                                                    if (res.success) {
                                                        alert(`Test Notification Sent!\nDebug Info:\nToken: ${res.debug?.token_used}\nChatID: ${res.debug?.chat_id_used}\nOutput: ${res.debug?.server_output}`);
                                                    } else {
                                                        alert("Failed: " + res.error + "\nOutput: " + res.output);
                                                    }
                                                } catch (e: any) {
                                                    alert("Error: " + e.message);
                                                }
                                            }}
                                            className="text-[10px] bg-zinc-800 hover:bg-zinc-700 text-lime-400 px-3 py-1.5 rounded-lg font-mono uppercase tracking-widest transition-all border border-lime-500/20"
                                        >
                                            TEST_NOTIFICATION
                                        </button>
                                    </div>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                        <div className="space-y-1">
                                            <label className="text-[10px] font-mono uppercase tracking-widest text-zinc-600">Client ID (Public)</label>
                                            <input type="text" value={emailSettings.paypal_client_id || ''} onChange={e => handleSettingChange('paypal_client_id', e.target.value)} className="w-full bg-black/50 border border-zinc-800 rounded-xl px-4 py-3 focus:outline-none focus:border-lime-500/50 text-sm font-mono text-white" placeholder="Client ID" />
                                        </div>
                                        <div className="space-y-1">
                                            <label className="text-[10px] font-mono uppercase tracking-widest text-zinc-600">Client Secret</label>
                                            <input
                                                value={emailSettings.paypal_secret || ''}
                                                onChange={e => handleSettingChange('paypal_secret', e.target.value)}
                                                className="w-full bg-black/50 border border-zinc-800 rounded-xl px-4 py-3 focus:outline-none focus:border-lime-500/50 text-sm font-mono text-white"
                                                placeholder="Hidden for security"
                                                type="password"
                                            />
                                        </div>
                                        <div className="space-y-1">
                                            <label className="text-[10px] font-mono uppercase tracking-widest text-zinc-600">Mode</label>
                                            <select
                                                value={emailSettings.paypal_mode || 'sandbox'}
                                                onChange={e => handleSettingChange('paypal_mode', e.target.value)}
                                                className="w-full bg-black/50 border border-zinc-800 rounded-xl px-4 py-3 focus:outline-none focus:border-lime-500/50 text-sm font-mono text-white"
                                            >
                                                <option value="sandbox">Sandbox (Testing)</option>
                                                <option value="live">Live (Production)</option>
                                            </select>
                                        </div>
                                    </div>
                                </div>

                                {[1, 2, 3, 4].map(tier => (
                                    <div key={tier} className="border-b border-zinc-800 pb-8 last:border-0 last:pb-0">
                                        <h3 className="text-sm font-mono uppercase tracking-[0.3em] text-zinc-500 mb-6 flex items-center gap-2">
                                            Tier_{tier}_Configuration
                                            {tier === 1 && <span className="text-xs bg-zinc-800 text-zinc-400 px-2 py-0.5 rounded">SUPPORTER</span>}
                                            {tier === 2 && <span className="text-xs bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded">STANDARD</span>}
                                            {tier === 3 && <span className="text-xs bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded">PRO</span>}
                                            {tier === 4 && <span className="text-xs bg-purple-500/20 text-purple-400 px-2 py-0.5 rounded">ULTRA</span>}
                                        </h3>
                                        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                                            <div className="space-y-1 md:col-span-2">
                                                <label className="text-[10px] font-mono uppercase tracking-widest text-zinc-600">Display Title</label>
                                                <input type="text" value={emailSettings[`donation_tier${tier}_title`] || ''} onChange={e => handleSettingChange(`donation_tier${tier}_title`, e.target.value)} className="w-full bg-black/50 border border-zinc-800 rounded-xl px-4 py-3 focus:outline-none focus:border-lime-500/50 text-sm font-mono text-white" />
                                            </div>
                                            <div className="space-y-1 md:col-span-2">
                                                <label className="text-[10px] font-mono uppercase tracking-widest text-zinc-600">Display Price Label</label>
                                                <input type="text" value={emailSettings[`donation_tier${tier}_price`] || ''} onChange={e => handleSettingChange(`donation_tier${tier}_price`, e.target.value)} className="w-full bg-black/50 border border-zinc-800 rounded-xl px-4 py-3 focus:outline-none focus:border-lime-500/50 text-sm font-mono text-white" />
                                            </div>
                                            <div className="space-y-1 md:col-span-2">
                                                <label className="text-[10px] font-mono uppercase tracking-widest text-lime-400">Discount Price Label (Optional)</label>
                                                <input type="text" value={emailSettings[`donation_tier${tier}_discount_label`] || ''} onChange={e => handleSettingChange(`donation_tier${tier}_discount_label`, e.target.value)} className="w-full bg-black/50 border border-zinc-800 rounded-xl px-4 py-3 focus:outline-none focus:border-lime-500/50 text-sm font-mono text-white" placeholder="e.g. €29.99" />
                                            </div>
                                            <div className="space-y-1 md:col-span-2">
                                                <label className="text-[10px] font-mono uppercase tracking-widest text-lime-400">Discount Amount (Optional)</label>
                                                <input type="number" step="0.01" value={emailSettings[`donation_tier${tier}_discount_amount`] || ''} onChange={e => handleSettingChange(`donation_tier${tier}_discount_amount`, e.target.value)} className="w-full bg-lime-400/10 border border-lime-500/30 rounded-xl px-4 py-3 focus:outline-none focus:border-lime-500 text-sm font-mono text-lime-400 font-bold" placeholder="0.00" />
                                            </div>
                                            <div className="space-y-1">
                                                <label className="text-[10px] font-mono uppercase tracking-widest text-lime-400">PayPal Amount</label>
                                                <input type="number" step="0.01" value={emailSettings[`donation_tier${tier}_amount`] || ''} onChange={e => handleSettingChange(`donation_tier${tier}_amount`, e.target.value)} className="w-full bg-lime-400/10 border border-lime-500/30 rounded-xl px-4 py-3 focus:outline-none focus:border-lime-500 text-sm font-mono text-lime-400 font-bold" placeholder="0.00" />
                                            </div>
                                            <div className="space-y-1">
                                                <label className="text-[10px] font-mono uppercase tracking-widest text-lime-400">Duration (Days)</label>
                                                <input type="number" value={emailSettings[`donation_tier${tier}_days`] || ''} onChange={e => handleSettingChange(`donation_tier${tier}_days`, e.target.value)} className="w-full bg-lime-400/10 border border-lime-500/30 rounded-xl px-4 py-3 focus:outline-none focus:border-lime-500 text-sm font-mono text-lime-400 font-bold" placeholder="365" />
                                            </div>
                                            <div className="space-y-1 md:col-span-4">
                                                <label className="text-[10px] font-mono uppercase tracking-widest text-zinc-600">Description</label>
                                                <textarea rows={2} value={emailSettings[`donation_tier${tier}_desc`] || ''} onChange={e => handleSettingChange(`donation_tier${tier}_desc`, e.target.value)} className="w-full bg-black/50 border border-zinc-800 rounded-xl px-4 py-3 focus:outline-none focus:border-lime-500/50 text-sm font-mono text-white" />
                                            </div>
                                        </div>
                                    </div>
                                ))}

                                <button type="submit" className="bg-lime-400 hover:bg-lime-300 text-black font-black py-4 px-8 rounded-xl shadow-[0_0_20px_rgba(163,230,53,0.15)] transition-all uppercase tracking-tighter text-sm w-full md:w-auto">
                                    SAVE_ALL_CONFIG
                                </button>
                            </form>
                        )
                        }
                    </div >
                )}

                {activeTab === 'templates' && (
                    <div className="bg-zinc-900/40 p-6 md:p-8 rounded-[2rem] border border-zinc-800 backdrop-blur-xl shadow-2xl">
                        <div className="flex justify-between items-center mb-6">
                            <h3 className="text-sm font-mono uppercase tracking-[0.3em] text-lime-400 flex items-center gap-2">
                                <File className="w-4 h-4" /> Template Management
                            </h3>
                            <div className="flex items-center gap-2">
                                <input
                                    type="text"
                                    placeholder="TEMPLATE NAME (Optional)"
                                    value={selectedTemplateName} // reusing this for upload name for simplicity or better add new state
                                    onChange={(e) => setSelectedTemplateName(e.target.value)}
                                    className="bg-black/50 border border-zinc-700 rounded-lg px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-lime-500 w-48"
                                />
                                <div className="relative overflow-hidden group">
                                    <button className="bg-lime-400 hover:bg-lime-300 text-black font-bold py-2 px-4 rounded-lg text-[10px] uppercase tracking-widest transition-all flex items-center gap-2">
                                        {isUploading ? <div className="w-3 h-3 border-2 border-black/30 border-t-black rounded-full animate-spin"></div> : <Upload className="w-3 h-3" />} Upload SVG
                                    </button>
                                    <input type="file" accept=".svg" onChange={handleTemplateUpload} disabled={isUploading} className="absolute inset-0 opacity-0 cursor-pointer" />
                                </div>
                            </div>
                        </div>

                        {templateLoading ? (
                            <div className="p-20 text-center">
                                <div className="inline-block w-8 h-8 border-2 border-lime-400/30 border-t-lime-400 rounded-full animate-spin mb-4"></div>
                                <p className="text-[10px] font-mono text-zinc-600 uppercase tracking-widest">Loading_Templates...</p>
                            </div>
                        ) : (
                            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 max-h-[400px] overflow-y-auto p-2">
                                {templates.map((tpl) => {
                                    const isHidden = tpl.startsWith('_hidden_');
                                    const displayName = tpl.replace('_hidden_', '').replace('.svg', '').replace(/_/g, ' ');

                                    return (
                                        <div key={tpl} className={`relative group border rounded-xl p-4 flex flex-col items-center gap-2 transition-all ${isHidden ? 'bg-zinc-900/50 border-zinc-800 text-zinc-600' : 'bg-black border-zinc-800 hover:border-lime-500/50'}`}>
                                            <div className="w-12 h-12 bg-zinc-900 rounded-lg flex items-center justify-center">
                                                <File className={`w-6 h-6 ${isHidden ? 'text-zinc-700' : 'text-lime-400'}`} />
                                            </div>

                                            {/* Name Display */}
                                            <span className="text-[10px] uppercase font-mono tracking-widest text-center truncate w-full">
                                                {displayName}
                                            </span>
                                            {isHidden && <span className="text-[8px] bg-red-900/30 text-red-500 px-1 rounded uppercase">Hidden</span>}

                                            {/* Hover Actions */}
                                            <div className="absolute inset-0 bg-black/80 flex items-center justify-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity rounded-xl backdrop-blur-sm">
                                                {/* Visibility Toggle */}
                                                <button
                                                    onClick={() => api.templates.toggleVisibility(tpl).then(fetchTemplates)}
                                                    className={`p-2 rounded-lg ${isHidden ? 'bg-lime-900/50 text-lime-400 hover:bg-lime-800' : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'}`}
                                                    title={isHidden ? "Show" : "Hide"}
                                                >
                                                    {isHidden ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
                                                </button>

                                                {/* Rename */}
                                                <button
                                                    onClick={() => {
                                                        const newName = prompt("Rename template:", displayName);
                                                        if (newName && newName !== displayName) {
                                                            api.templates.rename(tpl, newName).then(res => {
                                                                if (res.success) fetchTemplates();
                                                                else alert(res.error);
                                                            });
                                                        }
                                                    }}
                                                    className="p-2 bg-blue-900/50 hover:bg-blue-800 rounded-lg text-blue-400"
                                                    title="Rename"
                                                >
                                                    <Pencil className="w-3 h-3" />
                                                </button>

                                                {/* Delete */}
                                                <button
                                                    onClick={() => handleTemplateDelete(tpl)}
                                                    className="p-2 bg-red-900/50 hover:bg-red-800 rounded-lg text-red-400"
                                                    title="Delete"
                                                >
                                                    <Trash2 className="w-3 h-3" />
                                                </button>
                                            </div>
                                        </div>
                                    );
                                })}
                                {templates.length === 0 && (
                                    <div className="col-span-full py-12 text-center text-zinc-600 font-mono text-xs uppercase tracking-widest">
                                        No templates found
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )}

                {activeTab === 'fonts' && (
                    <div className="bg-zinc-900/40 p-6 md:p-8 rounded-[2rem] border border-zinc-800 backdrop-blur-xl shadow-2xl">
                        <div className="flex justify-between items-center mb-6">
                            <h3 className="text-sm font-mono uppercase tracking-[0.3em] text-lime-400 flex items-center gap-2">
                                <Type className="w-4 h-4" /> Font Management
                            </h3>
                            <div className="flex items-center gap-2">
                                <input
                                    type="text"
                                    placeholder="FONT NAME (Optional)"
                                    value={selectedFontName}
                                    onChange={(e) => setSelectedFontName(e.target.value)}
                                    className="bg-black/50 border border-zinc-700 rounded-lg px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-lime-500 w-48"
                                />
                                <div className="relative overflow-hidden group">
                                    <button className="bg-lime-400 hover:bg-lime-300 text-black font-bold py-2 px-4 rounded-lg text-[10px] uppercase tracking-widest transition-all flex items-center gap-2">
                                        {isUploading ? <div className="w-3 h-3 border-2 border-black/30 border-t-black rounded-full animate-spin"></div> : <Upload className="w-3 h-3" />} Upload TTF/ZIP
                                    </button>
                                    <input type="file" accept=".ttf,.otf,.zip" onChange={handleFontUpload} disabled={isUploading} className="absolute inset-0 opacity-0 cursor-pointer" />
                                </div>
                            </div>
                        </div>

                        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 max-h-[400px] overflow-y-auto p-2">
                            {fonts.map((font) => {
                                const isHidden = font.startsWith('_hidden_');
                                const displayName = font.replace('_hidden_', '').replace(/\.(ttf|otf)$/i, '').replace(/_/g, ' ');

                                return (
                                    <div key={font} className={`relative group border rounded-xl p-4 flex flex-col items-center gap-2 transition-all ${isHidden ? 'bg-zinc-900/50 border-zinc-800 text-zinc-600' : 'bg-black border-zinc-800 hover:border-lime-500/50'}`}>
                                        <div className="w-12 h-12 bg-zinc-900 rounded-lg flex items-center justify-center">
                                            <Type className={`w-6 h-6 ${isHidden ? 'text-zinc-700' : 'text-lime-400'}`} />
                                        </div>

                                        {/* Name Display */}
                                        <span className="text-[10px] uppercase font-mono tracking-widest text-center truncate w-full">
                                            {displayName}
                                        </span>
                                        {isHidden && <span className="text-[8px] bg-red-900/30 text-red-500 px-1 rounded uppercase">Hidden</span>}

                                        {/* Hover Actions */}
                                        <div className="absolute inset-0 bg-black/80 flex items-center justify-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity rounded-xl backdrop-blur-sm">
                                            <button
                                                onClick={() => api.fonts.toggleVisibility(font).then(fetchFonts)}
                                                className={`p-2 rounded-lg ${isHidden ? 'bg-lime-900/50 text-lime-400 hover:bg-lime-800' : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'}`}
                                                title={isHidden ? "Show" : "Hide"}
                                            >
                                                {isHidden ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
                                            </button>

                                            <button
                                                onClick={() => {
                                                    const newName = prompt("Rename font:", displayName);
                                                    if (newName && newName !== displayName) {
                                                        api.fonts.rename(font, newName).then(res => {
                                                            if (res.success) fetchFonts();
                                                            else alert(res.error);
                                                        });
                                                    }
                                                }}
                                                className="p-2 bg-blue-900/50 hover:bg-blue-800 rounded-lg text-blue-400"
                                                title="Rename"
                                            >
                                                <Pencil className="w-3 h-3" />
                                            </button>

                                            <button
                                                onClick={() => handleFontDelete(font)}
                                                className="p-2 bg-red-900/50 hover:bg-red-800 rounded-lg text-red-400"
                                                title="Delete"
                                            >
                                                <Trash2 className="w-3 h-3" />
                                            </button>
                                        </div>
                                    </div>
                                );
                            })}
                            {fonts.length === 0 && (
                                <div className="col-span-full py-12 text-center text-zinc-600 font-mono text-xs uppercase tracking-widest">
                                    No fonts found
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {activeTab === 'gadgets' && (
                    <div className="bg-zinc-900/40 p-6 md:p-8 rounded-[2rem] border border-zinc-800 backdrop-blur-xl shadow-2xl">
                        <div className="flex justify-between items-center mb-6">
                            <h3 className="text-sm font-mono uppercase tracking-[0.3em] text-lime-400 flex items-center gap-2">
                                <Smartphone className="w-4 h-4" /> Gadget Templates Manager
                            </h3>
                        </div>

                        {/* Create Gadget Form */}
                        <form onSubmit={handleGadgetCreate} className="bg-black/50 p-6 rounded-xl border border-zinc-800 mb-8">
                            <div className="flex justify-between items-center mb-4">
                                <h4 className="text-xs font-mono text-zinc-500 uppercase tracking-widest">{editingGadgetId ? 'Edit Gadget' : 'Add New Gadget'}</h4>
                                {editingGadgetId && (
                                    <button
                                        type="button"
                                        onClick={() => {
                                            setEditingGadgetId(null);
                                            setGadgetForm({ name: '', description: '', widthMm: '', heightMm: '', baseExtrusionMm: '', engravingDepthMm: '', defaultColor: '#ffffff' });
                                            setGadgetFile(null);
                                        }}
                                        className="text-[10px] text-zinc-500 hover:text-zinc-300 uppercase tracking-widest"
                                    >
                                        Cancel Edit
                                    </button>
                                )}
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                <div className="col-span-full mb-2">
                                    <label className="block text-[10px] font-mono text-zinc-500 uppercase tracking-widest mb-1">SVG Template File {editingGadgetId ? '(Optional)' : '(Auto-Detects Dimensions)'}</label>
                                    <input
                                        type="file"
                                        accept=".svg"
                                        onChange={handleGadgetFileChange}
                                        required={!editingGadgetId}
                                        className="w-full text-xs text-zinc-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:bg-lime-900/30 file:text-lime-400 hover:file:bg-lime-900/50 cursor-pointer"
                                    />
                                    <p className="text-[10px] text-zinc-600 mt-1">Select an SVG to auto-fill dimensions. Ensure units in SVG are correct or manually adjust below.</p>
                                </div>

                                <div>
                                    <label className="block text-[10px] font-mono text-zinc-500 uppercase tracking-widest mb-1">Template Name</label>
                                    <input
                                        type="text"
                                        value={gadgetForm.name}
                                        onChange={e => setGadgetForm({ ...gadgetForm, name: e.target.value })}
                                        required
                                        className="w-full bg-zinc-900/50 border border-zinc-700 rounded-lg p-2 text-xs text-white focus:border-lime-500 outline-none"
                                        placeholder="e.g. Phone Stand"
                                    />
                                </div>
                                <div className="col-span-2">
                                    <label className="block text-[10px] font-mono text-zinc-500 uppercase tracking-widest mb-1">Description</label>
                                    <input
                                        type="text"
                                        value={gadgetForm.description}
                                        onChange={e => setGadgetForm({ ...gadgetForm, description: e.target.value })}
                                        className="w-full bg-zinc-900/50 border border-zinc-700 rounded-lg p-2 text-xs text-white focus:border-lime-500 outline-none"
                                        placeholder="Brief description..."
                                    />
                                </div>

                                <div>
                                    <label className="block text-[10px] font-mono text-zinc-500 uppercase tracking-widest mb-1">Width (mm)</label>
                                    <input
                                        type="number"
                                        step="0.1"
                                        value={gadgetForm.widthMm}
                                        onChange={e => setGadgetForm({ ...gadgetForm, widthMm: e.target.value })}
                                        required
                                        className="w-full bg-zinc-900/50 border border-zinc-700 rounded-lg p-2 text-xs text-white focus:border-lime-500 outline-none"
                                    />
                                </div>
                                <div>
                                    <label className="block text-[10px] font-mono text-zinc-500 uppercase tracking-widest mb-1">Height (mm)</label>
                                    <input
                                        type="number"
                                        step="0.1"
                                        value={gadgetForm.heightMm}
                                        onChange={e => setGadgetForm({ ...gadgetForm, heightMm: e.target.value })}
                                        required
                                        className="w-full bg-zinc-900/50 border border-zinc-700 rounded-lg p-2 text-xs text-white focus:border-lime-500 outline-none"
                                    />
                                </div>
                                <div>
                                    <label className="block text-[10px] font-mono text-zinc-500 uppercase tracking-widest mb-1">Base Extrusion (mm)</label>
                                    <input
                                        type="number"
                                        step="0.1"
                                        value={gadgetForm.baseExtrusionMm}
                                        onChange={e => setGadgetForm({ ...gadgetForm, baseExtrusionMm: e.target.value })}
                                        required
                                        className="w-full bg-zinc-900/50 border border-zinc-700 rounded-lg p-2 text-xs text-white focus:border-lime-500 outline-none"
                                        placeholder="Default thickness"
                                    />
                                </div>
                                <div>
                                    <label className="block text-[10px] font-mono text-zinc-500 uppercase tracking-widest mb-1">Incisione (mm) [Optional]</label>
                                    <input
                                        type="number"
                                        step="0.1"
                                        value={gadgetForm.engravingDepthMm || ''}
                                        onChange={e => setGadgetForm({ ...gadgetForm, engravingDepthMm: e.target.value })}
                                        className="w-full bg-zinc-900/50 border border-zinc-700 rounded-lg p-2 text-xs text-white focus:border-lime-500 outline-none"
                                        placeholder="Overrides global default"
                                    />
                                </div>
                                <div>
                                    <label className="block text-[10px] font-mono text-zinc-500 uppercase tracking-widest mb-1">Default Color</label>
                                    <div className="flex gap-2">
                                        <input
                                            type="color"
                                            value={gadgetForm.defaultColor}
                                            onChange={e => setGadgetForm({ ...gadgetForm, defaultColor: e.target.value })}
                                            className="h-8 w-12 rounded cursor-pointer bg-transparent"
                                        />
                                        <input
                                            type="text"
                                            value={gadgetForm.defaultColor}
                                            onChange={e => setGadgetForm({ ...gadgetForm, defaultColor: e.target.value })}
                                            className="flex-1 bg-zinc-900/50 border border-zinc-700 rounded-lg p-2 text-xs text-white focus:border-lime-500 outline-none"
                                        />
                                    </div>
                                </div>

                                <div className="col-span-full flex justify-end mt-2">
                                    <button
                                        type="submit"
                                        disabled={isGadgetUploading}
                                        className="bg-lime-500 hover:bg-lime-400 text-black font-bold py-2 px-6 rounded-lg text-xs uppercase tracking-widest transition-all flex items-center gap-2"
                                    >
                                        {isGadgetUploading ? <div className="w-4 h-4 border-2 border-black/30 border-t-black rounded-full animate-spin"></div> : <Upload className="w-4 h-4" />}
                                        {editingGadgetId ? 'Update Gadget' : 'Upload Gadget'}
                                    </button>
                                </div>
                            </div>
                        </form>

                        {/* List Gadgets */}
                        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 max-h-[400px] overflow-y-auto p-2">
                            {gadgets.map((g) => {
                                const isHidden = g.hidden === true;
                                return (
                                    <div key={g.id} className={`relative group border rounded-xl p-4 flex flex-col items-center gap-2 transition-all ${isHidden ? 'bg-zinc-900/50 border-zinc-800 text-zinc-600' : 'bg-black border-zinc-800 hover:border-lime-500/50'}`}>
                                        <div className="w-12 h-12 bg-zinc-900 rounded-lg flex items-center justify-center">
                                            <Smartphone className={`w-6 h-6 ${isHidden ? 'text-zinc-600' : 'text-lime-400'}`} />
                                        </div>
                                        <span className="text-[10px] uppercase font-mono tracking-widest text-center truncate w-full">{g.name}</span>
                                        {isHidden && <span className="text-[8px] bg-red-900/30 text-red-500 px-1 rounded uppercase">Hidden</span>}
                                        <div className="text-[9px] text-zinc-500 font-mono flex flex-col items-center">
                                            <span>{g.widthMm}mm x {g.heightMm}mm</span>
                                            <span>Ext: {g.baseExtrusionMm}mm</span>
                                            {g.engravingDepthMm && <span>Inc: {g.engravingDepthMm}mm</span>}
                                        </div>

                                        <div className="absolute inset-0 bg-black/80 flex items-center justify-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity rounded-xl backdrop-blur-sm">
                                            <button
                                                onClick={() => handleGadgetVisibility(g.id)}
                                                className={`p-2 rounded-lg ${isHidden ? 'bg-lime-900/50 text-lime-400 hover:bg-lime-800' : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'}`}
                                                title={isHidden ? "Show" : "Hide"}
                                            >
                                                {isHidden ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
                                            </button>
                                            <button
                                                onClick={() => {
                                                    setEditingGadgetId(g.id);
                                                    setGadgetForm({
                                                        name: g.name,
                                                        description: g.description,
                                                        widthMm: g.widthMm,
                                                        heightMm: g.heightMm,
                                                        baseExtrusionMm: g.baseExtrusionMm,
                                                        engravingDepthMm: g.engravingDepthMm || '',
                                                        defaultColor: g.defaultColor || '#ffffff'
                                                    });
                                                    setGadgetFile(null);
                                                }}
                                                className="p-2 bg-blue-900/50 hover:bg-blue-800 rounded-lg text-blue-400"
                                                title="Edit"
                                            >
                                                <Pencil className="w-3 h-3" />
                                            </button>
                                            <button
                                                onClick={() => handleGadgetDelete(g.id)}
                                                className="p-2 bg-red-900/50 hover:bg-red-800 rounded-lg text-red-400"
                                                title="Delete"
                                            >
                                                <Trash2 className="w-3 h-3" />
                                            </button>
                                        </div>
                                    </div>
                                );
                            })}
                            {gadgets.length === 0 && (
                                <div className="col-span-full py-12 text-center text-zinc-600 font-mono text-xs uppercase tracking-widest">
                                    No gadgets found
                                </div>
                            )}
                        </div>
                    </div>
                )}

            </div >
        </div >
    );
};

export default AdminPanel;
