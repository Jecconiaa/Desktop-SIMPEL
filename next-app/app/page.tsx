// next-app/app/page.tsx
"use client";

import { useState, useEffect, useRef } from "react";
import UnifiedScanner from "@/components/Camera/UnifiedScanner";
import { Toast } from "@/components/Toast";

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
            quantity?: number;
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
    const [scannedData, setScannedData] = useState<TransactionData | null>(null);
    const [faceCount, setFaceCount] = useState(0);
    const [currentTime, setCurrentTime] = useState<string>("");
    const [isLoading, setIsLoading] = useState(false);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [scannerKey, setScannerKey] = useState(0);

    // ⭐ STATE TOAST
    const [toast, setToast] = useState<{
        message: string;
        type: 'success' | 'error' | 'info';
    } | null>(null);

    const lastScanRef = useRef<number>(0);

    // ⭐ FUNGSI SHOW TOAST
    const showToast = (message: string, type: 'success' | 'error' | 'info' = 'info') => {
        setToast({ message, type });
        setTimeout(() => setToast(null), 3000);
    };

    useEffect(() => {
        const updateTime = () =>
            setCurrentTime(new Date().toLocaleTimeString("id-ID"));
        const timer = setInterval(updateTime, 1000);
        return () => clearInterval(timer);
    }, []);

    const handleQrFound = async (qrString: string) => {
        const now = Date.now();
        if (now - lastScanRef.current < 1500) return;
        lastScanRef.current = now;

        if (scannedData || isLoading || errorMessage) return;

        setIsLoading(true);
        setErrorMessage(null);

        try {
            console.log("🔵 [STEP 1] Mengirim QR untuk update status...");

            // ⭐ 1. POST untuk update status Booked → Diproses
            const scanRes = await fetch(
                `http://localhost:5234/api/borrowing/scan-qr/${encodeURIComponent(qrString)}`,
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    }
                }
            );

            const scanResult = await scanRes.json();
            console.log("🔵 [STEP 1 Result]:", scanResult);

            if (!scanRes.ok || !scanResult.success) {
                throw new Error(scanResult.message || `Gagal scan QR. Status: ${scanRes.status}`);
            }

            // ⭐ TOAST SUCCESS - MODERN!
            showToast("✅ QR Berhasil di-Scan!", "success");

            console.log("✅ [STEP 1 Success] Status berubah: Booked → Diproses");

            // ⭐ 2. GET data untuk ditampilkan
            console.log("🔵 [STEP 2] Mengambil data transaksi...");
            const dataRes = await fetch(
                `http://localhost:5234/api/borrowing/scan-data/${encodeURIComponent(qrString)}`,
                {
                    method: "GET",
                    headers: {
                        "Accept": "application/json"
                    }
                }
            );

            const contentType = dataRes.headers.get("content-type");
            if (!contentType || !contentType.includes("application/json")) {
                throw new Error(`Server Error: ${dataRes.status}`);
            }

            const dataResult = await dataRes.json();
            console.log("🔵 [STEP 2 Result]:", dataResult);

            if (dataRes.ok && dataResult.success) {
                // Process data alat
                let alatArray: string[] = [];

                if (dataResult.data?.peminjaman_detail && Array.isArray(dataResult.data.peminjaman_detail)) {
                    const alatMap = new Map<string, number>();

                    dataResult.data.peminjaman_detail.forEach((item: any) => {
                        const nama = item.nama_alat || item.EquipmentName;
                        const qty = item.quantity || item.Quantity || 1;

                        if (nama) {
                            alatMap.set(nama, (alatMap.get(nama) || 0) + qty);
                        }
                    });

                    alatArray = Array.from(alatMap.entries()).map(([nama, qty]) =>
                        qty > 1 ? `${nama} (${qty}x)` : nama
                    );
                }

                const fixedData: TransactionData = {
                    nama: dataResult.data?.mahasiswa?.nama || "Mahasiswa Ditemukan",
                    nim: dataResult.data?.mahasiswa?.nim || "-",
                    alat: alatArray,
                    raw: qrString
                };

                console.log("✅ [STEP 2 Success] Data untuk UI:", fixedData);
                setScannedData(fixedData);

            } else {
                setErrorMessage(dataResult.message || "Data tidak ditemukan setelah scan");
                showToast("❌ Data tidak ditemukan", "error");
            }

        } catch (err: any) {
            console.error("❌ Error total:", err);

            let errorMsg = err.message || "Gagal terhubung ke server";

            if (errorMsg.includes("Booked")) {
                errorMsg = `❌ Hanya booking dengan status "Booked" yang bisa di-scan.\n${errorMsg}`;
                showToast("❌ Status bukan 'Booked'", "error");
            } else if (errorMsg.includes("404") || errorMsg.includes("tidak ditemukan")) {
                errorMsg = "❌ QR Code tidak ditemukan. Pastikan booking sudah dibuat di mobile app.";
                showToast("❌ QR tidak ditemukan", "error");
            } else if (errorMsg.includes("500")) {
                errorMsg = "❌ Server error. Hubungi administrator.";
                showToast("❌ Server error", "error");
            } else {
                showToast("❌ Gagal scan QR", "error");
            }

            setErrorMessage(errorMsg);
        } finally {
            setIsLoading(false);
        }
    };

    const handleFaceUpdate = (count: number) => {
        setFaceCount(count);
    };

    const resetScan = () => {
        setScannedData(null);
        setErrorMessage(null);
        lastScanRef.current = 0;
        setScannerKey(prev => prev + 1);
    };

    return (
        <div className="flex h-screen w-full flex-col overflow-hidden bg-[#0d1b2a] font-sans text-white">
            {/* ⭐ RENDER TOAST DISINI */}
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
                    />
                </div>

                <div className="col-span-12 h-full min-h-0 lg:col-span-4">
                    <InfoPanel scannedData={scannedData} onReset={resetScan} isLoading={isLoading} />
                </div>
            </main>
        </div>
    );
}

