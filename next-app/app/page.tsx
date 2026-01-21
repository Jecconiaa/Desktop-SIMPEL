// next-app/app/page.tsx (FINAL VERSION)
"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import UnifiedScanner from "@/components/Camera/UnifiedScanner";
import { Toast } from "@/components/Toast";
import { API_LINK } from "@/lib/constant";


// --- TIPE DATA ---
interface ScanResponse {
    success?: boolean;
    message?: string;
    warning?: string;
    data?: {
        id?: number;
        mhsId?: number;
        qrCode?: string;
        oldStatus?: string;
        newStatus?: string;
        semuaAlatHabis?: boolean;
        alatHabisList?: string[];
        alatBerhasil?: number;
        alatGagal?: number;
        borrowedAt?: string;
        returnedAt?: string | null;
        timestamp?: string;
    };
}

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
            quantity?: number;
            EquipmentName?: string;
            Quantity?: number;
        }>;
    };
}

interface TransactionData {
    nama?: string;
    nim?: string;
    alat?: string[];
    raw?: string;
    semuaAlatHabis?: boolean;
    warning?: string;
    mhsId?: number;
}

export default function Home() {
    const [scannedData, setScannedData] = useState<TransactionData | null>(null);
    const [faceCount, setFaceCount] = useState(0);
    const [currentTime, setCurrentTime] = useState<string>("");
    const [isLoading, setIsLoading] = useState(false);
    const [isLoadingStep2, setIsLoadingStep2] = useState(false);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [scannerKey, setScannerKey] = useState(0);
    const [autoResetTimer, setAutoResetTimer] = useState<NodeJS.Timeout | null>(null);

    // ⭐ STATE TOAST
    const [toast, setToast] = useState<{
        message: string;
        type: 'success' | 'error' | 'info' | 'warning';
    } | null>(null);

    const lastScanRef = useRef<number>(0);

    // ⭐ FUNGSI SHOW TOAST
    const showToast = useCallback((message: string, type: 'success' | 'error' | 'info' | 'warning' = 'info') => {
        setToast({ message, type });
        setTimeout(() => setToast(null), 3000);
    }, []);

    // ⭐ FUNGSI PLAY SOUND (OPTIONAL)
    const playSound = useCallback((type: 'success' | 'error' | 'warning') => {
        try {
            const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();

            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);

            // Frekuensi berbeda untuk tiap sound
            switch (type) {
                case 'success':
                    oscillator.frequency.setValueAtTime(800, audioContext.currentTime);
                    break;
                case 'warning':
                    oscillator.frequency.setValueAtTime(600, audioContext.currentTime);
                    break;
                case 'error':
                    oscillator.frequency.setValueAtTime(400, audioContext.currentTime);
                    break;
            }

            gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);

            oscillator.start();
            oscillator.stop(audioContext.currentTime + 0.5);
        } catch (e) {
            console.log("Sound not supported:", e);
        }
    }, []);

    // ⭐ AUTO RESET SETELAH 10 DETIK
    useEffect(() => {
        if (scannedData && !isLoading && !errorMessage) {
            // Clear timer sebelumnya
            if (autoResetTimer) clearTimeout(autoResetTimer);

            // Set timer baru
            const timer = setTimeout(() => {
                resetScan();
                showToast("Auto-reset untuk scan berikutnya", "info");
            }, 10000); // 10 detik

            setAutoResetTimer(timer);

            return () => {
                if (timer) clearTimeout(timer);
            };
        }
    }, [scannedData, isLoading, errorMessage]);

    // ⭐ UPDATE WAKTU
    useEffect(() => {
        const updateTime = () =>
            setCurrentTime(new Date().toLocaleTimeString("id-ID"));
        const timer = setInterval(updateTime, 1000);
        return () => clearInterval(timer);
    }, []);

    // ⭐ HANDLE QR SCAN (MAIN LOGIC)
    const handleQrFound = useCallback(async (qrString: string) => {
        const now = Date.now();
        if (now - lastScanRef.current < 2000) { // ⭐ 2 DETIK DEBOUNCE
            console.log("⏳ Skip scan - terlalu cepat");
            return;
        }
        lastScanRef.current = now;

        if (scannedData || isLoading || errorMessage) return;

        setIsLoading(true);
        setErrorMessage(null);
        setScannedData(null);

        try {
            console.log("🔵 [STEP 1] Mengirim QR untuk update status...");

            // ⭐ 1. POST untuk update status
            const scanRes = await fetch(
                `${API_LINK}borrowing/scan-qr/${encodeURIComponent(qrString)}`,
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                }
            );

            const scanResult: ScanResponse = await scanRes.json();
            console.log("🔵 [STEP 1 Result]:", scanResult);

            // ⭐ VALIDASI RESPONSE
            if (!scanResult) {
                throw new Error("Invalid response from server");
            }

            if (!scanResult.data) {
                throw new Error("Invalid response format from server");
            }

            if (!scanResult.data.newStatus) {
                console.warn("⚠️ Server tidak mengembalikan newStatus");
            }

            if (!scanRes.ok || !scanResult.success) {
                throw new Error(scanResult.message || `Gagal scan QR. Status: ${scanRes.status}`);
            }

            // ⭐ CEK APAKAH ALAT HABIS
            if (scanResult.data.semuaAlatHabis) {
                // KASUS: SEMUA ALAT HABIS
                playSound('error');
                showToast("⚠️ Semua alat habis! Booking selesai.", "error");

                const alatArray = scanResult.data.alatHabisList || [];
                const fixedData: TransactionData = {
                    nama: `Mahasiswa ID: ${scanResult.data.mhsId}`,
                    nim: scanResult.data.mhsId?.toString() || "-",
                    alat: alatArray,
                    raw: qrString,
                    semuaAlatHabis: true,
                    mhsId: scanResult.data.mhsId
                };

                setScannedData(fixedData);

                setErrorMessage(
                    `❌ SEMUA ALAT HABIS!\n\n` +
                    `Mahasiswa: ${scanResult.data.mhsId}\n` +
                    `Alat yang habis:\n${alatArray.join(", ")}\n\n` +
                    `Status: ${scanResult.data.newStatus}`
                );

                setIsLoading(false);
                return;
            }

            // ⭐ TOAST SUCCESS - NORMAL CASE
            const alatGagal = scanResult.data?.alatGagal || 0; // ⬅️ AMAN
            if (alatGagal > 0) {
                showToast(`✅ Scan berhasil! ${alatGagal} alat habis`, "info");
            } else {
                // SEMUA ALAT BERHASIL
                playSound('success');
                showToast("✅ QR Berhasil di-Scan!", "success");
            }

            console.log("✅ [STEP 1 Success] Status berubah:", scanResult.data.newStatus);

            // ⭐ 2. GET data untuk ditampilkan
            console.log("🔵 [STEP 2] Mengambil data transaksi...");
            setIsLoadingStep2(true);

            const dataRes = await fetch(
                `${API_LINK}borrowing/scan-data/${encodeURIComponent(qrString)}`,
                {
                    method: "GET",
                    headers: {
                        "Accept": "application/json",
                    },
                }
            );

            const contentType = dataRes.headers.get("content-type");
            if (!contentType || !contentType.includes("application/json")) {
                throw new Error(`Server Error: ${dataRes.status}`);
            }

            const dataResult: BackendResponse = await dataRes.json();
            console.log("🔵 [STEP 2 Result]:", dataResult);

            if (dataRes.ok && dataResult.success) {
                // ⭐ OPTIMASI GROUPING ALAT DENGAN REDUCE
                let alatArray: string[] = [];

                if (dataResult.data?.peminjaman_detail) {
                    const alatMap = dataResult.data.peminjaman_detail.reduce((acc: Record<string, number>, item) => {
                        const nama = item.nama_alat || item.EquipmentName;
                        const qty = item.quantity || item.Quantity || 1;

                        if (nama) {
                            acc[nama] = (acc[nama] || 0) + qty;
                        }
                        return acc;
                    }, {});

                    alatArray = Object.entries(alatMap).map(([nama, qty]) =>
                        qty > 1 ? `${nama} (${qty}x)` : nama
                    );
                }

                // ⭐ TAMBAHKAN INFO ALAT HABIS JIKA ADA
                if (scanResult.data.alatHabisList && scanResult.data.alatHabisList.length > 0) {
                    const habisItems = scanResult.data.alatHabisList.map((alat: string) => `❌ ${alat} (HABIS)`);
                    alatArray = [...alatArray, ...habisItems];
                }

                const fixedData: TransactionData = {
                    nama: dataResult.data?.mahasiswa?.nama || `Mahasiswa ${scanResult.data.mhsId}`,
                    nim: dataResult.data?.mahasiswa?.nim || scanResult.data.mhsId?.toString() || "-",
                    alat: alatArray,
                    raw: qrString,
                    semuaAlatHabis: scanResult.data.semuaAlatHabis,
                    mhsId: scanResult.data.mhsId
                };

                console.log("✅ [STEP 2 Success] Data untuk UI:", fixedData);
                setScannedData(fixedData);

            } else {
                throw new Error(dataResult.message || "Data tidak ditemukan setelah scan");
            }

        } catch (err: any) {
            console.error("❌ Error total:", err);

            let errorMsg = err.message || "Gagal terhubung ke server";
            let toastType: 'error' | 'warning' = 'error';

            if (errorMsg.includes("Booked")) {
                errorMsg = `❌ Hanya booking dengan status "Booked" yang bisa di-scan.\n${errorMsg}`;
                toastType = 'warning';
            } else if (errorMsg.includes("404") || errorMsg.includes("tidak ditemukan")) {
                errorMsg = "❌ QR Code tidak ditemukan. Pastikan booking sudah dibuat di mobile app.";
            } else if (errorMsg.includes("500")) {
                errorMsg = "❌ Server error. Hubungi administrator.";
            } else if (errorMsg.includes("expired")) {
                errorMsg = "❌ QR Code sudah expired. Booking otomatis dibatalkan.";
            }

            playSound('error');
            showToast(errorMsg.split('\n')[0], toastType);
            setErrorMessage(errorMsg);

        } finally {
            setIsLoading(false);
            setIsLoadingStep2(false);
        }
    }, [scannedData, isLoading, errorMessage, showToast, playSound]);

    const handleFaceUpdate = useCallback((count: number) => {
        setFaceCount(count);
    }, []);

    const resetScan = useCallback(() => {
        setScannedData(null);
        setErrorMessage(null);
        setIsLoadingStep2(false);
        lastScanRef.current = 0;

        if (autoResetTimer) {
            clearTimeout(autoResetTimer);
            setAutoResetTimer(null);
        }

        setScannerKey(prev => prev + 1);
    }, [autoResetTimer]);

    return (
        <div className="flex h-screen w-full flex-col overflow-hidden bg-[#0d1b2a] font-sans text-white">
            {/* ⭐ RENDER TOAST */}
            {toast && (
                <Toast
                    message={toast.message}
                    type={toast.type}
                    onClose={() => setToast(null)}
                />
            )}

            <Header currentTime={currentTime} />

            <main className="grid grid-cols-12 gap-6 p-6 h-[calc(100vh-4rem)]">
                <div className="col-span-12 flex h-full min-h-0 flex-col gap-4 lg:col-span-8">
                    <ScannerSection
                        key={scannerKey}
                        faceCount={faceCount}
                        onQrScan={handleQrFound}
                        onFaceDetect={handleFaceUpdate}
                        isLoading={isLoading}
                        errorMessage={errorMessage}
                        onRetry={resetScan}
                        isLoadingStep2={isLoadingStep2} // ⭐ PASS LOADING STEP 2
                    />
                </div>

                <div className="col-span-12 h-full min-h-0 lg:col-span-4">
                    <InfoPanel
                        scannedData={scannedData}
                        onReset={resetScan}
                        isLoading={isLoading}
                        isLoadingStep2={isLoadingStep2} // ⭐ PASS KE INFOPANEL
                    />
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
            <div className="w-32 text-center font-mono text-2xl font-bold text-white">
                {currentTime || "--:--:--"}
            </div>
        </header>
    );
}

