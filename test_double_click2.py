import tkinter as tk
import sys

def on_double_click(event):
    print("double click")
    sys.stdout.flush()
    root.destroy()

def on_drag_start(event):
    print(f"drag {event.x},{event.y}")
    sys.stdout.flush()

root = tk.Tk()
root.title("Test2")
root.geometry("280x80+100+100")
root.overrideredirect(True)
root.attributes("-topmost", True)
root.configure(bg="black")
root.attributes("-alpha", 0.99)
root.wm_attributes("-transparentcolor", "black")

frame = tk.Frame(root, bg="black")
frame.pack(fill="x", padx=12, pady=2)
label = tk.Label(frame, text="BTC-USDT-SWAP", font=("Microsoft YaHei", 11, "bold"), bg="black", fg="white", width=18, anchor="w")
label.pack(side="left")

def bind_recursive(widget, event, handler):
    widget.bind(event, handler)
    for child in widget.winfo_children():
        bind_recursive(child, event, handler)

menu = tk.Menu(root, tearoff=0)
menu.add_command(label="Exit", command=root.destroy)
root.bind("<ButtonRelease-3>", lambda e: menu.post(e.x_root, e.y_root))

bind_recursive(root, "<Double-Button-1>", on_double_click)

root.mainloop()
