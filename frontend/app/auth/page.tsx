'use client';
import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Scale, Mail, Lock, User, Loader2, ArrowRight, Eye, EyeOff } from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

export default function AuthPage() {
    const router = useRouter();
    const [mode, setMode] = useState<'signin' | 'signup'>('signin');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [fullName, setFullName] = useState('');
    const [gender, setGender] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [showPassword, setShowPassword] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        setLoading(true);

        try {
            const endpoint = mode === 'signup' ? '/auth/signup' : '/auth/signin';
            const body: Record<string, string> = { email, password };
            if (mode === 'signup') {
                body.full_name = fullName;
                if (gender) body.gender = gender;
            }

            const res = await fetch(`${API_BASE}${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });

            const data = await res.json();

            if (!res.ok) {
                setError(data.detail || 'Something went wrong');
                return;
            }

            // Store token + user info
            localStorage.setItem('auth_token', data.access_token);
            localStorage.setItem('auth_user', JSON.stringify(data.user));

            router.push('/');
        } catch {
            setError('Unable to connect to the server');
        } finally {
            setLoading(false);
        }
    };

    const toggleMode = () => {
        setMode(mode === 'signin' ? 'signup' : 'signin');
        setError(null);
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-[#ede8de] relative overflow-hidden">
            {/* Decorative background */}
            <div className="fixed inset-0 overflow-hidden pointer-events-none" style={{ zIndex: 0 }}>
                <div className="fixed -top-[10%] -right-[10%] w-[50%] h-[70%] rounded-full" style={{ background: '#74603e38', filter: 'blur(75px)' }} />
                <div className="fixed -bottom-[10%] right-[20%] w-[30%] h-[40%] rounded-full" style={{ background: '#d4812e2a', filter: 'blur(75px)' }} />
                <div className="fixed top-[30%] -left-[5%] w-[25%] h-[35%] rounded-full" style={{ background: '#74603e20', filter: 'blur(75px)' }} />
                <div className="fixed inset-0" style={{ opacity: 0.04, backgroundImage: 'radial-gradient(#000 1px, transparent 1px)', backgroundSize: '20px 20px' }} />
            </div>

            <div className="relative z-10 w-full max-w-md px-4">
                {/* Logo / branding */}
                <div className="text-center mb-8">
                    <div className="inline-flex p-4 bg-[#74603e]/10 rounded-2xl border border-[#c8b89a] mb-4 shadow-sm">
                        <Scale className="w-10 h-10 text-[#74603e]" />
                    </div>
                    <h1 className="text-2xl font-bold text-[#2d1f0e]">Family Law Assistant</h1>
                    <p className="text-sm text-[#8a7462] mt-1">AI-powered legal consultation</p>
                </div>

                {/* Card */}
                <div className="bg-white/90 backdrop-blur-md rounded-2xl border border-[#c8b89a] shadow-lg overflow-hidden">
                    {/* Tab strip */}
                    <div className="flex border-b border-[#c8b89a]">
                        <button
                            onClick={() => { setMode('signin'); setError(null); }}
                            className={`flex-1 py-3.5 text-sm font-semibold transition-colors ${mode === 'signin'
                                ? 'text-[#74603e] border-b-2 border-[#74603e] bg-[#f7f3ec]'
                                : 'text-[#8a7462] hover:text-[#74603e]'
                                }`}
                        >
                            Sign In
                        </button>
                        <button
                            onClick={() => { setMode('signup'); setError(null); }}
                            className={`flex-1 py-3.5 text-sm font-semibold transition-colors ${mode === 'signup'
                                ? 'text-[#74603e] border-b-2 border-[#74603e] bg-[#f7f3ec]'
                                : 'text-[#8a7462] hover:text-[#74603e]'
                                }`}
                        >
                            Sign Up
                        </button>
                    </div>

                    <form onSubmit={handleSubmit} className="p-6 space-y-4">
                        {error && (
                            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                                {error}
                            </div>
                        )}

                        {mode === 'signup' && (
                            <div>
                                <label className="block text-sm font-medium text-[#4a3728] mb-1.5">Full Name</label>
                                <div className="relative">
                                    <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#8a7462]" />
                                    <input
                                        type="text"
                                        value={fullName}
                                        onChange={e => setFullName(e.target.value)}
                                        required
                                        placeholder="Name"
                                        className="w-full pl-10 pr-4 py-2.5 bg-[#f7f3ec] border border-[#c8b89a] rounded-xl text-[#2d1f0e] placeholder-[#8a7462] focus:outline-none focus:ring-2 focus:ring-[#74603e]/40 focus:border-[#74603e] transition-colors text-sm"
                                    />
                                </div>
                            </div>
                        )}

                        {mode === 'signup' && (
                            <div>
                                <label className="block text-sm font-medium text-[#4a3728] mb-1.5">Gender</label>
                                <select
                                    value={gender}
                                    onChange={e => setGender(e.target.value)}
                                    className="w-full px-4 py-2.5 bg-[#f7f3ec] border border-[#c8b89a] rounded-xl text-[#2d1f0e] focus:outline-none focus:ring-2 focus:ring-[#74603e]/40 focus:border-[#74603e] transition-colors text-sm"
                                >
                                    <option value="">Select gender</option>
                                    <option value="male">Male</option>
                                    <option value="female">Female</option>
                                    <option value="other">Other</option>
                                </select>
                            </div>
                        )}

                        <div>
                            <label className="block text-sm font-medium text-[#4a3728] mb-1.5">Email</label>
                            <div className="relative">
                                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#8a7462]" />
                                <input
                                    type="email"
                                    value={email}
                                    onChange={e => setEmail(e.target.value)}
                                    required
                                    placeholder="you@example.com"
                                    className="w-full pl-10 pr-4 py-2.5 bg-[#f7f3ec] border border-[#c8b89a] rounded-xl text-[#2d1f0e] placeholder-[#8a7462] focus:outline-none focus:ring-2 focus:ring-[#74603e]/40 focus:border-[#74603e] transition-colors text-sm"
                                />
                            </div>
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-[#4a3728] mb-1.5">Password</label>
                            <div className="relative">
                                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#8a7462]" />
                                <input
                                    type={showPassword ? 'text' : 'password'}
                                    value={password}
                                    onChange={e => setPassword(e.target.value)}
                                    required
                                    minLength={6}
                                    placeholder="••••••••"
                                    className="w-full pl-10 pr-10 py-2.5 bg-[#f7f3ec] border border-[#c8b89a] rounded-xl text-[#2d1f0e] placeholder-[#8a7462] focus:outline-none focus:ring-2 focus:ring-[#74603e]/40 focus:border-[#74603e] transition-colors text-sm"
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowPassword(!showPassword)}
                                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[#8a7462] hover:text-[#74603e] transition-colors"
                                >
                                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                </button>
                            </div>
                        </div>

                        <button
                            type="submit"
                            disabled={loading}
                            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-amber-900 hover:bg-amber-800 text-white rounded-xl font-medium transition-colors shadow-sm disabled:opacity-50 text-sm"
                        >
                            {loading ? (
                                <><Loader2 className="w-4 h-4 animate-spin" /> Please wait…</>
                            ) : (
                                <>{mode === 'signin' ? 'Sign In' : 'Create Account'}<ArrowRight className="w-4 h-4" /></>
                            )}
                        </button>
                    </form>

                    {/* Footer toggle */}
                    <div className="px-6 pb-5 text-center">
                        <p className="text-sm text-[#8a7462]">
                            {mode === 'signin' ? "Don't have an account?" : 'Already have an account?'}{' '}
                            <button onClick={toggleMode} className="text-[#74603e] font-semibold hover:text-[#5c4b2f] transition-colors">
                                {mode === 'signin' ? 'Sign Up' : 'Sign In'}
                            </button>
                        </p>
                    </div>
                </div>

                <p className="text-center text-xs text-[#8a7462] mt-6">
                    AI-assisted legal guidance · Not a substitute for professional legal advice
                </p>
            </div>

            <style>{`
        @keyframes fade-in { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
        .relative.z-10 { animation: fade-in 0.4s ease-out; }
      `}</style>
        </div>
    );
}
