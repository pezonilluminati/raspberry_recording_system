import tkinter as tk
from tkinter import ttk, filedialog
import cv2
import os
import datetime
from pathlib import Path
import json
import threading
import pyaudio
import wave
import tempfile
from PIL import Image, ImageTk

class Config:
    def __init__(self):
        self.config_file = 'config.json'
        self.default_path = str(Path.home() / "Videos" / "Recordings")
        self.load_config()

    def load_config(self):
        try:
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            self.config = {
                'custom_save_path': self.default_path,
                'video_format': 'mp4'  # Default format
            }
            self.save_config()

    def save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f)

    def get_custom_path(self):
        return self.config.get('custom_save_path', self.default_path)

    def set_custom_path(self, path):
        self.config['custom_save_path'] = path
        self.save_config()

    def get_video_format(self):
        return self.config.get('video_format', 'mp4')

    def set_video_format(self, format):
        self.config['video_format'] = format
        self.save_config()

class VideoRecorder:
    def __init__(self, static_path, custom_path, video_format):
        self.static_path = Path(static_path)
        self.custom_path = Path(custom_path)
        self.video_format = video_format
        self.static_path.mkdir(parents=True, exist_ok=True)
        self.custom_path.mkdir(parents=True, exist_ok=True)
        
        self.cap = cv2.VideoCapture(0)
        self.frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = 20.0
        
        # Audio setup
        self.audio = pyaudio.PyAudio()
        self.audio_frames = []
        self.stream = None
        
        # Store current recording paths
        self.current_videos = []
        
    def start_recording(self):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Set video codec and extension based on format
        if self.video_format == 'mp4':
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            ext = 'mp4'
        else:  # avi
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            ext = 'avi'
            
        static_video_path = self.static_path / f"video_{timestamp}.{ext}"
        custom_video_path = self.custom_path / f"video_{timestamp}.{ext}"
        
        self.current_videos = [static_video_path, custom_video_path]
        
        self.video_writer_static = cv2.VideoWriter(
            str(static_video_path),
            fourcc,
            self.fps,
            (self.frame_width, self.frame_height)
        )
        
        self.video_writer_custom = cv2.VideoWriter(
            str(custom_video_path),
            fourcc,
            self.fps,
            (self.frame_width, self.frame_height)
        )
        
        # Start audio recording
        self.stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=2,
            rate=44100,
            input=True,
            frames_per_buffer=1024
        )
        self.audio_frames = []
        
        self.is_recording = True
        self.record_thread = threading.Thread(target=self._record)
        self.record_thread.start()

    def _record(self):
        while self.is_recording:
            ret, frame = self.cap.read()
            if ret:
                self.video_writer_static.write(frame)
                self.video_writer_custom.write(frame)
                
                # Record audio
                audio_data = self.stream.read(1024)
                self.audio_frames.append(audio_data)
                
    def stop_recording(self):
        self.is_recording = False
        self.record_thread.join()
        
        # Clean up video
        self.video_writer_static.release()
        self.video_writer_custom.release()
        
        # Clean up audio
        self.stream.stop_stream()
        self.stream.close()
        
        # Save audio files
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        for path in [self.static_path, self.custom_path]:
            wf = wave.open(str(path / f"audio_{timestamp}.wav"), 'wb')
            wf.setnchannels(2)
            wf.setsampwidth(self.audio.get_sample_size(pyaudio.paInt16))
            wf.setframerate(44100)
            wf.writeframes(b''.join(self.audio_frames))
            wf.close()
            
        return self.current_videos
            
    def __del__(self):
        self.cap.release()
        self.audio.terminate()

