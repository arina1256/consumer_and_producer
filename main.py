#!/usr/bin/python3

import tkinter as tk
from PIL import Image, ImageTk
import glob
import os
import multiprocessing
import queue
import glymur
import numpy as np

TASK_QUEUE_SIZE = 20
THUMBNAIL_SIZE = (640, 480)
LOADING_DELAY = 200
NUMBER_OF_CONSUMERS = max(os.cpu_count()-1,1)
RESULTS_CHECK_DELAY = 10
RGB_NUMBER = 3
MAX_RGB = 255

def consumer_task(task_queue, result_queue, stop_event):
    while not stop_event.is_set():
        try:
            task = task_queue.get(timeout=1)
            if task is None:
                break
            
            i, path = task
            
            jp2 = glymur.Jp2k(path)
            data = jp2[:]
            
            if len(data.shape) == RGB_NUMBER and data.shape[2] == RGB_NUMBER:
                if data.dtype != np.uint8:
                    data = (data / data.max() * MAX_RGB).astype(np.uint8)
                
            img = Image.fromarray(data, mode='RGB')
            img.thumbnail(THUMBNAIL_SIZE)
            result_queue.put((i, img.tobytes(), img.size))

        except queue.Empty:
            continue
        except Exception as err:
            print(f"Ошибка: {err}")

class JP2Viewer:
    def __init__(self, directory_path, fps):
        self.files = glob.glob(os.path.join(directory_path, "*.jp2"))
        self.files.sort()
        
        self.number_of_frames = len(self.files)
        if self.number_of_frames==0:
            print("Пустая папка")
            return
        
        self.fps = fps
        self.delay = 1000//fps if fps>0 else 66
        self.stop_event = multiprocessing.Event()
        
        self.num_consumers = NUMBER_OF_CONSUMERS
        
        self.task_queue = multiprocessing.Queue(maxsize=TASK_QUEUE_SIZE)
        self.result_queue = multiprocessing.Queue()
        
        self.frames = [None]*self.number_of_frames
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
        
        self.start_processings()
        self.check_loading()
        self.window.mainloop()
    
    def producer_task(self):
        for i, path in enumerate(self.files):
            if self.stop_event.is_set():
                break
            try:
                self.task_queue.put((i, path), timeout=1)
            except Exception as err:
                print(f"Ошибка: {err}")
        for _ in range(self.num_consumers):
            try:
                self.task_queue.put(None, timeout=1)
            except Exception as err:
                print(f"Ошибка: {err}")
    
    def start_processings(self):
        self.producer = multiprocessing.Process(target=self.producer_task)
        self.producer.start()
        
        self.consumers = []
        for i in range(self.num_consumers):
            consumer = multiprocessing.Process(target=consumer_task, args=(self.task_queue, self.result_queue, self.stop_event))
            consumer.start()
            self.consumers.append(consumer)

        self.window.after(0, self.collect_results)
    
    def collect_results(self):
        try:
            while True:
                i, data, size = self.result_queue.get_nowait()
                
                self.frames[i] = Image.frombytes('RGB', size, data)
                self.loaded_number += 1
                
                if i == 0:
                    self.show_frame(i)
        except queue.Empty:
            pass
        
        if not self.stop_event.is_set():
            self.window.after(RESULTS_CHECK_DELAY, self.collect_results)
    
    def check_loading(self):
        if self.frames[0] is not None:
            self.show_frame(0)
            self.play()
        else:
            self.info.config(text=f"Загрузка первого кадра({self.loaded_number}/{self.number_of_frames})")
            self.window.after(LOADING_DELAY, self.check_loading)
    
    def show_frame(self, index):
        try:
            img = self.frames[index]
            
            if img:
                photo = ImageTk.PhotoImage(img)
                self.label.config(image=photo)
                self.label.image = photo
                self.current_index = index
                
        except Exception as err:
            print(f"Ошибка: {err}")
    
    def play(self):
        if self.stop_event.is_set():
            return
        
        next_index = (self.current_index+1)%self.number_of_frames
        
        if self.frames[next_index]:
            self.show_frame(next_index)
        else:
            next_index = self.current_index
        
        self.info.config(text=f"Кадр {next_index + 1}/{self.number_of_frames}, Загружено: {self.loaded_number}")
        
        self.window.after(self.delay, self.play)
    
    def exit(self):
        print("Завершение")
        self.stop_event.set()
        
        for _ in range(self.num_consumers):
            self.task_queue.put_nowait(None)

        self.producer.join()
        for i in self.consumers:
            i.join()
	
        self.window.quit()
        self.window.destroy()

if __name__ == "__main__":
    directory = "converted"
    if os.path.exists(directory):
        print("Запуск")
        viewer = JP2Viewer(directory, fps=15)
    else:
        print(f"Папка {directory} не найдена")