// --- SUB COMPONENTS (TETAP SAMA) ---

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

            {/* OVERLAY ERROR */}
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
        // ⭐ PASTIKAN PARENT PUNYA h-full DAN overflow-hidden
        <div className="relative flex h-full flex-col rounded-3xl border border-gray-700 bg-[#162032] overflow-hidden">
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
        // ⭐ SIMPLE: HANYA FLEX-COL H-FULL
        <div className="flex flex-col h-full">
            {/* HEADER */}
            <div className="shrink-0 border-b border-white/10 bg-gradient-to-r from-cyan-900/50 to-blue-900/50 p-6">
                <div className="flex items-center justify-between mb-2">
                    <div>
                        <p className="mb-1 text-[10px] font-bold uppercase tracking-widest text-cyan-300">
                            DATA PEMINJAM
                        </p>
                        <h2 className="text-2xl font-bold leading-tight text-white">{data.nama}</h2>
                        <p className="mt-1 font-mono text-sm text-gray-300">{data.nim}</p>
                    </div>
                    <div className="rounded-full bg-green-500/20 px-3 py-1">
                        <span className="text-xs font-bold text-green-400">DIPROSES</span>
                    </div>
                </div>
                <div className="mt-3 rounded-lg bg-green-900/30 p-2">
                    <p className="text-xs text-green-300">
                        ✅ Status berhasil diupdate: <span className="font-bold">Booked → Diproses</span>
                    </p>
                </div>
            </div>

            {/* ⭐ MIDDLE SECTION YANG BISA SCROLL */}
            <div className="flex-1 overflow-y-auto">
                {/* HEADER DAFTAR ALAT */}
                <div className="sticky top-0 z-10 px-6 pt-4 pb-2 border-b border-gray-800 bg-[#162032]">
                    <p className="text-xs font-bold uppercase tracking-wider text-gray-500">
                        DAFTAR ALAT ({data.alat?.length || 0})
                    </p>
                </div>

                {/* LIST ALAT */}
                <div className="px-6 py-4">
                    <div className="space-y-3">
                        {data.alat && data.alat.length > 0 ? (
                            data.alat.map((item, i) => (
                                <div key={i} className="flex items-start gap-3 rounded-xl border border-gray-700/50 bg-[#0d1b2a] p-4">
                                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-indigo-500/20 bg-indigo-500/10 text-lg text-indigo-400 mt-0.5">
                                        📦
                                    </div>
                                    <span className="block text-sm font-medium text-gray-200 break-words flex-1">
                                        {item}
                                    </span>
                                </div>
                            ))
                        ) : (
                            <p className="text-sm text-gray-400 text-center py-8">Tidak ada detail alat.</p>
                        )}
                    </div>
                </div>
            </div>

            {/* FOOTER - SELALU DI BAWAH */}
            <div className="shrink-0 border-t border-gray-800 bg-[#0d1b2a] p-6">
                <button
                    onClick={onReset}
                    className="w-full rounded-xl bg-gray-800 py-4 font-bold text-gray-300 hover:bg-gray-700 transition-all active:scale-95"
                >
                    SELESAI
                </button>
            </div>
        </div>
    );
}