class PreviewWindow:
    def __init__(self, root, video_path, on_close):
        self.window = tk.Toplevel(root)
        self.window.title("Vista Previa")
        self.on_close = on_close
        
        # Set up video capture
        self.cap = cv2.VideoCapture(str(video_path))
        self.video_path = video_path
        
        # Create canvas for video display
        self.canvas = tk.Canvas(
            self.window,
            width=640,
            height=480
        )
        self.canvas.pack(pady=10)
        
        # Control buttons
        button_frame = ttk.Frame(self.window)
        button_frame.pack(pady=10)
        
        ttk.Button(
            button_frame,
            text="Reproducir",
            command=self.play_video
        ).pack(side="left", padx=5)
        
        ttk.Button(
            button_frame,
            text="Pausar",
            command=self.pause_video
        ).pack(side="left", padx=5)
        
        ttk.Button(
            button_frame,
            text="Borrar",
            command=self.delete_video
        ).pack(side="left", padx=5)
        
        ttk.Button(
            button_frame,
            text="Cerrar",
            command=self.close_window
        ).pack(side="left", padx=5)
        
        self.is_playing = False
        self.window.protocol("WM_DELETE_WINDOW", self.close_window)
        
    def play_video(self):
        self.is_playing = True
        self.update_frame()
        
    def pause_video(self):
        self.is_playing = False
        
    def update_frame(self):
        if self.is_playing:
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = cv2.resize(frame, (640, 480))
                photo = ImageTk.PhotoImage(image=Image.fromarray(frame))
                self.canvas.create_image(0, 0, image=photo, anchor="nw")
                self.canvas.photo = photo
                self.window.after(30, self.update_frame)
            else:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self.is_playing = False
                
    def delete_video(self):
        self.cap.release()
        try:
            os.remove(self.video_path)
            audio_path = self.video_path.parent / f"audio_{self.video_path.stem.split('_')[1]}.wav"
            if audio_path.exists():
                os.remove(audio_path)
        except Exception as e:
            print(f"Error deleting files: {e}")
        self.close_window()
        
    def close_window(self):
        self.cap.release()
        self.window.destroy()
        if self.on_close:
            self.on_close()

class RecordingInterface:
    def __init__(self, root, return_callback, config):
        self.root = root
        self.return_callback = return_callback
        self.config = config
        self.root.title("Grabación")
        
        # Static save path (hardcoded)
        self.static_path = Path.home() / "Videos" / "StaticRecordings"
        
        # Initialize video recorder
        self.recorder = None
        self.preview_window = None
        
        # Main frame
        self.main_frame = ttk.Frame(root, padding="20")
        self.main_frame.pack(expand=True, fill="both")
        
        # Return button at the top
        ttk.Button(
            self.main_frame,
            text="Volver al Menú",
            command=self.return_to_menu
        ).pack(anchor="nw", pady=(0, 20))
        
        # Create canvas for circular button
        canvas_size = 100
        self.canvas = tk.Canvas(
            self.main_frame,
            width=canvas_size,
            height=canvas_size,
            highlightthickness=0,
            bg=root.cget("bg")
        )
        self.canvas.pack(expand=True)
        
        # Create circular button
        self.is_recording = False
        button_radius = 40
        self.button = self.canvas.create_oval(
            canvas_size/2 - button_radius,
            canvas_size/2 - button_radius,
            canvas_size/2 + button_radius,
            canvas_size/2 + button_radius,
            fill="red",
            tags="button"
        )
        
        # Bind click events
        self.canvas.tag_bind("button", "<Button-1>", self.toggle_recording)
        
        # Status label
        self.status_label = ttk.Label(
            self.main_frame,
            text="Listo para grabar",
            font=("Arial", 12)
        )
        self.status_label.pack(pady=10)

    def return_to_menu(self):
        if self.is_recording:
            self.toggle_recording()
        if self.recorder:
            del self.recorder
        self.main_frame.destroy()
        self.return_callback()
        
    def toggle_recording(self, event=None):
        self.is_recording = not self.is_recording
        if self.is_recording:
            self.canvas.itemconfig(self.button, fill="darkred")
            self.status_label.config(text="Grabando...")
            self.recorder = VideoRecorder(
                self.static_path,
                self.config.get_custom_path(),
                self.config.get_video_format()
            )
            self.recorder.start_recording()
        else:
            self.canvas.itemconfig(self.button, fill="red")
            self.status_label.config(text="Grabación detenida")
            if self.recorder:
                video_paths = self.recorder.stop_recording()
                # Show preview of the custom path video
                self.show_preview(video_paths[1])  # Show the custom path video

    def show_preview(self, video_path):
        self.preview_window = PreviewWindow(
            self.root,
            video_path,
            on_close=lambda: setattr(self, 'preview_window', None)
        )

