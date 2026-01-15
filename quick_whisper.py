from utils.quick_whisper import QuickWhisper

if __name__ == "__main__":
    app = QuickWhisper()
    # Note: WM_DELETE_WINDOW protocol is set in setup_system_tray()
    # to minimize to tray (or on_closing if tray unavailable)
    try:
        app.mainloop()
    except KeyboardInterrupt:
        print("\nCtrl+C detected, shutting down.")
        # Ensure cleanup happens even on Ctrl+C
        if app.winfo_exists(): # Check if window still exists
            app.on_closing()
    except Exception as e:
        print(f"Unhandled exception in main loop: {e}")
        import traceback
        traceback.print_exc()
        # Attempt cleanup even on other errors
        if app.winfo_exists():
            app.on_closing()
