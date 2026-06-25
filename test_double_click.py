import tkinter as tk
import sys

def on_double_click(event):
    print("double click")
    sys.stdout.flush()
    root.destroy()

root = tk.Tk()
root.title("Test")
root.geometry("200x100+100+100")
label = tk.Label(root, text="Double click me", bg="white")
label.pack(expand=True, fill="both")
label.bind("<Double-Button-1>", on_double_click)
root.bind("<Double-Button-1>", on_double_click)
root.mainloop()
