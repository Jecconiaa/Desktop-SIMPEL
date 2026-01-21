    //components/Camera/UnifiedScanner.tsx

    "use client";

    import { useEffect, useRef, useState } from "react"; //hooks
    import * as faceapi from "face-api.js"; // library face detection
    import jsQR from "jsqr"; // library QR code scanning

    interface UnifiedScannerProps {
        onQrScan: (data: string) => void; // callback saat QR code terdeteksi
        onFaceDetect: (count: number) => void; // callback saat wajah terdeteksi
    }

    export default function UnifiedScanner({ onQrScan, onFaceDetect }: UnifiedScannerProps) { // komponen utama
        const videoRef = useRef<HTMLVideoElement>(null); // referensi elemen video
        const faceCanvasRef = useRef<HTMLCanvasElement>(null); // referensi kanvas untuk face detection
        const qrCanvasRef = useRef<HTMLCanvasElement>(null); // referensi kanvas untuk QR scanning

        const loopRef = useRef<NodeJS.Timeout | null>(null); // referensi untuk loop utama
        const lastQrRef = useRef<string | null>(null); // menyimpan data QR terakhir yang terdeteksi
        const [isLoading, setIsLoading] = useState(true); // state loading

        // 1. LOAD MODEL + START CAMERA
        useEffect(() => {

            let stream: MediaStream | null = null; // menyimpan stream kamera
            const start = async () => { // fungsi untuk memulai kamera dan load model
                try {
                    await faceapi.nets.tinyFaceDetector.loadFromUri("/Models"); // load model face detection

                    stream = await navigator.mediaDevices.getUserMedia({ 
                        video: { facingMode: "user", width: 640, height: 480 } // konfigurasi kamera depan
                    });

                    if (videoRef.current) { // kalo video siap
                        videoRef.current.srcObject = stream;  // set stream ke elemen video
                        setIsLoading(false); // set loading false
                    }
                } catch (e) {
                    console.error("Camera Error:", e); // tangani error kamera
                    setIsLoading(false);
                }
            };

            start(); // jalanin fungsi diatas

            return () => { // cleanup wktu user tinggalin halaman
                if (loopRef.current) clearInterval(loopRef.current); 
                if (stream) stream.getTracks().forEach((t) => t.stop());
            };
        }, []);

        // 2. MAIN SCAN LOOP 
        const handleVideoPlay = () => { // fungsi utama pas video mulai main
            const video = videoRef.current;
            const faceCanvas = faceCanvasRef.current;
            const qrCanvas = qrCanvasRef.current;

            if (!video || !faceCanvas || !qrCanvas) return; // kalo gada apa" ga jalanin

            // Tunggu video siap
            if (video.readyState < 2) {
                setTimeout(handleVideoPlay, 100);
                return;
            }

            const W = video.videoWidth;
            const H = video.videoHeight;

            // Fix ukuran canvas sesuai video
            faceCanvas.width = W;
            faceCanvas.height = H;

            qrCanvas.width = W;
            qrCanvas.height = H;

            const faceCtx = faceCanvas.getContext("2d");
            const qrCtx = qrCanvas.getContext("2d", { willReadFrequently: true });

            if (!faceCtx || !qrCtx) return; // kalo gada context ga jalanin

            // clear loop sebelumnya
            if (loopRef.current) clearInterval(loopRef.current);

            // === Proses Scanning ===
            loopRef.current = setInterval(async () => { // loop utama setiap 160ms
                if (!video || video.paused || video.ended) return; // kalo video ga jalanin ga lanjut

                // ===== FACE DETECTION =====
                const detections = await faceapi.detectAllFaces( //manggil pendeteksian wajah
                    video,
                    new faceapi.TinyFaceDetectorOptions()
                );

                onFaceDetect(detections.length); // kirim jumlah wajah terdeteksi

                faceCtx.clearRect(0, 0, W, H);
                const resized = faceapi.resizeResults(detections, { width: W, height: H });
                faceapi.draw.drawDetections(faceCanvas, resized);

                // ==== QR SCAN ====
                qrCtx.clearRect(0, 0, W, H); 
                qrCtx.drawImage(video, 0, 0, W, H); // gambar frame video ke kanvas

                const img = qrCtx.getImageData(0, 0, W, H); // ambil data gambar dari kanvas
                const code = jsQR(img.data, W, H, { inversionAttempts: "dontInvert" }); // suruh jsqr scan 

                if (code && code.data !== lastQrRef.current) { // kalo ada QR code baru
                    lastQrRef.current = code.data; // simpan data QR terakhir
                    onQrScan(code.data); // kirim isi QR code
                }

            }, 160); // **160ms = optimal**
        };

        return (
            <div className="relative w-full h-full bg-black overflow-hidden">
                {isLoading && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center z-20 bg-gray-900 text-white">
                        <div className="w-10 h-10 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin mb-4"></div>
                        <p className="animate-pulse text-xs">Loading...</p>
                    </div>
                )}

                <video
                    ref={videoRef}
                    autoPlay
                    muted
                    playsInline
                    onPlay={handleVideoPlay}
                    className="w-full h-full object-cover transform scale-x-[-1]"
                />

                {/* FACE OVERLAY */}
                <canvas
                    ref={faceCanvasRef}
                    className="absolute top-0 left-0 w-full h-full pointer-events-none transform scale-x-[-1]"/>

                {/* QR CANVAS (hidden) */}
                <canvas ref={qrCanvasRef} className="hidden" />
            </div>
        );
    }