class SettingsInterface:
    def __init__(self, root, return_callback, config):
        self.root = root
        self.return_callback = return_callback
        self.config = config
        self.root.title("Configuración")
        
        # Main frame
        self.main_frame = ttk.Frame(root, padding="20")
        self.main_frame.pack(expand=True, fill="both")
        
        # Return button at the top
        ttk.Button(
            self.main_frame,
            text="Volver al Menú",
            command=self.return_to_menu
        ).pack(anchor="nw", pady=(0, 20))
        
        # Settings title
        ttk.Label(
            self.main_frame,
            text="Configuración",
            font=("Arial", 20)
        ).pack(pady=20)
        
        # Current path display
        self.path_var = tk.StringVar(value=self.config.get_custom_path())
        ttk.Label(
            self.main_frame,
            text="Carpeta de guardado personalizada:",
            font=("Arial", 12)
        ).pack(pady=(20, 5))
        
        path_frame = ttk.Frame(self.main_frame)
        path_frame.pack(fill="x", padx=20)
        
        ttk.Entry(
            path_frame,
            textvariable=self.path_var,
            state="readonly"
        ).pack(side="left", fill="x", expand=True)
        
        ttk.Button(
            path_frame,
            text="Cambiar",
            command=self.choose_directory
        ).pack(side="right", padx=(10, 0))
        
        # Video format selection
        ttk.Label(
            self.main_frame,
            text="Formato de video:",
            font=("Arial", 12)
        ).pack(pady=(20, 5))
        
        self.format_var = tk.StringVar(value=self.config.get_video_format())
        format_frame = ttk.Frame(self.main_frame)
        format_frame.pack(fill="x", padx=20)
        
        ttk.Radiobutton(
            format_frame,
            text="MP4",
            value="mp4",
            variable=self.format_var,
            command=self.update_format
        ).pack(side="left", padx=10)
        
        ttk.Radiobutton(
            format_frame,
            text="AVI",
            value="avi",
            variable=self.format_var,
            command=self.update_format
        ).pack(side="left", padx=10)
        
    def choose_directory(self):
        directory = filedialog.askdirectory(
            initialdir=self.config.get_custom_path(),
            title="Seleccionar carpeta de guardado"
        )
        if directory:
            self.config.set_custom_path(directory)
            self.path_var.set(directory)
            
    def update_format(self):
        self.config.set_video_format(self.format_var.get())
        
    def return_to_menu(self):
        self.main_frame.destroy()
        self.return_callback()

class MenuInterface:
    def __init__(self, root):
        self.root = root
        self.config = Config()
        self.root.title("Grabador de Video")
        
        # Main frame
        self.main_frame = ttk.Frame(root, padding="20")
        self.main_frame.pack(expand=True, fill="both")
        
        # Title
        ttk.Label(
            self.main_frame,
            text="Grabador de Video",
            font=("Arial", 24)
        ).pack(pady=20)
        
        # Buttons
        button_frame = ttk.Frame(self.main_frame)
        button_frame.pack(pady=20)
        
        ttk.Button(
            button_frame,
            text="Iniciar Grabación",
            command=self.start_recording
        ).pack(pady=10, fill="x")
        
        ttk.Button(
            button_frame,
            text="Configuración",
            command=self.open_settings
        ).pack(pady=10, fill="x")
        
        ttk.Button(
            button_frame,
            text="Salir",
            command=self.root.quit
        ).pack(pady=10, fill="x")
        
    def start_recording(self):
        # Clear the main frame and open the recording interface
        self.main_frame.destroy()
        RecordingInterface(self.root, self.return_to_menu, self.config)
        
    def open_settings(self):
        # Clear the main frame and open the settings interface
        self.main_frame.destroy()
        SettingsInterface(self.root, self.return_to_menu, self.config)
        
    def return_to_menu(self):
        # Recreate the main menu interface
        self.main_frame = ttk.Frame(self.root, padding="20")
        self.main_frame.pack(expand=True, fill="both")
        
        # Title
        ttk.Label(
            self.main_frame,
            text="Grabador de Video",
            font=("Arial", 24)
        ).pack(pady=20)
        
        # Buttons
        button_frame = ttk.Frame(self.main_frame)
        button_frame.pack(pady=20)
        
        ttk.Button(
            button_frame,
            text="Iniciar Grabación",
            command=self.start_recording
        ).pack(pady=10, fill="x")
        
        ttk.Button(
            button_frame,
            text="Configuración",
            command=self.open_settings
        ).pack(pady=10, fill="x")
        
        ttk.Button(
            button_frame,
            text="Salir",
            command=self.root.quit
        ).pack(pady=10, fill="x")

def main():
    root = tk.Tk()
    app = MenuInterface(root)
    root.mainloop()

if __name__ == "__main__":
    main()