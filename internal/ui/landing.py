import tkinter as tk

def signup():
    signup_button.config(text="Signing up ...")
def login():
    login_button.config(text="Logging in ...")

root = tk.Tk()

root.title("Ruach_ToDo")
root.geometry("800x500")

heading = tk.Label(root, text="Welcome to Ruach_ToDo")
heading.pack(pady=20)

subheading= tk.Label(root, text="Your efficient task_manager for your day-to-day activities", activebackground="Grey", activeforeground="blue",anchor="center")
subheading.pack(pady=25)

sign_count = 1
log_count = 1
if sign_count % 2 == 0:
    signup_button = tk.Button(root, text="Sign up", command=signup)
    signup_button.pack()
else:
    signup_button = tk.Button(root, text="Sign up", command=signup)
    signup_button.pack()

if log_count % 2 == 0: 
    login_button = tk.Button(root, text="Log in", command=login)
    login_button.pack()
else:
    signup_button = tk.Button(root, text="Sign up", command=signup)
    signup_button.pack()

root.mainloop()

