"use client";

import { useState, useEffect, useRef } from "react";
import UnifiedScanner from "@/components/Camera/UnifiedScanner";

// --- TIPE DATA ---
interface BackendResponse {
    success?: boolean;
    message?: string;
    data?: {
        transaksi_id?: string;
        mahasiswa?: {
            nama: string;
            nim: string;
        };
        peminjaman_detail?: Array<{
            nama_alat: string;
            kondisi: string;
        }>;
    };
}

interface TransactionData {
    nama?: string;
    nim?: string;
    alat?: string[];
    raw?: string;
}

export default function Home() {
    const [scannedData, setScannedData] = useState<TransactionData | null>(null); //simpan data hasil scan
    const [faceCount, setFaceCount] = useState(0); //simpan jumlah wajah terdeteksi
    const [currentTime, setCurrentTime] = useState<string>(""); //simpan waktu sekarang 

    const [isLoading, setIsLoading] = useState(false); //state loading pas verifikasi
    const [errorMessage, setErrorMessage] = useState<string | null>(null); //state pesan error
    const [scannerKey, setScannerKey] = useState(0); // Kunci buat refresh kamera

    const lastScanRef = useRef<number>(0); // CD biar ga spam scan

    useEffect(() => {
        const updateTime = () =>
            setCurrentTime(new Date().toLocaleTimeString("id-ID")); // update waktu setiap detik
        const timer = setInterval(updateTime, 1000); 
        return () => clearInterval(timer);
    }, []);

    const handleQrFound = async (qrString: string) => {
        const now = Date.now();
        // Cooldown 1.5 detik (biar ga spam scan)
        if (now - lastScanRef.current < 1500) return;
        lastScanRef.current = now;

        // Stop kalau lagi loading, ada data, atau lagi error
        if (scannedData || isLoading || errorMessage) return;

        setIsLoading(true); // mulai loading (muter muter)
        setErrorMessage(null);

        try {
            console.log("Mengirim QR ke Backend:", qrString);

            // Panggil API Backend
            const res = await fetch("http://localhost:5234/api/borrowing/scan-qr", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    qrCode: qrString,
                    scannerId: "desktop-scan-01",
                }),
            });

            const contentType = res.headers.get("content-type"); // Cek tipe konten kalo bukan JSON error
            if (!contentType || !contentType.includes("application/json")) {
                throw new Error(`Server Error: ${res.status}`);
            }

            const result = await res.json(); // baca response JSON

            if (res.ok) { //mapping datanya biar rapih masuk UI
                const dataFromApi = result.data || result;
                const fixedData: TransactionData = {
                    nama: dataFromApi.mahasiswa?.nama || dataFromApi.nama || "User Ditemukan",
                    nim: dataFromApi.mahasiswa?.nim || dataFromApi.nim || "-",
                    alat: dataFromApi.peminjaman_detail?.map((a: any) => a.nama_alat || a.nama) || [],
                    raw: qrString
                };
                
                setScannedData(fixedData); // simpan data ke state (UI berubah jadi tampil hasil)

            } else {
                // Backend nolak (misal: Transaksi tidak ditemukan / Pending)
                setErrorMessage(result.message || "QR Code tidak valid / Data tidak ditemukan.");
                // Hapus timeout otomatis, paksa user klik tombol "Coba Lagi" biar kamera refresh
            }

        } catch (err: any) {
            console.error("Error API:", err);
            setErrorMessage(err.message || "Gagal terhubung ke server.");
        } finally {
            setIsLoading(false);
        }
    };

    const handleFaceUpdate = (count: number) => { // Update jumlah wajah terdeteksi
        setFaceCount(count);
    };

    // Fungsi Reset Total (Dipanggil pas Selesai atau pas Error Retry)
    const resetScan = () => {
        setScannedData(null);
        setErrorMessage(null);
        lastScanRef.current = 0;
        // Refresh kamera biar mau baca QR yg sama lagi
        setScannerKey(prev => prev + 1);
    };

    return (
        <div className="flex h-screen w-full flex-col overflow-hidden bg-[#0d1b2a] font-sans text-white">
            <Header currentTime={currentTime} />

            <main className="grid flex-1 grid-cols-12 gap-6 p-6">
                <div className="col-span-12 flex h-full flex-col gap-4 lg:col-span-8">
                    <ScannerSection
                        key={scannerKey} // Kunci Reset Kamera
                        faceCount={faceCount}
                        onQrScan={handleQrFound}
                        onFaceDetect={handleFaceUpdate}
                        isLoading={isLoading}
                        errorMessage={errorMessage}
                        onRetry={resetScan} 
                    />
                </div>

                <div className="col-span-12 h-full lg:col-span-4">
                    <InfoPanel scannedData={scannedData} onReset={resetScan} isLoading={isLoading} />
                </div>
            </main>
        </div>
    );
}

