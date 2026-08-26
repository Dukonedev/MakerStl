import React, { useState } from 'react';
import { User, Lock, UserPlus, LogIn } from 'lucide-react';
import { PayPalScriptProvider, PayPalButtons } from "@paypal/react-paypal-js";
import { api } from '../api';

interface LoginProps {
    onLoginSuccess: (user: any) => void;
}

const Login: React.FC<LoginProps> = ({ onLoginSuccess }) => {
    console.log("Login component mounted");
    const [isRegistering, setIsRegistering] = useState(false);
    const [isRecovering, setIsRecovering] = useState(false);
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');

    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [globalDownloads, setGlobalDownloads] = useState<number | null>(null);
    const [globalUsers, setGlobalUsers] = useState<number | null>(null);

    const [showDonationModal, setShowDonationModal] = useState(false);
    const [donationSettings, setDonationSettings] = useState<any>({});

    React.useEffect(() => {
        const fetchStats = async () => {
            try {
                const response = await api.stats.getGlobal();
                if (response.success) {
                    setGlobalDownloads(response.total_downloads);
                    setGlobalUsers(response.total_users);
                }
            } catch (err) {
                console.error("Failed to fetch global stats", err);
            }
        };

        const fetchSettings = async () => {
            try {
                const response = await api.settings.getPublic();
                if (response.success && response.settings) {
                    setDonationSettings(response.settings);
                }
            } catch (err) {
                console.error("Failed to fetch donation settings", err);
            }
        };

        fetchStats();
        fetchSettings();
    }, []);



    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        // Email validation (bypass for 'admin')
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (username !== 'admin' && !emailRegex.test(username)) {
            setError('Please enter a valid email address');
            return;
        }

        setLoading(true);
        setError(null);

        try {
            if (isRecovering) {
                // PASSWORD RECOVERY
                const response = await api.auth.forgotPassword(username);
                if (response.success) {
                    setError('New password sent to your email!');
                    setIsRecovering(false); // Go back to login
                    setIsRegistering(false);
                } else {
                    setError(response.error || 'Failed to reset password');
                }
            } else {
                // NORMAL LOGIN / REGISTER
                const credentials = { username, password };
                const response = isRegistering
                    ? await api.auth.register(credentials)
                    : await api.auth.login(credentials);

                if (response.success) {
                    if (isRegistering) {
                        setIsRegistering(false);
                        setError('Account created! Please log in.');
                        setLoading(false);
                    } else {
                        // FIX: Add small delay to allow browser "Save Password" prompt to initialize 
                        // before React unmounts the form. This prevents 'removeChild' errors.
                        setTimeout(() => {
                            onLoginSuccess(response.user);
                        }, 300);
                    }
                } else {
                    setError(response.error);
                }
            }
        } catch (err: any) {
            setError(err.message || 'An unexpected error occurred');
        } finally {
            if ((!isRegistering && !isRecovering) || error) {
                setLoading(false);
            }
        }
    };

    return (
        <div className="flex flex-col items-center justify-center min-h-screen bg-black text-white p-4 cyber-bg">
            {/* ... (background divs stay same) ... */}
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,#1a2e05_0%,transparent_70%)] pointer-events-none opacity-50" />
            <div className="bg-zinc-900/40 p-10 rounded-[2rem] shadow-[0_0_50px_rgba(0,0,0,0.5)] w-full max-w-sm border border-zinc-800 backdrop-blur-xl relative z-10 transition-all hover:border-lime-500/30">
                <h2 className="text-4xl font-black mb-1 text-center text-lime-400 tracking-tighter uppercase italic">
                    Keygen 3D
                </h2>
                <p className="text-zinc-500 text-center mb-10 text-[10px] font-mono uppercase tracking-[0.2em] opacity-80">
                    {isRecovering ? 'Recover Password' : (isRegistering ? 'Create an account' : 'Sign in to your account')}
                </p>

                {error && (
                    <div className={`p-3 rounded-lg mb-6 text-sm ${error.includes('created') || error.includes('sent') ? 'bg-green-500/10 text-green-400 border border-green-500/50' : 'bg-red-500/10 text-red-200 border border-red-500/50'}`}>
                        {error}
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-4" autoComplete="off">
                    <div className="space-y-1">
                        <label className="text-[10px] font-mono uppercase tracking-widest text-zinc-600 ml-1">Email Address</label>
                        <div className="relative">
                            <User className="absolute left-3.5 top-3 w-4 h-4 text-zinc-500" />
                            <input
                                type="email"
                                name="email"
                                autoComplete="new-password" // Trick to disable autocomplete usually
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                required
                                className="w-full bg-black/50 border border-zinc-800 rounded-xl py-3 pl-11 pr-4 focus:outline-none focus:border-lime-500/50 text-sm placeholder-zinc-700 transition-all font-mono"
                                placeholder="USER@EMAIL.COM"
                            />
                        </div>
                    </div>

                    {!isRecovering && (
                        <div className="space-y-1">
                            <label className="text-[10px] font-mono uppercase tracking-widest text-zinc-600 ml-1">Password</label>
                            <div className="relative">
                                <Lock className="absolute left-3.5 top-3 w-4 h-4 text-zinc-500" />
                                <input
                                    type="password"
                                    name="password"
                                    autoComplete="new-password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    required
                                    className="w-full bg-black/50 border border-zinc-800 rounded-xl py-3 pl-11 pr-4 focus:outline-none focus:border-lime-500/50 text-sm placeholder-zinc-700 transition-all font-mono"
                                    placeholder="••••••••"
                                />
                            </div>
                        </div>
                    )}

                    <button
                        type="submit"
                        disabled={loading}
                        className="w-full mt-8 bg-lime-400 hover:bg-lime-300 text-black font-black py-4 rounded-xl shadow-[0_0_20px_rgba(163,230,53,0.3)] transition-all transform active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 uppercase tracking-tighter"
                    >
                        {loading ? (
                            <span className="w-5 h-5 border-2 border-black/30 border-t-black rounded-full animate-spin" />
                        ) : (
                            <>
                                {isRecovering ? <Lock className="w-4 h-4" /> : (isRegistering ? <UserPlus className="w-4 h-4" /> : <LogIn className="w-4 h-4" />)}
                                {isRecovering ? 'RESET_PASSWORD' : (isRegistering ? 'INITIALIZE_ACC' : 'ACCESS_SYSTEM')}
                            </>
                        )}
                    </button>
                </form>

                <div className="mt-6 text-center space-y-2">
                    <button
                        type="button"
                        onClick={() => { setIsRegistering(!isRegistering); setIsRecovering(false); setError(null); }}
                        className="text-xs text-slate-500 hover:text-indigo-400 transition-colors block w-full"
                    >
                        {isRegistering ? 'Already have an account? Sign In' : 'Need an account? Register'}
                    </button>

                    {!isRegistering && !isRecovering && (
                        <button
                            type="button"
                            onClick={() => { setIsRecovering(true); setError(null); }}
                            className="text-xs text-lime-600/70 hover:text-lime-400 transition-colors block w-full"
                        >
                            Forgot Password?
                        </button>
                    )}

                    {isRecovering && (
                        <button
                            type="button"
                            onClick={() => { setIsRecovering(false); setError(null); }}
                            className="text-xs text-slate-500 hover:text-indigo-400 transition-colors block w-full"
                        >
                            Back to Login
                        </button>
                    )}


                    <div className="mt-4 pt-4 border-t border-zinc-800">
                        <button
                            type="button"
                            onClick={() => onLoginSuccess({ id: 0, username: 'Guest', role: 'guest' })}
                            className="text-xs text-emerald-500 hover:text-emerald-400 transition-colors flex items-center justify-center gap-1 mx-auto"
                        >
                            <span>Continue as Guest (Offline)</span>
                        </button>
                    </div>
                    {/* Donation / Support Button */}
                    <div className="mt-4 text-center">
                        <button
                            type="button"
                            onClick={() => setShowDonationModal(true)}
                            className="text-[10px] text-zinc-500 hover:text-lime-400 transition-colors uppercase tracking-widest flex items-center justify-center gap-1 mx-auto hover:underline"
                        >
                            <UserPlus className="w-3 h-3" /> {/* Reusing icon or import Heart if preferred */}
                            Support Development & Get Premium
                        </button>
                    </div>
                </div>

                {(globalDownloads != null || globalUsers != null) && (
                    <div className="mt-8 space-y-3">
                        <div className="p-4 bg-lime-400/5 border border-lime-500/20 rounded-2xl text-center">
                            <span className="text-[10px] font-mono text-lime-400/60 uppercase tracking-widest block mb-1 font-bold">Total Users</span>
                            <span className="text-2xl font-black text-lime-400">{(globalUsers ?? 0).toLocaleString()}</span>
                        </div>
                        <div className="p-4 bg-lime-400/5 border border-lime-500/20 rounded-2xl text-center">
                            <span className="text-[10px] font-mono text-lime-400/60 uppercase tracking-widest block mb-1 font-bold">Total Exports</span>
                            <span className="text-2xl font-black text-lime-400">{(globalDownloads ?? 0).toLocaleString()}</span>
                        </div>
                    </div>
                )}
            </div>

            {/* Donation Modal - Native PayPal Integration */}
            {showDonationModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
                    <div className="bg-zinc-900 border border-zinc-800 rounded-[2rem] p-6 md:p-10 w-full max-w-5xl max-h-[90vh] overflow-y-auto shadow-2xl relative">
                        <button
                            onClick={() => setShowDonationModal(false)}
                            className="absolute top-6 right-6 text-zinc-500 hover:text-white transition-colors z-50"
                        >
                            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                        </button>

                        <h2 className="text-2xl font-black text-lime-400 mb-2 uppercase italic tracking-tighter">Choose Your Plan</h2>
                        <p className="text-zinc-500 text-xs font-mono uppercase tracking-widest mb-8">Support the project and unlock advanced features</p>

                        {(() => {
                            const hasPayPal = !!donationSettings.paypal_client_id;

                            const tiersGrid = (
                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                                    {[1, 2, 3, 4].map(tier => {
                                        const title = donationSettings[`donation_tier${tier}_title`] || `Tier ${tier}`;
                                        const desc = donationSettings[`donation_tier${tier}_desc`] || 'Support us!';
                                        const originalPriceLabel = donationSettings[`donation_tier${tier}_price`] || 'N/A';
                                        const originalAmount = donationSettings[`donation_tier${tier}_amount`];

                                        const discountLabel = donationSettings[`donation_tier${tier}_discount_label`];
                                        const discountAmount = donationSettings[`donation_tier${tier}_discount_amount`];

                                        const hasDiscount = discountAmount && parseFloat(discountAmount) > 0;
                                        const finalAmount = hasDiscount ? discountAmount : originalAmount;

                                        const theme = tier === 1 ? 'zinc' : tier === 2 ? 'blue' : tier === 3 ? 'emerald' : 'purple';
                                        const themeColor = tier === 1 ? 'text-zinc-400' : tier === 2 ? 'text-blue-400' : tier === 3 ? 'text-emerald-400' : 'text-purple-400';
                                        const themeBorder = tier === 1 ? 'border-zinc-700' : tier === 2 ? 'border-blue-500/30' : tier === 3 ? 'border-emerald-500/30' : 'border-purple-500/30';
                                        const themeBg = tier === 1 ? 'bg-zinc-800/50' : tier === 2 ? 'bg-blue-500/10' : tier === 3 ? 'bg-emerald-500/10' : 'bg-purple-500/10';

                                        return (
                                            <div key={tier} className={`flex flex-col p-6 rounded-2xl border ${themeBorder} ${themeBg} relative overflow-hidden transition-all hover:scale-[1.02]`}>
                                                {hasDiscount && (
                                                    <div className="absolute top-0 right-0 bg-lime-400 text-black text-[10px] font-black uppercase tracking-widest px-3 py-1 rounded-bl-xl shadow-lg z-20">
                                                        OFFER
                                                    </div>
                                                )}

                                                <h3 className={`text-xl font-bold uppercase mb-2 ${themeColor}`}>{title}</h3>

                                                <div className="flex items-baseline gap-2 mb-4 flex-wrap">
                                                    {hasDiscount ? (
                                                        <>
                                                            <span className="text-zinc-500 line-through text-sm font-mono decoration-zinc-500/50 decoration-2">{originalPriceLabel}</span>
                                                            <span className="text-2xl font-black text-lime-400">{discountLabel || `€${discountAmount}`}</span>
                                                        </>
                                                    ) : (
                                                        <div className="text-2xl font-black text-white">{originalPriceLabel}</div>
                                                    )}
                                                </div>

                                                <p className="text-xs text-zinc-400 mb-6 flex-grow leading-relaxed">{desc}</p>

                                                <div className="relative z-10 block min-h-[40px]">
                                                    {finalAmount && parseFloat(finalAmount) > 0 && hasPayPal ? (
                                                        <PayPalButtons
                                                            style={{ layout: "horizontal", color: "blue", height: 40, tagline: false }}
                                                            createOrder={(data, actions) => {
                                                                return actions.order.create({
                                                                    intent: "CAPTURE",
                                                                    purchase_units: [{
                                                                        description: `${title} License`,
                                                                        amount: { value: finalAmount, currency_code: "EUR" }
                                                                    }]
                                                                });
                                                            }}
                                                            onApprove={async (data, actions) => {
                                                                return actions.order!.capture().then(async (details) => {
                                                                    // Call Backend to Verify & Create User
                                                                    try {
                                                                        const res = await api.auth.verifyPayment({
                                                                            orderID: data.orderID,
                                                                            tierID: tier,
                                                                            userIdentifier: username // Use current input email if provided
                                                                        });
                                                                        if (res.success) {
                                                                            alert(`Payment Successful! Role: ${res.role}. Check email for credentials.`);
                                                                            setShowDonationModal(false);
                                                                        } else {
                                                                            alert('Payment Verified but User Update Failed: ' + res.error);
                                                                        }
                                                                    } catch (e: any) {
                                                                        alert('Server Error: ' + e.message);
                                                                    }
                                                                });
                                                            }}
                                                        />
                                                    ) : (
                                                        <a
                                                            href={donationSettings[`donation_tier${tier}_url`] || 'https://paypal.me/virtuprinto'}
                                                            target="_blank"
                                                            rel="noopener noreferrer"
                                                            className={`block w-full py-3 rounded-xl font-bold text-xs uppercase tracking-widest text-center transition-all bg-zinc-700 hover:bg-zinc-600 text-white`}
                                                        >
                                                            {hasPayPal ? 'Free Donation' : 'Donation/Support'}
                                                        </a>
                                                    )}
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            );

                            return hasPayPal ? (
                                <PayPalScriptProvider options={{ "clientId": donationSettings.paypal_client_id, currency: "EUR" }}>
                                    {tiersGrid}
                                </PayPalScriptProvider>
                            ) : (
                                tiersGrid
                            );
                        })()}

                        <div className="mt-8 text-center text-[10px] text-zinc-600 font-mono uppercase">
                            Secure Payment via PayPal. Accounts are automatically created/upgraded.
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default Login;
