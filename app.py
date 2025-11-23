import sys
from streamlit.web.cli import main

def start():
    sys.argv = ["streamlit","run", "main.py"]
    print('entering __main__')
    main()
    print('exiting __main__')

if __name__ == "__main__":
    start()
