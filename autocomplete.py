"""Live suggestions without the native combobox popup stealing typing focus."""
import tkinter as tk


class LiveSuggestions:
    def __init__(self, widget, variable, refresh):
        self.widget, self.variable, self.refresh = widget, variable, refresh
        self.popup = None
        self.pending = None
        self.choosing = False
        self.trace = variable.trace_add('write', self.changed)
        widget.bind('<Down>', lambda event: self.move(1), add='+')
        widget.bind('<Up>', lambda event: self.move(-1), add='+')
        widget.bind('<Return>', self.choose, add='+')
        widget.bind('<Escape>', self.hide, add='+')
        widget.bind('<FocusOut>', self.hide, add='+')
        widget.bind('<Destroy>', self.destroy, add='+')
        widget.bind('<ButtonPress-1>', self.hide, add='+')
        self.window = widget.winfo_toplevel()
        self.configure_binding = self.window.bind('<Configure>', self.hide, add='+')

    def changed(self, *args):
        if self.choosing:
            return
        if self.pending is not None:
            self.widget.after_cancel(self.pending)
        self.pending = self.widget.after_idle(self.show)

    def show(self):
        self.pending = None
        self.refresh()
        values = list(self.widget['values'])
        if self.widget.focus_get() != self.widget or not self.variable.get().strip() or not values:
            self.hide()
            return
        if self.popup is None:
            self.popup = tk.Toplevel(self.widget)
            self.popup.withdraw()
            self.popup.overrideredirect(True)
            self.popup.attributes('-topmost', True)
            self.list = tk.Listbox(self.popup, exportselection=False, takefocus=False)
            scroll = tk.Scrollbar(self.popup, command=self.list.yview)
            self.list.configure(yscrollcommand=scroll.set)
            scroll.pack(side='right', fill='y')
            self.list.pack(fill='both', expand=True)
            self.list.bind('<ButtonPress-1>', self.click)
        self.list.delete(0, 'end')
        for value in values:
            self.list.insert('end', value)
        self.list.configure(height=min(8, len(values)))
        self.list.selection_set(0)
        self.widget.update_idletasks()
        width = max(self.widget.winfo_width(), 260)
        self.popup.geometry(f'{width}x{min(8, len(values)) * 22 + 4}+{self.widget.winfo_rootx()}+{self.widget.winfo_rooty() + self.widget.winfo_height()}')
        self.popup.deiconify()

    def move(self, delta):
        if self.popup is None or not self.popup.winfo_viewable():
            self.show()
        if self.popup is not None and self.popup.winfo_viewable():
            selected = self.list.curselection()
            index = max(0, min(self.list.size() - 1, (selected[0] if selected else -1) + delta))
            self.list.selection_clear(0, 'end')
            self.list.selection_set(index)
            self.list.see(index)
            return 'break'

    def click(self, event):
        index = self.list.nearest(event.y)
        self.list.selection_clear(0, 'end')
        self.list.selection_set(index)
        self.choose()
        return 'break'

    def choose(self, event=None):
        if self.popup is None or not self.popup.winfo_viewable() or not self.list.curselection():
            return
        value = self.list.get(self.list.curselection()[0])
        self.choosing = True
        try:
            self.variable.set(value)
            self.widget.icursor('end')
            self.widget.event_generate('<<ComboboxSelected>>')
        finally:
            self.choosing = False
        self.hide()
        return 'break'

    def hide(self, event=None):
        if self.pending is not None:
            self.widget.after_cancel(self.pending)
            self.pending = None
        if self.popup is not None:
            self.popup.withdraw()

    def destroy(self, event):
        if event.widget == self.widget:
            self.window.unbind('<Configure>', self.configure_binding)
            if self.pending is not None:
                self.widget.after_cancel(self.pending)
            self.variable.trace_remove('write', self.trace)
            if self.popup is not None:
                self.popup.destroy()
                self.popup = None
