# import tkinter as tk

# def clicked():
#     root.title("Hello")

# root = tk.Tk()
# root.geometry("500x300")

# button = tk.Button(root,text="Click Me", command=clicked)
# button.pack()

# root.mainloop()

import tkinter as tk

def say_hi():
    button.config(text="Hello Ayomide!")

root = tk.Tk()

root.title("Ruach_ToDo")
root.geometry("800x500")

label = tk.Label(root, text="Welcome")
label.pack(pady=20)

button = tk.Button(root, text="Say Hi", command=say_hi)
button.pack()

root.mainloop()

