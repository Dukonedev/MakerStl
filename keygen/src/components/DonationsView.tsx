import React, { useEffect, useState } from 'react';
import { PayPalScriptProvider, PayPalButtons } from "@paypal/react-paypal-js";
import { api } from '../api';

export const DonationsView: React.FC = () => {
    const [settings, setSettings] = useState<any>({});
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        api.settings.getPublic().then(res => {
            if (res.success) setSettings(res.settings || {});
            setLoading(false);
        }).catch(e => {
            console.error(e);
            setLoading(false);
        });
    }, []);

    if (loading) return <div className="min-h-screen bg-black flex items-center justify-center text-lime-400 font-mono animate-pulse">LOADING_DATA...</div>;

    return (
        <div className="min-h-screen bg-black flex flex-col items-center justify-center p-4 md:p-8 relative cyber-bg overflow-y-auto">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_-20%,#1a2e05_0%,transparent_50%)] pointer-events-none opacity-50" />

            <div className="w-full max-w-6xl z-10">
                <div className="text-center mb-12">
                    <h1 className="text-4xl md:text-6xl font-black text-lime-400 mb-4 uppercase italic tracking-tighter drop-shadow-[0_0_15px_rgba(163,230,53,0.5)]">
                        Support The Project
                    </h1>
                    <p className="text-zinc-500 text-sm md:text-base font-mono uppercase tracking-widest max-w-2xl mx-auto">
                        Help us build the ultimate 3D Keygen Generator. <br />
                        Your contribution unlocks advanced features and servers.
                    </p>
                </div>

                {(() => {
                    const hasPayPal = !!settings.paypal_client_id;

                    const tiersGrid = (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                            {[1, 2, 3, 4].map(tier => {
                                const title = settings[`donation_tier${tier}_title`] || `Tier ${tier}`;
                                const desc = settings[`donation_tier${tier}_desc`] || 'Support us!';
                                const originalPriceLabel = settings[`donation_tier${tier}_price`] || 'N/A';
                                const originalAmount = settings[`donation_tier${tier}_amount`];

                                const discountLabel = settings[`donation_tier${tier}_discount_label`];
                                const discountAmount = settings[`donation_tier${tier}_discount_amount`];

                                const hasDiscount = discountAmount && parseFloat(discountAmount) > 0;
                                const finalAmount = hasDiscount ? discountAmount : originalAmount;

                                const theme = tier === 1 ? 'zinc' : tier === 2 ? 'blue' : tier === 3 ? 'emerald' : 'purple';
                                const themeColor = tier === 1 ? 'text-zinc-400' : tier === 2 ? 'text-blue-400' : tier === 3 ? 'text-emerald-400' : 'text-purple-400';
                                const themeBorder = tier === 1 ? 'border-zinc-700' : tier === 2 ? 'border-blue-500/30' : tier === 3 ? 'border-emerald-500/30' : 'border-purple-500/30';
                                const themeBg = tier === 1 ? 'bg-zinc-800/50' : tier === 2 ? 'bg-blue-500/10' : tier === 3 ? 'bg-emerald-500/10' : 'bg-purple-500/10';

                                return (
                                    <div key={tier} className={`flex flex-col p-6 rounded-2xl border ${themeBorder} ${themeBg} relative overflow-hidden transition-all hover:scale-[1.02] backdrop-blur-sm`}>
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

                                        <div className="relative z-10 block min-h-[40px] mt-auto">
                                            {finalAmount && parseFloat(finalAmount) > 0 && hasPayPal ? (
                                                <PayPalButtons
                                                    style={{ layout: "horizontal", color: "blue", height: 40, tagline: false }}
                                                    createOrder={(data, actions) => {
                                                        return actions.order.create({
                                                            intent: "CAPTURE",
                                                            purchase_units: [{
                                                                description: `${title} Donation`,
                                                                amount: { value: finalAmount, currency_code: "EUR" }
                                                            }]
                                                        });
                                                    }}
                                                    onApprove={async (data, actions) => {
                                                        return actions.order!.capture().then(async () => {
                                                            alert("Thank you for your donation! If you have an account, please log in to see your status update.");
                                                        });
                                                    }}
                                                />
                                            ) : (
                                                <a
                                                    href={settings[`donation_tier${tier}_url`] || 'https://paypal.me/virtuprinto'}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className={`block w-full py-3 rounded-xl font-bold text-xs uppercase tracking-widest text-center transition-all bg-zinc-700 hover:bg-zinc-600 text-white`}
                                                >
                                                    {hasPayPal ? 'Free Donation' : 'Donate'}
                                                </a>
                                            )}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    );

                    return hasPayPal ? (
                        <PayPalScriptProvider options={{ "clientId": settings.paypal_client_id, currency: "EUR" }}>
                            {tiersGrid}
                        </PayPalScriptProvider>
                    ) : (
                        tiersGrid
                    );
                })()}

                <div className="mt-12 text-center">
                    <a href="/" className="inline-block text-zinc-500 hover:text-white text-xs font-mono uppercase tracking-widest border-b border-zinc-700 hover:border-white transition-colors pb-1">Back to App</a>
                </div>
            </div>
        </div>
    );
};
