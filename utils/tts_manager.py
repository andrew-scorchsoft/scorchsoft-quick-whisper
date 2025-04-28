import threading
import pyttsx3
import platform

class TTSManager:
    def __init__(self, parent):
        self.parent = parent
        self.tts_engine = None
        self.tts_lock = threading.Lock()
        self.current_speech_thread = None
        self.speech_should_stop = threading.Event()
        self.init_tts_engine()
        
    def init_tts_engine(self):
        """Initialize or reinitialize the TTS engine."""
        if platform.system() == 'Windows':
            try:
                # Clean up existing engine if it exists
                if self.tts_engine:
                    try:
                        self.tts_engine.stop()
                    except:
                        pass
                
                self.tts_engine = pyttsx3.init()
                self.tts_engine.setProperty('rate', 175)  # Adjust speed
                print("TTS engine initialized successfully")
            except Exception as e:
                print(f"TTS initialization error: {e}")
                self.tts_engine = None
                
    def speak_text(self, text):
        """Speak the given text using the TTS engine."""
        # Only available on Windows
        if platform.system() != 'Windows':
            return
            
        # Signal any existing speech to stop
        self.speech_should_stop.set()
        
        # If there's a current speech thread, wait briefly for it to stop
        if self.current_speech_thread and self.current_speech_thread.is_alive():
            self.current_speech_thread.join(0.1)  # Wait max 100ms
        
        # Reset the stop flag
        self.speech_should_stop.clear()
        
        # Create and start new speech thread
        self.current_speech_thread = threading.Thread(
            target=self._speak_thread, 
            args=(text,), 
            daemon=True
        )
        self.current_speech_thread.start()
        
    def _speak_thread(self, text):
        """Thread function that actually performs the speech."""
        with self.tts_lock:
            try:
                # Reinitialize engine if needed
                if not self.tts_engine:
                    self.init_tts_engine()
                
                if self.tts_engine and not self.speech_should_stop.is_set():
                    try:
                        self.tts_engine.stop()
                    except:
                        self.init_tts_engine()
                    
                    if self.tts_engine:
                        self.tts_engine.say(text)
                        
                        # Break runAndWait into smaller chunks to check for interruption
                        while not self.speech_should_stop.is_set():
                            try:
                                self.tts_engine.startLoop(False)
                                # Run a short iteration
                                if not self.tts_engine.iterate():
                                    break
                                self.tts_engine.endLoop()
                            except:
                                break
                        
                        # If we were interrupted, stop the engine
                        if self.speech_should_stop.is_set():
                            try:
                                self.tts_engine.stop()
                            except:
                                pass
                
            except Exception as e:
                print(f"TTS error: {e}")
                self.init_tts_engine()
                
    def cleanup(self):
        """Clean up resources before closing."""
        # Signal any speech to stop
        self.speech_should_stop.set()
        
        # Wait briefly for speech to stop
        if self.current_speech_thread and self.current_speech_thread.is_alive():
            self.current_speech_thread.join(0.2)
        
        # Clean up TTS engine
        if self.tts_engine:
            with self.tts_lock:
                try:
                    self.tts_engine.stop()
                    self.tts_engine = None
                except:
                    pass 