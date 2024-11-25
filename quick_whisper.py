from utils.quick_whisper import QuickWhisper

if __name__ == "__main__":
    app = QuickWhisper()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
