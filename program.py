import tkinter as tk
from tkinter import messagebox
import json
import os
import random
import time
import threading

# --- OCR 및 화면 캡처 관련 라이브러리 ---
import pytesseract
from PIL import Image
import mss
# pynput은 이제 사용하지 않으므로 제거해도 됩니다.

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
        if not self.is_running: return
        self.current_string = random.choice(self.strings)
        self.current_note_pair = random.choice(self.notes)
        problem_text = f"{self.current_string}, {self.current_note_pair[0]}"
        self.problem_label.config(text=problem_text)
        self.status_label.config(text="해당 음을 연주하세요...", fg="blue")

    def ocr_loop(self):
        """지정된 영역을 지속적으로 캡처하고 OCR을 수행합니다."""
        with mss.mss() as sct:
            while self.is_running:
                sct_img = sct.grab(self.capture_coords)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                img = img.convert('L')
                img = img.point(lambda x: 0 if x < 128 else 255, '1')

                try:
                    custom_config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFG#b/'
                    recognized_text = pytesseract.image_to_string(img, config=custom_config).strip()
                    
                    # === ✨ [개선 2] 음이름 인식 로직 확장 ===
                    is_correct = False
                    # 1. 직접 일치 확인 (예: "A#"가 ("A#", "Bb") 안에 있는지)
                    if recognized_text in self.current_note_pair:
                        is_correct = True
                    # 2. 복합 표기 확인 (예: "A#/Bb"가 문제일 때)
                    elif len(self.current_note_pair) > 1:
                        note1, note2 = self.current_note_pair
                        # 인식된 텍스트 안에 두 음이 모두 포함되어 있는지 확인
                        if note1 in recognized_text and note2 in recognized_text:
                            is_correct = True
                    
                    if is_correct:
                        self.root.after(0, self.on_correct_answer)
                        time.sleep(1) 

                except pytesseract.TesseractNotFoundError:
                    self.root.after(0, self.show_tesseract_error)
                    self.stop()
                    break
                except Exception as e:
                    print(f"OCR Error: {e}")

                time.sleep(0.1)

    def on_correct_answer(self):
        """정답일 때 GUI를 업데이트하는 함수"""
        self.status_label.config(text="정답!", fg="green")
        self.root.update_idletasks()
        self.root.after(1000, self.next_problem)

    def on_closing(self):
        self.is_running = False
        self.root.destroy()
        
    def show_tesseract_error(self):
        messagebox.showerror("Tesseract 오류", "Tesseract-OCR이 설치되지 않았거나 경로가 지정되지 않았습니다.\n코드 상단의 경로 설정을 확인해주세요.")

    # === ✨ [개선 1] 캡처 영역 시각화 로직 ===
    def setup_capture_region(self):
        """사용자가 마우스로 캡처 영역을 설정하도록 안내합니다."""
        messagebox.showinfo("최초 설정", "튜너의 음이름이 표시되는 영역을 마우스로 드래그하여 지정합니다.\n'확인'을 누른 후, 화면 왼쪽 위에서 클릭을 시작하여 오른쪽 아래로 드래그하세요.")
        
        self.setup_window = tk.Toplevel(self.root)
        self.setup_window.attributes("-fullscreen", True)
        self.setup_window.attributes("-alpha", 0.3)
        self.setup_window.attributes("-topmost", True) # 항상 위에 있도록
        
        self.canvas = tk.Canvas(self.setup_window, cursor="cross", bg="grey")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.start_x, self.start_y = None, None
        self.rect = None

        self.canvas.bind("<ButtonPress-1>", self.on_mouse_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_release)

    def on_mouse_press(self, event):
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='red', width=2)

    def on_mouse_drag(self, event):
        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_mouse_release(self, event):
        end_x = self.canvas.canvasx(event.x)
        end_y = self.canvas.canvasy(event.y)
        self.setup_window.destroy()

        left = min(self.start_x, end_x)
        top = min(self.start_y, end_y)
        right = max(self.start_x, end_x)
        bottom = max(self.start_y, end_y)

        if right - left < 10 or bottom - top < 10:
             messagebox.showwarning("설정 오류", "영역이 너무 작습니다. 다시 시도해주세요.")
             self.capture_coords = None
             return

        self.capture_coords = {"top": int(top), "left": int(left), "width": int(right - left), "height": int(bottom - top)}
        
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.capture_coords, f)
        
        messagebox.showinfo("설정 완료", f"캡처 영역이 저장되었습니다: {self.capture_coords}\n프로그램을 시작합니다.")
        self.load_config()
        self.start()


if __name__ == "__main__":
    root = tk.Tk()
    app = FretboardTrainer(root)
    root.mainloop()