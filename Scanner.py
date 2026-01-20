# scanner.py
import cv2
from pyzbar.pyzbar import decode
import json

def start_scanner():
    last_qr_data = None
    cap = cv2.VideoCapture(0) 

    print("Scanner Aktif... (Tekan 'q' di jendela kamera buat stop)")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        detected_qrs = decode(frame)

        for obj in detected_qrs:
            current_qr_string = obj.data.decode('utf-8')

            if current_qr_string != last_qr_data:
                last_qr_data = current_qr_string
                
                # Pas dapet data, kita stop scanner dan balikin datanya
                cap.release()
                cv2.destroyAllWindows()
                return current_qr_string # <--- Ini yang bakal ditangkep Main.py

            (x, y, w, h) = obj.rect
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

        cv2.imshow('Scanner Window', frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    return raw_data