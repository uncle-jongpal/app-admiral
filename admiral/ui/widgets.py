"""공통 화면 부품: 카드, 설정 한 줄, 스위치, 줄바꿈 라벨.
기능(features)은 이 부품만 써서 화면을 만든다 → 모든 기능이 같은 모양."""
import customtkinter as ctk

from .theme import FONT, THEME


class Wrapper:
    """창 폭에 맞춰 줄바꿈할 라벨 모음. 메인 창이 폭이 바뀔 때만 apply() 를 부른다."""

    def __init__(self):
        self._items = []  # (라벨, 폭에서 뺄 값)

    def add(self, label, margin=200):
        self._items.append((label, margin))
        return label

    def apply(self, content_width):
        for lb, margin in self._items:
            try:
                lb.configure(wraplength=max(content_width - margin, 220))
            except Exception:
                pass


def card(parent, title=None, grow=False):
    c = ctk.CTkFrame(parent, fg_color=THEME["card"], corner_radius=14, border_width=1, border_color=THEME["line"])
    c.pack(fill="both" if grow else "x", expand=grow, pady=(0, 0 if grow else 10))
    if title:
        ctk.CTkLabel(c, text=title, text_color=THEME["sub"], font=(FONT, 12, "bold"),
                     anchor="w").pack(fill="x", padx=16, pady=(12, 6))
    return c


def label(parent, text, wrapper=None, size=11, color="sub", margin=200, bold=False):
    lb = ctk.CTkLabel(parent, text=text, text_color=THEME[color], font=(FONT, size, "bold" if bold else "normal"),
                      anchor="w", justify="left")
    if wrapper is not None:
        wrapper.add(lb, margin)
    return lb


def setting_row(parent, title, desc=None, wrapper=None):
    """설정 한 줄: 왼쪽 제목·설명, 오른쪽 조작부. 조작부를 넣을 프레임을 돌려준다."""
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", padx=16, pady=(4, 10))
    right = ctk.CTkFrame(row, fg_color="transparent")
    right.pack(side="right", padx=(12, 0))
    left = ctk.CTkFrame(row, fg_color="transparent")
    left.pack(side="left", fill="x", expand=True)
    ctk.CTkLabel(left, text=title, text_color=THEME["text"], font=(FONT, 13), anchor="w").pack(fill="x")
    if desc:
        label(left, desc, wrapper).pack(fill="x")
    return right


def switch(parent, value, on_change):
    var = ctk.BooleanVar(value=value)
    ctk.CTkSwitch(parent, text="", variable=var, width=46, progress_color=THEME["accent"],
                  command=lambda: on_change(bool(var.get()))).pack()
    return var


def segmented(parent, values, current, on_change, width=200):
    var = ctk.StringVar(value=current)
    ctk.CTkSegmentedButton(parent, values=values, variable=var, command=on_change, font=(FONT, 12), height=30,
                           width=width, selected_color=THEME["accent"],
                           unselected_color=THEME["field"]).pack()
    return var


def button(parent, text, command, primary=False, width=72, height=30):
    return ctk.CTkButton(parent, text=text, width=width, height=height, font=(FONT, 12), command=command,
                         fg_color=THEME["accent"] if primary else THEME["field"],
                         hover_color=THEME["accent_hover"] if primary else THEME["field_hover"])
