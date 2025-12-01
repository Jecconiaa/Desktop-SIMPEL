"use client";

import { useEffect, useRef, useState } from "react";
import * as faceapi from "face-api.js";
import jsQR from "jsqr";

interface UnifiedScannerProps {
    onQrScan: (data: string) => void;
    onFaceDetect: (count: number) => void; // Opsional: kasih tau ada berapa muka
}

export default function UnifiedScanner({ onQrScan, onFaceDetect }: UnifiedScannerProps) {
    const videoRef = useRef<HTMLVideoElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const [isLoading, setIsLoading] = useState(true);
    const lastQrRef = useRef<string | null>(null); // Biar gak spam scan QR yg sama

    useEffect(() => {
        let stream: MediaStream | null = null;
        let isMounted = true;

        const startSystem = async () => {
            try {
                // 1. Load Model Face API
                console.log("Loading AI Models...");
                await faceapi.nets.tinyFaceDetector.loadFromUri("/Models");

                // 2. Nyalain Kamera
                stream = await navigator.mediaDevices.getUserMedia({
                    video: { facingMode: "user", width: 640, height: 480 }
                });

                if (isMounted && videoRef.current) {
                    videoRef.current.srcObject = stream;
                    videoRef.current.setAttribute("playsinline", "true");
                    setIsLoading(false);
                }
            } catch (err) {
                console.error("Error starting scanner:", err);
                setIsLoading(false);
            }
        };

        startSystem();

        return () => {
            isMounted = false;
            if (stream) stream.getTracks().forEach(track => track.stop());
        };
    }, []);

    const handleVideoPlay = () => {
        const video = videoRef.current;
        const canvas = canvasRef.current;

        if (!video || !canvas) return;

        const displaySize = { width: video.videoWidth, height: video.videoHeight };
        faceapi.matchDimensions(canvas, displaySize);

        // Bikin canvas virtual kecil buat proses QR
        const qrCanvas = document.createElement("canvas");
        const qrCtx = qrCanvas.getContext("2d", { willReadFrequently: true });

        const renderLoop = setInterval(async () => {
            if (!video || video.paused || video.ended) {
                clearInterval(renderLoop);
                return;
            }

            // Deteksi Wajah
            const detections = await faceapi.detectAllFaces(
                video,
                new faceapi.TinyFaceDetectorOptions()
            );

            // Kirim info jumlah muka ke parent
            if (detections.length > 0) onFaceDetect(detections.length);

            // Deteksi QR
            if (qrCtx) {
                // Resize canvas virtual sesuaikan video
                if (qrCanvas.width !== video.videoWidth) {
                    qrCanvas.width = video.videoWidth;
                    qrCanvas.height = video.videoHeight;
                }

                // Gambar frame video ke canvas virtual
                qrCtx.drawImage(video, 0, 0);
                const imageData = qrCtx.getImageData(0, 0, qrCanvas.width, qrCanvas.height);

                // Scan pixelnya
                const code = jsQR(imageData.data, imageData.width, imageData.height, {
                    inversionAttempts: "dontInvert",
                });

                // Kalau dapet QR
                if (code) {
                    // Cek duplikat biar gak spam
                    if (code.data !== lastQrRef.current) {
                        lastQrRef.current = code.data;
                        onQrScan(code.data);

                        // Efek getar kalo di HP (Haptic Feedback)
                        if (navigator.vibrate) navigator.vibrate(200);
                    }
                }
            }

            // --- JOB 3: DRAWING VISUALS (Overlay) ---
            const ctx = canvas.getContext("2d");
            if (ctx) {
                // Bersihin canvas dulu
                ctx.clearRect(0, 0, canvas.width, canvas.height);

                // 1. Gambar Kotak Muka (Biru)
                const resizedDetections = faceapi.resizeResults(detections, displaySize);
                faceapi.draw.drawDetections(canvas, resizedDetections);

                // 2. Gambar Kotak QR (Merah) - Kita gambar manual di canvas yg sama
                // Kita re-scan ulang frame yg sama? Gak perlu, kita ambil koordinat dari JOB 2 tadi
                // Tapi karena 'code' ada di scope lokal, kita scan ulang bentar di sini atau 
                // idealnya state manajemen. Tapi biar simple, kita gambar indikator teks aja.

                if (lastQrRef.current) {
                    ctx.font = "bold 20px Courier New";
                    ctx.fillStyle = "#00FF00";
                    ctx.fillText("QR DETECTED ✅", 20, 50);
                }
            }

        }, 150); // Loop setiap 150ms (Cukup cepet buat muka & QR)
    };

    return (
        <div className="relative w-full h-full bg-black rounded-2xl overflow-hidden shadow-2xl border border-gray-700">
            {isLoading && (
                <div className="absolute inset-0 flex flex-col items-center justify-center z-20 bg-gray-900 text-white">
                    <div className="w-10 h-10 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin mb-4"></div>
                    <p className="animate-pulse">Loading...</p>
                </div>
            )}

            <video
                ref={videoRef}
                autoPlay
                muted
                playsInline
                onPlay={handleVideoPlay}
                className="w-full h-full object-cover transform scale-x-[-1]" // Mirror effect
            />
            <canvas
                ref={canvasRef}
                className="absolute top-0 left-0 w-full h-full pointer-events-none transform scale-x-[-1]"
            />

            {/* UI Overlay statis */}
            <div className="absolute bottom-4 left-0 w-full text-center pointer-events-none">
                <div className="inline-block px-4 py-1 bg-black/50 rounded-full backdrop-blur-sm border border-white/10">
                    <p className="text-xs text-cyan-400 tracking-widest font-mono">
                        SCANNING: FACE & QR
                    </p>
                </div>
            </div>
        </div>
    );
}