function ScannerSection({
    faceCount,
    onQrScan,
    onFaceDetect,
    isLoading,
    isLoadingStep2,
    errorMessage,
    onRetry
}: {
    faceCount: number;
    onQrScan: (data: string) => void;
    onFaceDetect: (count: number) => void;
    isLoading: boolean;
    isLoadingStep2: boolean; // ⭐ PROPS BARU
    errorMessage: string | null;
    onRetry: () => void;
}) {
    return (
        <div className={`relative flex-1 overflow-hidden rounded-3xl border-2 transition-all ${errorMessage ? 'border-red-500' : 'border-gray-700'} bg-black shadow-2xl shadow-cyan-900/10`}>
            <div className="absolute inset-0">
                <UnifiedScanner
                    onQrScan={onQrScan}
                    onFaceDetect={onFaceDetect}
                />
            </div>

            {/* OVERLAY LOADING STEP 1 */}
            {isLoading && !isLoadingStep2 && (
                <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-black/80 backdrop-blur-sm">
                    <div className="h-12 w-12 animate-spin rounded-full border-4 border-cyan-500 border-t-transparent"></div>
                    <p className="mt-4 animate-pulse font-bold text-cyan-400">MEMVERIFIKASI QR...</p>
                </div>
            )}

            {/* OVERLAY LOADING STEP 2 */}
            {isLoadingStep2 && (
                <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-black/80 backdrop-blur-sm">
                    <div className="h-10 w-10 animate-spin rounded-full border-4 border-blue-500 border-t-transparent"></div>
                    <p className="mt-4 animate-pulse font-bold text-blue-400">MENGAMBIL DATA...</p>
                </div>
            )}

            {/* OVERLAY ERROR */}
            {errorMessage && !isLoading && !isLoadingStep2 && (
                <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-black/90 backdrop-blur-md animate-in fade-in space-y-4">
                    <div className={`text-6xl mb-2 ${errorMessage.includes('HABIS') ? 'text-orange-500' : 'text-red-500'}`}>
                        {errorMessage.includes('HABIS') ? '⚠️' : '❌'}
                    </div>

                    <div className="max-w-md text-center">
                        <h3 className="font-bold text-xl mb-2">
                            {errorMessage.includes('HABIS') ? 'ALAT HABIS' : 'SCAN GAGAL'}
                        </h3>
                        <p className="text-gray-300 whitespace-pre-line text-sm">
                            {errorMessage}
                        </p>
                    </div>

                    <button
                        onClick={onRetry}
                        className={`mt-4 px-6 py-3 rounded-xl font-bold transition-all transform hover:scale-105 active:scale-95 shadow-lg ${errorMessage.includes('HABIS')
                            ? 'bg-orange-600 hover:bg-orange-700 shadow-orange-900/50'
                            : 'bg-red-600 hover:bg-red-700 shadow-red-900/50'
                            }`}
                    >
                        {errorMessage.includes('HABIS') ? 'OK, LANJUT SCAN' : '↻ SCAN ULANG'}
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
    isLoading,
    isLoadingStep2
}: {
    scannedData: TransactionData | null;
    onReset: () => void;
    isLoading: boolean;
    isLoadingStep2: boolean;
}) {
    return (
        <div className="relative flex h-full flex-col rounded-3xl border border-gray-700 bg-[#162032] overflow-hidden">
            {!scannedData ? (
                <WaitingState isLoading={isLoading} isLoadingStep2={isLoadingStep2} />
            ) : (
                <ResultState data={scannedData} onReset={onReset} />
            )}
        </div>
    );
}

function WaitingState({ isLoading, isLoadingStep2 }: { isLoading: boolean; isLoadingStep2: boolean }) {
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
            ) : isLoadingStep2 ? (
                <>
                    <div className="flex h-40 w-40 animate-spin items-center justify-center rounded-full border-4 border-blue-500 border-t-transparent"></div>
                    <div>
                        <h2 className="mb-2 text-xl font-bold text-white">Mengambil Data...</h2>
                        <p className="text-sm text-gray-400">Mengambil detail transaksi...</p>
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
    const hasAlatHabis = data.alat?.some(item => item.includes("(HABIS)")) || data.semuaAlatHabis;

    return (
        <div className="flex flex-col h-full">
            {/* HEADER */}
            <div className={`shrink-0 border-b border-white/10 p-6 ${hasAlatHabis ? 'bg-gradient-to-r from-orange-900/50 to-red-900/50' : 'bg-gradient-to-r from-cyan-900/50 to-blue-900/50'}`}>
                <div className="flex items-center justify-between mb-2">
                    <div>
                        <p className="mb-1 text-[10px] font-bold uppercase tracking-widest text-gray-300">
                            DATA PEMINJAM
                        </p>
                        <h2 className="text-2xl font-bold leading-tight text-white">{data.nama}</h2>
                        <p className="mt-1 font-mono text-sm text-gray-300">{data.nim}</p>
                    </div>
                    <div className={`rounded-full px-3 py-1 ${hasAlatHabis ? 'bg-red-500/20' : 'bg-green-500/20'}`}>
                        <span className={`text-xs font-bold ${hasAlatHabis ? 'text-red-400' : 'text-green-400'}`}>
                            {hasAlatHabis ? 'SELESAI' : 'DIPROSES'}
                        </span>
                    </div>
                </div>

                <div className={`mt-3 rounded-lg p-2 ${hasAlatHabis ? 'bg-red-900/30' : 'bg-green-900/30'}`}>
                    <p className={`text-xs ${hasAlatHabis ? 'text-red-300' : 'text-green-300'}`}>
                        {hasAlatHabis
                            ? (data.semuaAlatHabis ? '⚠️ Semua alat habis. Booking selesai.' : '⚠️ Beberapa alat habis.')
                            : '✅ Status berhasil diupdate: Booked → Diproses'}
                    </p>
                </div>
            </div>

            {/* MIDDLE SECTION */}
            <div className="flex-1 overflow-y-auto">
                <div className="sticky top-0 z-10 px-6 pt-4 pb-2 border-b border-gray-800 bg-[#162032]">
                    <p className="text-xs font-bold uppercase tracking-wider text-gray-500">
                        DAFTAR ALAT ({data.alat?.length || 0})
                    </p>
                </div>

                {/* LIST ALAT */}
                <div className="px-6 py-4">
                    <div className="space-y-3">
                        {data.alat && data.alat.length > 0 ? (
                            data.alat.map((item, i) => {
                                const isHabis = item.includes("(HABIS)");

                                return (
                                    <div
                                        key={i}
                                        className={`flex items-start gap-3 rounded-xl border p-4 ${isHabis
                                            ? 'border-red-700/50 bg-red-900/10'
                                            : 'border-gray-700/50 bg-[#0d1b2a]'
                                            }`}
                                    >
                                        <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border mt-0.5 ${isHabis
                                            ? 'border-red-500/20 bg-red-500/10 text-red-400'
                                            : 'border-indigo-500/20 bg-indigo-500/10 text-indigo-400'
                                            }`}>
                                            {isHabis ? '❌' : '📦'}
                                        </div>
                                        <span className={`block text-sm font-medium break-words flex-1 ${isHabis ? 'text-red-300' : 'text-gray-200'
                                            }`}>
                                            {item}
                                        </span>
                                    </div>
                                );
                            })
                        ) : (
                            <p className="text-sm text-gray-400 text-center py-8">Tidak ada detail alat.</p>
                        )}
                    </div>
                </div>
            </div>

            {/* FOOTER */}
            <div className="shrink-0 border-t border-gray-800 bg-[#0d1b2a] p-6">
                <button
                    onClick={onReset}
                    className="w-full rounded-xl bg-gray-800 py-4 font-bold text-gray-300 hover:bg-gray-700 transition-all active:scale-95"
                >
                    {hasAlatHabis ? 'KEMBALI KE SCAN' : 'SELESAI'}
                </button>
            </div>
        </div>
    );
}