// --- SUB COMPONENTS ---

    function Header({ currentTime }: { currentTime: string }) {
        return (
            <header className="z-10 flex h-16 items-center justify-between border-b border-gray-800 bg-[#162032]/50 px-8 backdrop-blur-md">
                <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-500 font-bold text-[#0d1b2a]">S</div>
                    <div>
                        <h1 className="leading-none text-lg font-bold tracking-wider text-cyan-400">SIMPEL</h1>
                        <p className="text-[10px] text-gray-400">Made By Kelompok 8 - TRPL</p>
                    </div>
                </div>
                <div className="w-32 text-center font-mono text-2xl font-bold text-white">{currentTime || "--:--:--"}</div>
            </header>
        );
    }

    function ScannerSection({
        faceCount,
        onQrScan,
        onFaceDetect,
        isLoading,
        errorMessage,
        onRetry 
    }: {
        faceCount: number;
        onQrScan: (data: string) => void;
        onFaceDetect: (count: number) => void;
        isLoading: boolean;
        errorMessage: string | null;
        onRetry: () => void; 
    }) {
    return (
        <div className={`relative flex-1 overflow-hidden rounded-3xl border-2 transition-all ${errorMessage ? 'border-red-500' : 'border-gray-700'} bg-black shadow-2xl shadow-cyan-900/10`}>
            <div className="absolute inset-0">
                <UnifiedScanner onQrScan={onQrScan} onFaceDetect={onFaceDetect} />
            </div>

            {/* OVERLAY LOADING */}
            {isLoading && (
                <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-black/80 backdrop-blur-sm">
                    <div className="h-12 w-12 animate-spin rounded-full border-4 border-cyan-500 border-t-transparent"></div>
                    <p className="mt-4 animate-pulse font-bold text-cyan-400">MEMVERIFIKASI DATA...</p>
                </div>
            )}

            {/* OVERLAY ERROR (DENGAN TOMBOL RETRY) */}
            {errorMessage && (
                <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-black/90 backdrop-blur-md animate-in fade-in space-y-4">
                    <p className="font-bold text-red-500 text-xl text-center px-6 max-w-md">{errorMessage}</p>

                    <button
                        onClick={onRetry}
                        className="mt-4 px-6 py-3 bg-red-600 hover:bg-red-700 text-white rounded-xl font-bold transition-all transform hover:scale-105 active:scale-95 shadow-lg shadow-red-900/50"
                    >
                        ↻ SCAN ULANG
                    </button>
                </div>
            )}

            <div className="absolute left-4 top-4 flex items-center gap-3 rounded-full border border-white/10 bg-black/60 px-4 py-2 backdrop-blur-sm">
                <div className={`h-3 w-3 rounded-full transition-colors ${faceCount > 0 ? "bg-green-500 shadow-[0_0_10px_#22c55e]" : "bg-red-500"}`}></div>
                <span className="text-xs font-bold tracking-wide">
                    {faceCount > 0 ? `${faceCount} WAJAH TERDETEKSI` : "MENCARI WAJAH..."}
                </span>
            </div>
        </div>
    );
}

function InfoPanel({
    scannedData,
    onReset,
    isLoading
}: {
    scannedData: TransactionData | null;
    onReset: () => void;
    isLoading: boolean;
}) {
    return (
        <div className="relative flex h-full flex-col overflow-hidden rounded-3xl border border-gray-700 bg-[#162032]">
            {!scannedData ? (
                <WaitingState isLoading={isLoading} />
            ) : (
                <ResultState data={scannedData} onReset={onReset} />
            )}
        </div>
    );
}

function WaitingState({ isLoading }: { isLoading: boolean }) {
    return (
        <div className="flex flex-1 flex-col items-center justify-center space-y-6 p-8 text-center">
            {isLoading ? (
                <>
                    <div className="flex h-40 w-40 animate-spin items-center justify-center rounded-full border-4 border-cyan-500 border-t-transparent"></div>
                    <div>
                        <h2 className="mb-2 text-xl font-bold text-white">Sedang Memproses...</h2>
                        <p className="text-sm text-gray-400">Menghubungi server...</p>
                    </div>
                </>
            ) : (
                <>
                    <div className="flex h-40 w-40 animate-spin-slow items-center justify-center rounded-full border-4 border-dashed border-gray-600">
                        <span className="animate-pulse text-4xl">📷</span>
                    </div>
                    <div>
                        <h2 className="mb-2 text-xl font-bold text-white">Menunggu Scan...</h2>
                        <p className="text-sm text-gray-400">
                            Silakan scan QR Code pada aplikasi mobile mahasiswa.
                        </p>
                    </div>
                </>
            )}
        </div>
    );
}

function ResultState({ data, onReset }: { data: TransactionData; onReset: () => void; }) {
    return (
        <div className="animate-in slide-in-from-right flex flex-1 flex-col duration-300">
            <div className="border-b border-white/10 bg-gradient-to-r from-cyan-900/50 to-blue-900/50 p-6">
                <p className="mb-1 text-[10px] font-bold uppercase tracking-widest text-cyan-300">DATA PEMINJAM</p>
                <h2 className="text-2xl font-bold leading-tight text-white">{data.nama}</h2>
                <p className="mt-1 font-mono text-sm text-gray-300">{data.nim}</p>
            </div>

            <div className="custom-scrollbar flex flex-1 flex-col overflow-y-auto p-6">
                <div className="sticky top-0 z-10 mb-4 flex items-center justify-between bg-[#162032] py-2">
                    <p className="text-xs font-bold uppercase tracking-wider text-gray-500">DAFTAR ALAT ({data.alat?.length || 0})</p>
                </div>
                <div className="space-y-3">
                    {data.alat && data.alat.length > 0 ? (
                        data.alat.map((item, i) => (
                            <div key={i} className="flex items-center gap-3 rounded-xl border border-gray-700/50 bg-[#0d1b2a] p-4">
                                <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-indigo-500/20 bg-indigo-500/10 text-lg text-indigo-400">📦</div>
                                <span className="block text-sm font-medium text-gray-200">{item}</span>
                            </div>
                        ))
                    ) : (
                        <p className="text-sm text-gray-400 text-center">Tidak ada detail alat.</p>
                    )}
                </div>
            </div>

            <div className="border-t border-gray-800 bg-[#0d1b2a] p-6">
                <button onClick={onReset} className="w-full rounded-xl bg-gray-800 py-4 font-bold text-gray-300 hover:bg-gray-700">SELESAI</button>
            </div>
        </div>
    );
}