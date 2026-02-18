import tkinter as tk
from PIL import Image, ImageTk
import glob
import os
import threading
import queue
import time

class JP2Viewer:
    def __init__(self, directory_path, fps=30):
        self.files = glob.glob(os.path.join(directory_path, "*.jp2"))
        self.files.sort()
        
        self.number_of_frames = len(self.files)
        
        self.fps = fps
        self.delay = int(1000 / fps)
        self.running = True
        
        self.num_consumers = 2
        
        self.task_queue = queue.Queue(maxsize=20)
        self.result_queue = queue.Queue(maxsize=10)
        
        self.frames = [None]*self.number_of_frames
        self.frames_lock = threading.Lock()
        self.loaded_number = 0
        
        self.current_index = 0
        
        self.window = tk.Tk()
        self.window.title("JP2 Viewer")
        self.window.protocol("WM_DELETE_WINDOW", self.exit)
        
        self.label = tk.Label(self.window, bg='pink')
        self.label.pack()
        
        self.info = tk.Label(self.window, text="Инициализация")
        self.info.pack()
        tk.Button(self.window, text="Выход", command=self.exit).pack()
        
        self.start_threads()
        self.check_loading()
        self.window.mainloop()
    
    def start_threads(self):
        self.producer = threading.Thread(target=self.producer_task)
        self.producer.daemon = True
        self.producer.start()
        
        self.consumers = []
        for i in range(self.num_consumers):
            consumer = threading.Thread(target=self.consumer_task, args=(i,))
            consumer.daemon = True
            consumer.start()
            self.consumers.append(consumer)
        
        self.collector = threading.Thread(target=self.collector_task)
        self.collector.daemon = True
        self.collector.start()
    
    def producer_task(self):
        for i, path in enumerate(self.files):
            if not self.running:
                break
            try:
                self.task_queue.put((i, path), timeout=1)
            except:
                pass
        
        for _ in range(self.num_consumers):
            try:
                self.task_queue.put(None, timeout=1)
            except:
                pass
    
    def consumer_task(self, worker_id):
        while self.running:
            try:
                task = self.task_queue.get(timeout=1)
                if task is None:
                    break
                
                i, path = task
                
                img = Image.open(path)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                img.thumbnail((640, 480))
                
                self.result_queue.put((i, img))
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Ошибка: {e}")
    
    def collector_task(self):
        while self.running:
            try:
                i, img = self.result_queue.get(timeout=1)
                
                with self.frames_lock:
                    self.frames[i] = img
                    self.loaded_number += 1
                    
                    if i == 0:
                        self.window.after(0, self.show_frame, i)
                
            except queue.Empty:
                continue
    
    def check_loading(self):
        if self.frames[0] is not None:
            self.show_frame(0)
            self.play()
        else:
            self.info.config(text=f"Загрузка первого кадра({self.loaded_number}/{self.number_of_frames})")
            self.window.after(200, self.check_loading)
    
    def show_frame(self, index):
        try:
            with self.frames_lock:
                img = self.frames[index]
            
            if img:
                photo = ImageTk.PhotoImage(img)
                self.label.config(image=photo)
                self.label.image = photo
                self.current_index = index
                
        except Exception as e:
            print(f"Ошибка: {e}")
    
    def play(self):
        if not self.running:
            return
        
        next_index = (self.current_index+1)%self.number_of_frames
        
        with self.frames_lock:
            next_img = self.frames[next_index]
            loaded = self.loaded_number
        
        if next_img:
            self.show_frame(next_index)
        
        self.info.config(text=f"Кадр {next_index + 1}/{self.number_of_frames}, Загружено: {loaded}")
        
        self.window.after(self.delay, self.play)
    
    def exit(self):
        print("Завершение")
        self.running = False
        self.window.quit()
        self.window.destroy()

if __name__ == "__main__":
    folder = "converted"
    
    if os.path.exists(folder):
        print("Запуск")
        viewer = JP2Viewer(folder, fps=15)
    else:
        print(f"Папка {folder} не найдена")