"use client";

import { useState, useEffect } from "react";
// Import scanner hybrid kita yang baru
import UnifiedScanner from "@/components/Camera/UnifiedScanner";

export default function Home() {
    const [qrResult, setQrResult] = useState<string | null>(null);
    const [faceCount, setFaceCount] = useState(0);
    const [currentTime, setCurrentTime] = useState<string>("");

    // Effect buat jalanin jam real-time
    useEffect(() => {
        // Fungsi helper buat update jam
        const updateTime = () => setCurrentTime(new Date().toLocaleTimeString());

        //  Jgn panggil langsung, tapi bungkus setTimeout biar gak blocking
        const initialTimeout = setTimeout(updateTime, 0);

        // Update tiap detik
        const timer = setInterval(updateTime, 1000);

        return () => {
            clearTimeout(initialTimeout);
            clearInterval(timer);
        };
    }, []);

    const handleQrFound = (data: string) => {
        console.log("QR Ditemukan:", data);
        setQrResult(data);
    };

    const handleFaceUpdate = (count: number) => {
        setFaceCount(count);
    };

    const resetScan = () => {
        setQrResult(null);
    };

    return (
        <div className="min-h-screen bg-[#0d1b2a] flex flex-col items-center justify-center p-6 text-white font-sans overflow-hidden">

            {/* Header Keren */}
            <div className="w-full max-w-md flex justify-between items-center mb-8">
                <div>
                    <h1 className="text-2xl font-bold text-cyan-400 tracking-tighter">LAB EQUIPMENT</h1>
                    <p className="text-xs text-gray-400">Made By Kel 8 - RPL</p>
                </div>
                <div className="flex flex-col items-end">
                    <span className="text-xs text-green-400 font-mono animate-pulse">● SYSTEM ACTIVE</span>
                    {/* FIX: Render state currentTime di sini */}
                    <span className="text-[10px] text-gray-500 font-mono">
                        {currentTime || "--:--:--"}
                    </span>
                </div>
            </div>

            {/* Main Scanner Card */}
            <div className="relative w-full max-w-md aspect-[3/4] bg-[#162032] rounded-3xl shadow-2xl border border-gray-700 p-2 flex flex-col">

                {/* Layar Kamera (Full Height) */}
                <div className="flex-1 relative rounded-2xl overflow-hidden bg-black">
                    {!qrResult ? (
                        <UnifiedScanner
                            onQrScan={handleQrFound}
                            onFaceDetect={handleFaceUpdate}
                        />
                    ) : (
                        // Tampilan Sukses
                        <div className="absolute inset-0 bg-[#0d1b2a] flex flex-col items-center justify-center p-6 animate-in zoom-in duration-300">
                            <div className="w-20 h-20 bg-green-500/20 rounded-full flex items-center justify-center mb-4">
                                <span className="text-4xl">🔓</span>
                            </div>
                            <h2 className="text-xl font-bold text-white mb-1">Access Granted</h2>
                            <p className="text-sm text-gray-400 mb-6">Identitas Terverifikasi</p>

                            <div className="w-full bg-black/30 p-4 rounded-xl border border-gray-700 mb-6 break-all">
                                <p className="text-[10px] text-gray-500 uppercase mb-1">Hasil QR :</p>
                                <p className="font-mono text-green-400 text-sm">{qrResult}</p>
                            </div>
                            
                            <button
                                onClick={resetScan}
                                className="w-full py-3 bg-cyan-600 hover:bg-cyan-500 text-white font-bold rounded-xl transition-all shadow-lg shadow-cyan-500/20"
                            >
                                SCAN LAGI
                            </button>
                        </div>
                    )}
                </div>

                {/* Status Bar di Bawah */}
                {!qrResult && (
                    <div className="h-16 flex items-center justify-between px-4">
                        <div className="flex items-center space-x-3">
                            <div className={`w-2 h-2 rounded-full transition-colors duration-300 ${faceCount > 0 ? 'bg-green-500 shadow-[0_0_10px_#22c55e]' : 'bg-red-500'}`}></div>
                            <div>
                                <p className="text-xs font-bold text-gray-300">Face Sensor</p>
                                <p className="text-[10px] text-gray-500">
                                    {faceCount > 0 ? `${faceCount} Wajah Terdeteksi` : "Mencari Wajah..."}
                                </p>
                            </div>
                        </div>

                        <div className="w-px h-8 bg-gray-700"></div>

                        <div className="text-right">
                            <p className="text-xs font-bold text-gray-300">QR Sensor</p>
                            <p className="text-[10px] text-gray-500 text-cyan-400 animate-pulse">Scanning Active...</p>
                        </div>
                    </div>
                )}
            </div>

            <p className="mt-6 text-[10px] text-gray-600 max-w-xs text-center">
                Pastikan wajah terlihat jelas dan kode QR memiliki pencahayaan yang cukup.
            </p>
        </div>
    );
}