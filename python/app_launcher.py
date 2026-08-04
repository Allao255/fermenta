"""PyInstaller entry point for the wdfviola GUI.

Frozen build resolves bundled data (the C++ plugin templates) from
sys._MEIPASS; see wdfviola/gui.py :: _export_project.
"""
from wdfviola.gui import launch

if __name__ == "__main__":
    launch()
