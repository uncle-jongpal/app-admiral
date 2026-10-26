"""녹음 중 화면 오른쪽 아래 빨간 표시."""
import customtkinter as ctk

from .theme import FONT, STATE_COLORS


class Overlay:
    def __init__(self, root):
        self.root = root
        self.win = ctk.CTkToplevel(root, fg_color=STATE_COLORS["rec"])
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        ctk.CTkLabel(self.win, text="●  녹음 중", text_color="white", font=(FONT, 14, "bold")).pack(padx=16, pady=8)
        self.win.withdraw()

    def show(self, on):
        if on:
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            self.win.geometry(f"+{sw - 190}+{sh - 120}")
            self.win.deiconify()
        else:
            self.win.withdraw()
