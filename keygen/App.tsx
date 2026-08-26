import React, { useState, useRef, useDeferredValue, useEffect } from 'react';
import { Scene, SceneRef } from './components/Scene';
import { Controls } from './components/Controls';
import { KeychainConfig } from './types';
import { Loader2, Calendar, Download as DownloadIcon, User as UserIcon, RotateCcw, Move } from 'lucide-react';
import { PayPalScriptProvider, PayPalButtons } from "@paypal/react-paypal-js";
import Login from './src/components/Login';
import AdminPanel from './src/components/AdminPanel';
import { AVAILABLE_FONTS } from './src/constants';
import { api } from './src/api';

import { UltraStudio } from './components/UltraStudio';

import { DonationsView } from './src/components/DonationsView';

const App: React.FC = () => {
  console.log("App mounted");

  // Simple Routing
  const urlParams = new URLSearchParams(window.location.search);
  const isDonationPage = urlParams.get('page') === 'donations';

  const sceneRef = useRef<SceneRef>(null);
  // SUPER NUCLEAR FIX: Lazy Init to avoid mount flicker & DOM issues
  const [user, setUser] = useState<any>(() => {
    try {
      const savedUser = localStorage.getItem('user');
      if (savedUser) {
        return JSON.parse(savedUser);
      }
    } catch (e) {
      console.error("Failed to parse user from storage", e);
      localStorage.removeItem('user');
    }
    return null;
  });

  const handleLoginSuccess = (userData: any) => {
    // SUPER NUCLEAR FIX:
    // Instead of React state update (which triggers reconciliation & removeChild error),
    // we save to LocalStorage and RELOAD the page. The browser handles the DOM wipe.
    localStorage.setItem('user', JSON.stringify(userData));
    window.location.reload();
  };

  // Only update user state (e.g. download count) without changing view mode
  const handleUserUpdate = (userData: any) => {
    setUser(userData);
    localStorage.setItem('user', JSON.stringify(userData));
  };

  const handleLogout = () => {
    setUser(null);
    localStorage.removeItem('user');
    window.location.reload(); // Clean slate on logout too
  };

  const [config, setConfig] = useState<KeychainConfig>({
    text: 'TOMAS',
    fontSize: 14.0,
    thickness: 2.4,
    textDepth: 1.0,
    color: '#eab308', // Khaki/Yellowish
    textColor: '#880000', // DarkRed
    fontUrl: AVAILABLE_FONTS[2].url, // Optimer Bold (Default startup font)
    baseShape: 'outline',
    fontScaleX: 1.0,
    letterSpacing: -0.1,
    baseWidth: 80.0,
    outlineSize: 1.4,
    roundness: 32,
    ringOverlap: 1.5,
    ringOffsetY: 0,
    textOffsetY: 0,
    edgeRoundness: 0,
    addBorder: false,
    addSecondOutline: false,
    secondOutlineSize: 1,
    secondOutlineDepth: 1,
    secondOutlineEdgeRoundness: 0,
    baseRoundness: 8,
    textOffsetX: 0,
    svgMaxDimension: 50, // Default 50mm
    showRing: true,
    ringPosition: 0,
    // baseRoundness defined above
  });

  // Missing State Definitions
  const [showAdminPanel, setShowAdminPanel] = useState(false);
  const [mode, setMode] = useState<'keychain' | 'ultra'>('keychain');
  const [autoRotate, setAutoRotate] = useState(true);
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);
  const [donationSettings, setDonationSettings] = useState<any>({});

  // Optimize performance: slow 3D updates shouldn't block the UI
  const deferredConfig = useDeferredValue(config);
  const isStale = config !== deferredConfig;

  // Expiration Logic
  const expiryDate = user?.expiry_date ? new Date(user.expiry_date) : new Date();
  const isExpired = new Date() > expiryDate;

  const handleExport = async (format: 'stl') => {
    if (sceneRef.current) {
      sceneRef.current.exportSTL();

      // Track download (Async, don't block UI)
      if (user && user.id) {
        try {
          const response = await api.stats.track(user.id);
          if (response.success) {
            // Update local user state with new count
            const updatedUser = { ...user, download_count: response.download_count };
            setUser(updatedUser);
            localStorage.setItem('user', JSON.stringify(updatedUser));
          }
        } catch (e) {
          console.error("Failed to track download", e);
        }
      }
    }
  };

  // Fetch Settings for Modal (Always run, safe to run early)
  useEffect(() => {
    const fetchSettings = async () => {
      try {
        // We can check if we actually need them here, or just fetch them globally
        const response = await api.settings.getPublic();
        if (response.success && response.settings) {
          setDonationSettings(response.settings);
        }
      } catch (err) {
        console.error("Failed to fetch donation settings", err);
      }
    };
    fetchSettings();
  }, []);

  // Reset Camera
  const handleResetCamera = () => {
    if (sceneRef.current) {
      sceneRef.current.resetCamera();
    }
  };

  if (!user) {
    return <Login key="login-view" onLoginSuccess={handleLoginSuccess} />;
  }

  // Admin Panel View
  if (showAdminPanel && user.role === 'admin') {
    return <AdminPanel key="admin-view" onLogout={handleLogout} onBack={() => setShowAdminPanel(false)} />;
  }

  return (
    <div key="main-app-view" className="min-h-screen bg-black flex items-center justify-center p-4 md:p-8 relative cyber-bg overflow-hidden">

      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_-20%,#1a2e05_0%,transparent_50%)] pointer-events-none opacity-50" />

      {/* Top Right Controls: Logout & Mode Switcher */}
      <div className="absolute top-4 right-4 z-50 flex items-center gap-3">
        {/* Admin Panel Toggle */}
        {user.role === 'admin' && (
          <button
            onClick={() => setShowAdminPanel(true)}
            className="bg-zinc-800/80 hover:bg-zinc-700 text-lime-400 px-4 py-2 rounded-xl backdrop-blur-md border border-lime-500/20 shadow-lg transition-all font-mono text-xs uppercase tracking-widest flex items-center gap-2"
          >
            <RotateCcw className="w-3 h-3" /> {/* Using generic icon or dedicated 'Settings/Shield' icon would be better but keeping simple */}
            Admin_Panel
          </button>
        )}

        {/* Mode Switcher for Ultra/Admin */}
        {(user.role === 'admin' || user.role === 'ultra') && (
          <div className="bg-black/80 backdrop-blur-sm rounded-full p-1 border border-zinc-800 flex items-center">
            <button
              onClick={() => setMode('keychain')}
              className={`px-4 py-1.5 rounded-full text-xs font-bold uppercase transition-all ${mode === 'keychain' ? 'bg-lime-500 text-black shadow-[0_0_10px_rgba(163,230,53,0.4)]' : 'text-zinc-500 hover:text-white'}`}
            >
              Keychain
            </button>
            <button
              onClick={() => setMode('ultra')}
              className={`px-4 py-1.5 rounded-full text-xs font-bold uppercase transition-all ${mode === 'ultra' ? 'bg-purple-500 text-white shadow-[0_0_10px_rgba(168,85,247,0.4)]' : 'text-zinc-500 hover:text-white'}`}
            >
              Ultra Studio
            </button>
          </div>
        )}

        <button
          onClick={() => {
            if (confirm('Clear local cache and reload?')) {
              localStorage.clear();
              sessionStorage.clear();
              window.location.reload();
            }
          }}
          className="bg-black/80 hover:bg-zinc-900 text-zinc-400 hover:text-red-400 p-2 rounded-full transition-all border border-zinc-800 hover:border-red-500/30 shadow-[0_0_15px_rgba(0,0,0,0.1)] backdrop-blur-sm"
          title="Clear Cache & Reset"
        >
          <RotateCcw className="w-4 h-4" />
        </button>

        <button
          onClick={handleLogout}
          className="bg-black/80 hover:bg-zinc-900 text-lime-400 p-2 rounded-full transition-all border border-lime-500/30 shadow-[0_0_15px_rgba(163,230,53,0.1)] backdrop-blur-sm"
          title="Logout"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" x2="9" y1="12" y2="12" /></svg>
        </button>
      </div>

      {mode === 'ultra' ? (
        <UltraStudio user={user} onUserUpdate={handleUserUpdate} />
      ) : (
        <div className="w-full max-w-7xl h-[90vh] grid grid-cols-1 lg:grid-cols-2 gap-6">

          {/* Left Panel: 3D Scene */}
          <div className="lg:col-span-1 relative h-[40vh] lg:h-auto rounded-3xl overflow-hidden shadow-[0_0_50px_rgba(0,0,0,0.5)] border border-zinc-900 bg-black group">

            {/* HUD Overlay */}
            <div className="absolute inset-0 pointer-events-none z-10">
              {/* Corner Accents */}
              <div className="absolute top-0 left-0 w-16 h-16 border-l-2 border-t-2 border-lime-500/30 rounded-tl-xl"></div>
              <div className="absolute top-0 right-0 w-16 h-16 border-r-2 border-t-2 border-lime-500/30 rounded-tr-xl"></div>
              <div className="absolute bottom-0 left-0 w-16 h-16 border-l-2 border-b-2 border-lime-500/30 rounded-bl-xl"></div>
              <div className="absolute bottom-0 right-0 w-16 h-16 border-r-2 border-b-2 border-lime-500/30 rounded-br-xl"></div>

              {/* Crosshairs */}
              <div className="absolute top-1/2 left-4 w-2 h-0.5 bg-lime-500/20"></div>
              <div className="absolute top-1/2 right-4 w-2 h-0.5 bg-lime-500/20"></div>
              <div className="absolute bottom-4 left-1/2 w-0.5 h-2 bg-lime-500/20"></div>
              <div className="absolute top-4 left-1/2 w-0.5 h-2 bg-lime-500/20"></div>

              {/* Status Header */}
              <div className="absolute top-6 left-6 flex items-center gap-3">
                <div className="bg-black/40 backdrop-blur-md border border-lime-500/20 px-3 py-1 rounded text-[10px] font-mono text-lime-400 uppercase tracking-widest flex items-center gap-2">
                  <div className={`w-1.5 h-1.5 rounded-full ${isStale ? 'bg-yellow-500 animate-pulse' : 'bg-lime-500 animate-pulse'}`}></div>
                  {isStale ? 'RENDERING...' : 'LIVE FEED'}
                </div>
                {isStale && <Loader2 className="w-3 h-3 text-lime-400 animate-spin" />}
              </div>
            </div>

            {/* Interactive Controls Overlay */}
            <div className="absolute bottom-6 left-6 right-6 z-20 flex justify-between items-end">
              <div className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest opacity-60">
                <p>CAM_POS: {config.svgMaxDimension}mm</p>
                <p>GRID_RES: 5.0</p>
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => setAutoRotate(!autoRotate)}
                  className={`p-2 rounded border transition-all backdrop-blur-md ${autoRotate ? 'bg-lime-500/20 border-lime-500 text-lime-400' : 'bg-black/40 border-zinc-700 text-zinc-400 hover:border-lime-500/50 hover:text-white'}`}
                  title="Toggle Auto-Rotate"
                >
                  <RotateCcw className={`w-4 h-4 ${autoRotate ? 'animate-spin-slow' : ''}`} />
                </button>
                <button
                  onClick={handleResetCamera}
                  className="p-2 rounded border bg-black/40 border-zinc-700 text-zinc-400 hover:border-lime-500/50 hover:text-white transition-all backdrop-blur-md"
                  title="Reset Camera View"
                >
                  <Move className="w-4 h-4" />
                </button>
              </div>
            </div>

            <Scene ref={sceneRef} config={deferredConfig} autoRotate={autoRotate} />
          </div>

          {/* Right Panel: Controls */}
          <div className="h-full flex flex-col gap-6 overflow-hidden">
            <div className="flex-grow overflow-y-auto pr-2 custom-scrollbar">
              <Controls
                config={config}
                onChange={setConfig}
                onExport={handleExport}
                fonts={AVAILABLE_FONTS}
                userRole={user?.role || 'user'}
                isExpired={isExpired}
              />
            </div>

            {/* User Info Section */}
            <div className="bg-zinc-900/40 p-5 rounded-2xl border border-zinc-800 backdrop-blur-sm flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-lime-400/10 border border-lime-500/20 flex items-center justify-center text-lime-400 relative">
                  <UserIcon className="w-5 h-5" />
                  {/* Role Indicator Badge */}
                  <div className={`absolute -top-1 -right-1 w-3 h-3 rounded-full border border-black ${user.role === 'ultra' || user.role === 'admin' ? 'bg-purple-500' : 'bg-blue-500'}`} />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest leading-tight">User</p>
                    <span className={`text-[8px] font-bold px-1 rounded uppercase ${user.role === 'ultra' ? 'bg-purple-500/20 text-purple-400' : 'bg-blue-500/20 text-blue-400'}`}>
                      {user.role}
                    </span>
                  </div>
                  <p className="text-sm font-black text-white uppercase">{user.username}</p>
                </div>
              </div>

              <div className="h-8 w-px bg-zinc-800" />

              <div className="flex-1 px-2">
                <div className="flex justify-between items-center">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <Calendar className="w-3.5 h-3.5 text-lime-400/60" />
                      <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">Expires On</p>
                    </div>
                    <p className={`text-xs font-bold ${isExpired ? 'text-red-400' : 'text-zinc-300'}`}>
                      {expiryDate.toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })}
                      {isExpired && <span className="ml-2 text-[10px] bg-red-500/10 text-red-500 px-1.5 py-0.5 rounded border border-red-500/20">EXPIRED</span>}
                    </p>
                  </div>

                  <button
                    onClick={() => setShowUpgradeModal(true)}
                    className="bg-lime-500 hover:bg-lime-400 text-black text-[10px] font-black uppercase px-3 py-1.5 rounded-lg transition-colors"
                  >
                    Upgrade
                  </button>
                </div>
              </div>

              <div className="h-8 w-px bg-zinc-800" />

              <div className="flex items-center gap-3 text-right">
                <div>
                  <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest leading-tight">Downloads</p>
                  <p className="text-sm font-black text-lime-400">{user.download_count || 0}</p>
                </div>
                <div className="w-10 h-10 rounded-full bg-lime-400/10 border border-lime-500/20 flex items-center justify-center text-lime-400">
                  <DownloadIcon className="w-5 h-5" />
                </div>
              </div>
            </div>
          </div>

        </div>
      )}

      {/* Upgrade / Donation Modal */}
      {showUpgradeModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
          <div className="bg-zinc-900 border border-zinc-800 rounded-[2rem] p-6 md:p-10 w-full max-w-5xl max-h-[90vh] overflow-y-auto shadow-2xl relative">
            <button
              onClick={() => setShowUpgradeModal(false)}
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
                                      userId: user.id
                                    });
                                    if (res.success) {
                                      alert(`Upgrade Successful! New Role: ${res.role}. Expiry extended.`);
                                      // Update Local User State
                                      const updatedUser = {
                                        ...user,
                                        role: res.role,
                                        expiry_date: res.expiry
                                      };
                                      setUser(updatedUser);
                                      localStorage.setItem('user', JSON.stringify(updatedUser)); // Persist
                                      setShowUpgradeModal(false);
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
            })()}        <div className="mt-8 text-center text-[10px] text-zinc-600 font-mono uppercase">
              Secure Payment via PayPal. Accounts are automatically created/upgraded.
            </div>
          </div>
        </div>
      )}

    </div>
  );
};

export default App;