import tkinter as tk
from tkinter import messagebox
import json
import os
import random
import time
import threading

import pytesseract
from PIL import Image
import mss
from pynput import mouse

# --- 설정 (Configuration) ---
# Windows 사용자의 경우, Tesseract 설치 경로를 지정해야 합니다.
# 예: pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# 아래 주석을 풀고 자신의 경로에 맞게 수정하세요.
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe" 

CONFIG_FILE = "config.json"

class FretboardTrainer:
    def __init__(self, root):
        self.root = root
        self.root.title("기타 프렛보드 트레이너")
        self.root.geometry("400x250")

        # --- 상태 변수 ---
        self.capture_coords = None
        self.is_running = False
        self.current_string = ""
        self.current_note_pair = []

        # --- 데이터 ---
        self.strings = [f"{i}번 줄" for i in range(1, 7)]
        self.notes = [
            ("C",), ("C#", "Db"), ("D",), ("D#", "Eb"), ("E",), ("F",),
            ("F#", "Gb"), ("G",), ("G#", "Ab"), ("A",), ("A#", "Bb"), ("B",)
        ]

        # --- UI 요소 ---
        self.info_label = tk.Label(root, text="아래 '시작' 버튼을 눌러주세요.", font=("Arial", 14))
        self.info_label.pack(pady=10)

        self.problem_label = tk.Label(root, text="", font=("Arial", 36, "bold"))
        self.problem_label.pack(pady=20)

        self.status_label = tk.Label(root, text="", font=("Arial", 12), fg="blue")
        self.status_label.pack(pady=5)
        
        self.start_button = tk.Button(root, text="시작", command=self.start)
        self.start_button.pack(side=tk.LEFT, padx=20)
        
        self.stop_button = tk.Button(root, text="정지", command=self.stop, state=tk.DISABLED)
        self.stop_button.pack(side=tk.RIGHT, padx=20)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.load_config()

    def load_config(self):
        """설정 파일에서 캡처 좌표를 불러옵니다."""
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                self.capture_coords = json.load(f)
            self.info_label.config(text="설정이 로드되었습니다. '시작' 버튼을 누르세요.")
        else:
            self.info_label.config(text="최초 설정이 필요합니다. '시작' 버튼을 누르세요.")

    def start(self):
        """트레이너를 시작합니다."""
        if self.capture_coords is None:
            self.setup_capture_region()
        else:
            if not self.is_running:
                self.is_running = True
                self.start_button.config(state=tk.DISABLED)
                self.stop_button.config(state=tk.NORMAL)
                self.info_label.config(text="트레이너가 실행 중입니다.")
                self.status_label.config(text="")
                
                # 별도의 스레드에서 OCR 루프 실행
                self.ocr_thread = threading.Thread(target=self.ocr_loop, daemon=True)
                self.ocr_thread.start()
                
                self.next_problem()

    def stop(self):
        """트레이너를 정지합니다."""
        if self.is_running:
            self.is_running = False
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.info_label.config(text="정지되었습니다. 다시 시작하려면 '시작' 버튼을 누르세요.")

    def next_problem(self):
        """다음 문제를 출제합니다."""
        self.current_string = random.choice(self.strings)
        self.current_note_pair = random.choice(self.notes)
        problem_text = f"{self.current_string}, {self.current_note_pair[0]}"
        self.problem_label.config(text=problem_text)
        self.status_label.config(text="해당 음을 연주하세요...", fg="blue")

    def ocr_loop(self):
        """지정된 영역을 지속적으로 캡처하고 OCR을 수행합니다."""
        with mss.mss() as sct:
            while self.is_running:
                # 캡처 및 이미지 처리
                sct_img = sct.grab(self.capture_coords)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                
                # 이미지 전처리 (흑백, 이진화) - OCR 정확도 향상
                img = img.convert('L')
                img = img.point(lambda x: 0 if x < 128 else 255, '1')

                # OCR 실행
                try:
                    # --psm 7: 이미지를 한 줄의 텍스트로 취급
                    custom_config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFG#b'
                    recognized_text = pytesseract.image_to_string(img, config=custom_config).strip()
                    
                    # 정답 확인
                    if recognized_text in self.current_note_pair:
                        self.root.after(0, self.on_correct_answer)
                        time.sleep(1) # 정답 표시 후 잠시 대기

                except pytesseract.TesseractNotFoundError:
                    self.root.after(0, self.show_tesseract_error)
                    self.stop()
                    break
                except Exception as e:
                    print(f"OCR Error: {e}")

                time.sleep(0.1) # 확인 주기 (0.1초)

    def on_correct_answer(self):
        """정답일 때 GUI를 업데이트하는 함수"""
        self.status_label.config(text="정답!", fg="green")
        self.root.update_idletasks()
        self.root.after(1000, self.next_problem) # 1초 후 다음 문제 출제

    def setup_capture_region(self):
        """사용자가 마우스로 캡처 영역을 설정하도록 안내합니다."""
        messagebox.showinfo("최초 설정", "튜너의 음이름이 표시되는 영역을 마우스로 드래그하여 지정합니다.\n'확인'을 누른 후, 화면 왼쪽 위에서 클릭을 시작하여 오른쪽 아래로 드래그하세요.")
        
        # 설정 창 생성
        self.setup_window = tk.Toplevel(self.root)
        self.setup_window.attributes("-fullscreen", True)
        self.setup_window.attributes("-alpha", 0.3) # 반투명
        self.setup_window.wait_visibility(self.setup_window)
        
        self.start_x, self.start_y = None, None
        self.rect = None

        self.setup_window.bind("<ButtonPress-1>", self.on_mouse_press)
        self.setup_window.bind("<B1-Motion>", self.on_mouse_drag)
        self.setup_window.bind("<ButtonRelease-1>", self.on_mouse_release)

    def on_mouse_press(self, event):
        self.start_x = event.x
        self.start_y = event.y

    def on_mouse_drag(self, event):
        pass # 드래그 시 시각적 효과는 생략하여 단순화

    def on_mouse_release(self, event):
        end_x, end_y = event.x, event.y
        self.setup_window.destroy()

        # 좌표 정렬 (왼쪽-위 -> 오른쪽-아래)
        left = min(self.start_x, end_x)
        top = min(self.start_y, end_y)
        right = max(self.start_x, end_x)
        bottom = max(self.start_y, end_y)

        if right - left < 10 or bottom - top < 10:
             messagebox.showwarning("설정 오류", "영역이 너무 작습니다. 다시 시도해주세요.")
             return

        self.capture_coords = {"top": top, "left": left, "width": right - left, "height": bottom - top}
        
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.capture_coords, f)
        
        messagebox.showinfo("설정 완료", f"캡처 영역이 저장되었습니다: {self.capture_coords}\n프로그램을 시작합니다.")
        self.load_config()
        self.start()

    def show_tesseract_error(self):
        messagebox.showerror("Tesseract 오류", "Tesseract-OCR이 설치되지 않았거나 경로가 지정되지 않았습니다.\n코드 상단의 경로 설정을 확인해주세요.")

    def on_closing(self):
        self.is_running = False
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = FretboardTrainer(root)
    root.mainloop()