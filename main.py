import sys
import os

# Ensure the project root is on sys.path when run as a script
sys.path.insert(0, os.path.dirname(__file__))

from gui.wizard import Wizard


def main() -> None:
    app = Wizard()
    app.mainloop()


if __name__ == "__main__":
    main()
